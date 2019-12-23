/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2019 Yonatan Goldschmidt
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

/* skeleton taken from structsizes.cc plugin by Richard W.M. Jones
   https://rwmj.wordpress.com/2016/02/24/playing-with-gcc-plugins/ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <gcc-plugin.h>
#include <tree.h>
#include <print-tree.h>


int plugin_is_GPL_compatible; // must be defined for the plugin to run

static FILE *output_file;
static const char *target_struct = NULL;

// taken from linux/scripts/gcc-plugins/randomize_layout_plugin.c
#define ORIG_TYPE_NAME(node) \
    (TYPE_NAME(TYPE_MAIN_VARIANT(node)) != NULL_TREE ? ((const char *)IDENTIFIER_POINTER(TYPE_NAME(TYPE_MAIN_VARIANT(node)))) : NULL)

// from linux
#define container_of(ptr, type, member) ({                      \
    const typeof( ((type *)0)->member ) *__mptr = (ptr);    \
    (type *)( (char *)__mptr - offsetof(type,member) );})

static void debug_tree_helper(tree t, const char *msg)
{
#ifndef NDEBUG
    fprintf(stderr, "dumping tree: '%s'\n", msg);
    debug_tree(t);
    fprintf(stderr, "\n\n");
    fflush(stdout);
#endif
}

// sadly GCC doesn't have any nice list API. probably because you're just supposed
// to use C++.
struct list {
    struct list *next;
};

struct dumped_list {
    struct list list;
    char name[0];
};

static struct dumped_list dumped_structs;

struct dump_list {
    struct list list;
    tree type;
};

static struct dump_list to_dump;

static bool was_dumped(const char *name)
{
    struct list *iter = dumped_structs.list.next;

    while (NULL != iter) {
        struct dumped_list *n = container_of(iter, struct dumped_list, list);

        if (0 == strcmp(name, n->name)) {
            return true;
        }
        iter = iter->next;
    }

    return false;
}

static void add_to_list(struct list *iter, struct list *n)
{
    while (NULL != iter->next) {
        iter = iter->next;
    }

    iter->next = n;
}

static void add_to_dumped_structs(const char *name)
{
    const size_t len = strlen(name) + 1;
    struct dumped_list *n = (struct dumped_list*)xmalloc(sizeof(*n) + len);
    n->list.next = NULL;
    memcpy(n->name, name, len);

    add_to_list(&dumped_structs.list, &n->list);
}

static void add_to_dump_list(tree type)
{
    struct dump_list *n = (struct dump_list*)xmalloc(sizeof(*n));
    n->list.next = NULL;
    n->type = type;

    add_to_list(&to_dump.list, &n->list);
}

// types that don't have another type beneath them.
static bool is_basic_type(tree type)
{
    switch (TREE_CODE(type)) {
    case INTEGER_TYPE:
    case BOOLEAN_TYPE:
    case ENUMERAL_TYPE:
    case REAL_TYPE:
    case RECORD_TYPE:
    case UNION_TYPE:
    case VOID_TYPE:
    case FUNCTION_TYPE:
        return true;

    default:
        return false;
    }
}

static void print_array_type(const tree field_type, size_t sizeof_array)
{
    const size_t elem_size = tree_to_uhwi(TYPE_SIZE_UNIT(TREE_TYPE(field_type)));
    size_t num_elem;

    if (NULL == TYPE_SIZE_UNIT(field_type)) {
        // it is a flexible array
        // linux, btw, has a more complex "is_flexible_array" function in the randomize_layout_plugin.
        // but until proven wrong, that ^^ check is sufficient.
        num_elem = 0;
    } else if (0 == elem_size) {
        // probably an empty struct (happens in linux with lock_class_key)
        // let it be 0 elements as well. not that it matters...
        num_elem = 0;
    } else {
        // it might be 0 / elem_size, in which case we also end up with num_elem = 0.
        num_elem = tree_to_uhwi(TYPE_SIZE_UNIT(field_type)) / elem_size;
    }

    fprintf(output_file, "Array(%zu, %zu, ", sizeof_array, num_elem);
}

static void print_pointer_type(size_t size)
{
    fprintf(output_file, "Pointer(%zu, ", size);
}

// returns 0 if type has no size (i.e VOID_TYPE)
static size_t get_field_size(const tree field_type)
{
    if (TYPE_SIZE(field_type)) {
        return tree_to_uhwi(TYPE_SIZE(field_type));
    } else {
        return 0;
    }
}

static bool is_struct_or_union(const_tree type)
{
    return RECORD_TYPE == TREE_CODE(type) || UNION_TYPE == TREE_CODE(type);
}

// returns the underlying type name for structs/unions/enums and their typedefs.
// returns the typedef name if the underlying type doesn't have a name.
static const char *get_type_name(const_tree type)
{
    gcc_assert(is_struct_or_union(type) || ENUMERAL_TYPE == TREE_CODE(type));
    gcc_assert(TYPE_IDENTIFIER(type)); // must be named

    // __va_list_tag is the final type beneath __builtin_va_list.
    // it behaves different from other types - it has a TYPE_MAIN_VARIANT, but the main TYPE_NAME seems to give
    // an unexpected tree, and therefore ORIG_TYPE_NAME returns a garbage value.
    // I think this patch is good enough.
    if (0 == strcmp("__va_list_tag", IDENTIFIER_POINTER(TYPE_IDENTIFIER(type)))) {
        return "__va_list_tag";
    }

    // TYPE_MAIN_VARIANT might be different if, afaik:
    // 1. type is a modified version of another type (with "const", "volatile", ...)
    // 2. type is a typedefed version of another type (possibly with modifiers)
    // anyway, we'll use the TYPE_MAIN_VARIANT name if possible.
    const char *orig_name = ORIG_TYPE_NAME(type);
    if (NULL != orig_name) {
        return orig_name;
    }

    // then it must be named with a typedef
    return IDENTIFIER_POINTER(TYPE_IDENTIFIER(type));
}

static void print_spaces(size_t n)
{
    for (size_t i = 0; i < n; ++i) {
        fputc(' ', output_file);
    }
}

static void dump_struct(const_tree base_type, const char *name, size_t indent_level);

static void dump_fields(tree first_field, size_t base_offset, size_t indent_level)
{
    for (tree field = first_field; field; field = TREE_CHAIN(field)) {
        gcc_assert(TREE_CODE(field) == FIELD_DECL);

        debug_tree_helper(field, "field");

        tree field_type = TREE_TYPE(field);

        // field offset
        size_t offset = base_offset;
        tree t_offset = DECL_FIELD_OFFSET(field);
        gcc_assert(TREE_CODE(t_offset) == INTEGER_CST && TREE_CONSTANT(t_offset));
        offset += tree_to_uhwi(t_offset) * 8;
        // add bit offset. there's an explanation about why it's required, see macro declaration in tree.h
        tree t_bit_offset = DECL_FIELD_BIT_OFFSET(field);
        gcc_assert(TREE_CODE(t_bit_offset) == INTEGER_CST && TREE_CONSTANT(t_bit_offset));
        offset += tree_to_uhwi(t_bit_offset);

        // field name
        const char *field_name;
        const_tree decl_name = DECL_NAME(field);
        if (NULL != decl_name) {
            field_name = IDENTIFIER_POINTER(decl_name);
        } else {
            // unnamed bitfield, ignore and continue
            // I've also seen integers used for struct padding, so I'll allow that as well.
            // (e.g linux/include/uapi/linux/timex.h timex)
            if (DECL_BIT_FIELD(field) || TREE_CODE(field_type) == INTEGER_TYPE) {
                continue;
            }

            // shouldn't be NULL, only allowed for anonymous unions.
            gcc_assert(is_struct_or_union(field_type));

            // inline the fields into current struct/union.
            dump_fields(TYPE_FIELDS(field_type), offset, indent_level);
            continue;
        }

        print_spaces((indent_level + 1) * 4);
        fprintf(output_file, "'%s': (%zu, ", field_name, offset);

        size_t type_depth = 0;

        // handle arrays and pointers, until we reach a "basic" type.
        while (!is_basic_type(field_type)) {
            const size_t field_type_size = get_field_size(field_type);

            switch (TREE_CODE(field_type)) {
            case VECTOR_TYPE:
            case ARRAY_TYPE:
                print_array_type(field_type, field_type_size);
                break;

            case POINTER_TYPE:
            case REFERENCE_TYPE: // POINTER_TYPE_P checks for this as well. let's try to be c++ compatible.
                print_pointer_type(field_type_size);
                break;

            default:
                debug_tree_helper(field_type, "unknown type!");
                gcc_unreachable();
            }

            // next
            field_type = TREE_TYPE(field_type);

            ++type_depth;
        }

        const size_t field_size = get_field_size(field_type);

        if (NULL == TYPE_IDENTIFIER(field_type) && is_struct_or_union(field_type)) {
            // anonymous definition of struct/union, just dump it.
            fprintf(output_file, "StructField(%zu, ", field_size);
            dump_struct(field_type, NULL, indent_level + 1);
            fprintf(output_file, ")");
        } else {
            // is it another struct / union?
            if (is_struct_or_union(field_type)) {
                // I assume that "tree" objects are alive basically forever.
                add_to_dump_list(field_type);

                fprintf(output_file, "StructField(%zu, '%s')", field_size, get_type_name(field_type));
            } else if (TREE_CODE(field_type) == VOID_TYPE) {
                fprintf(output_file, "Void()");
            } else if (DECL_BIT_FIELD(field)) {
                // bitfields TREE_TYPE has no TYPE_IDENTIFIER.
                fprintf(output_file, "Bitfield(%ld)", tree_to_uhwi(DECL_SIZE(field)));
            } else if (TREE_CODE(field_type) == FUNCTION_TYPE) {
                // function pointers
                // TODO: print type & args
                fprintf(output_file, "Function()");
            } else {
                const char *type_name_s;
                if (TREE_CODE(field_type) == ENUMERAL_TYPE) {
                    if (NULL == TYPE_IDENTIFIER(field_type)) {
                        type_name_s = "anonymous enum";
                    } else {
                        type_name_s = get_type_name(field_type);
                    }
                } else {
                    type_name_s = IDENTIFIER_POINTER(TYPE_IDENTIFIER(field_type));
                }

                fprintf(output_file, "Scalar(%zu, '%s', %s)", field_size, type_name_s,
                    TYPE_UNSIGNED(field_type) ? "False" : "True");
            }
        }

        for (size_t i = 0; i < type_depth; ++i) {
            fprintf(output_file, ")");
        }

        fprintf(output_file, "),\n");
    }
}

static void dump_struct(const_tree base_type, const char *name, size_t indent_level)
{
    if (NULL != name) {
        if (was_dumped(name)) {
            return;
        }
        // add it immediately, so if we find any back references into current struct, we don't
        // dump it again.
        add_to_dumped_structs(name);

        fprintf(output_file, "'%s': ", name);
    } else {
        // indent != 0 means this struct is dumped inline in a StructField.
        // if indent == 0 and the struct has no name, something is wrong.
        gcc_assert(indent_level != 0);
    }

    gcc_assert(COMPLETE_TYPE_P(base_type));

    gcc_assert(is_struct_or_union(base_type));
    fprintf(output_file, "Struct(");
    if (NULL != name) {
        fprintf(output_file, "'%s'", name);
    } else {
        fprintf(output_file, "None");
    }
    fprintf(output_file, ", %ld, {\n", tree_to_uhwi(TYPE_SIZE(base_type)));

    dump_fields(TYPE_FIELDS(base_type), 0, indent_level);

    print_spaces(indent_level * 4);
    fprintf(output_file, "})");
    if (indent_level == 0) {
        fprintf(output_file, ",\n");
    }
}

static void plugin_finish_type(void *event_data, void *user_data)
{
    tree type = (tree)event_data;

    if (TREE_CODE(type) != RECORD_TYPE // it is a struct tree
        || TYPE_FIELDS(type) == NULL_TREE) // not empty, i.e not a forward declaration.
    {
        return;
    }

    tree type_name = TYPE_IDENTIFIER(type);
    if (NULL == type_name) {
        // anonymous, ignore.
        return;
    }
    const char *type_name_s = IDENTIFIER_POINTER(type_name);

    if (NULL != target_struct && strcmp(type_name_s, target_struct)) {
        // bye
        return;
    }

    dump_struct(type, type_name_s, 0);
}

static void plugin_finish(void *event_data, void *user_data)
{
    // all leftovers
    for (struct list *iter = to_dump.list.next; iter != NULL; iter = iter->next) {
        struct dump_list *n = container_of(iter, struct dump_list, list);

        // if it's not complete by now, it must've had references only as a pointer
        // w/ a forward declaration.
        // (by the time a struct field is declared, the type must be complete)
        if (COMPLETE_TYPE_P(n->type)) {
            // items added to the list are surely named.
            gcc_assert(TYPE_IDENTIFIER(n->type));

            dump_struct(n->type, get_type_name(n->type), 0);
        }
    }

    fprintf(output_file, "# dumped structs:\n");

    struct list *iter = dumped_structs.list.next;
    while (NULL != iter) {
        struct dumped_list *n = container_of(iter, struct dumped_list, list);

        fprintf(output_file, "# %s\n", n->name);
        iter = iter->next;
    }

    fprintf(output_file, "}\n");

    fflush(output_file);
}

int plugin_init(struct plugin_name_args *plugin_info, struct plugin_gcc_version *version)
{
    const char *output = NULL;

    for (int i = 0; i < plugin_info->argc; ++i) {
        if (0 == strcmp(plugin_info->argv[i].key, "output")) {
            output = plugin_info->argv[i].value;
        }

        // can be given with -fplugin-arg-struct_layout-struct=<struct>
        if (0 == strcmp(plugin_info->argv[i].key, "struct")) {
            target_struct = xstrdup(plugin_info->argv[i].value);
        }
    }

    if (NULL == output) {
        fprintf(stderr, "structlayout plugin: missing parameter: -fplugin-arg-struct_layout-output=<output>\n");
        exit(EXIT_FAILURE);
    }

    output_file = fopen(output, "w");
    if (NULL == output_file) {
        perror(output);
        exit(EXIT_FAILURE);
    }

    fprintf(output_file, "try:\n    from python.fields import *\nexcept ImportError:\n    from fields import *\nstructs = {\n");

    register_callback(plugin_info->base_name, PLUGIN_FINISH_TYPE, plugin_finish_type, NULL);
    register_callback(plugin_info->base_name, PLUGIN_FINISH, plugin_finish, NULL);

    return 0;
}
