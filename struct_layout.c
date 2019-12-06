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
    size_t num_elem;

    // is it a flexible array?
    if (TYPE_SIZE_UNIT(field_type)) {
        const size_t elem_size = TREE_INT_CST_LOW(TYPE_SIZE_UNIT(TREE_TYPE(field_type)));
        // it might be 0 / elem_size, in which case we also end up with num_elem = 0.
        num_elem = TREE_INT_CST_LOW(TYPE_SIZE_UNIT(field_type)) / elem_size;
    } else {
        num_elem = 0;
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
        return TREE_INT_CST_LOW(TYPE_SIZE(field_type));
    } else {
        return 0;
    }
}

static bool is_struct_or_union(const_tree type)
{
    return RECORD_TYPE == TREE_CODE(type) || UNION_TYPE == TREE_CODE(type);
}

static void print_spaces(size_t n)
{
    for (size_t i = 0; i < n; ++i) {
        fputc(' ', output_file);
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

        fprintf(output_file, "%s = ", name);
    }

    gcc_assert(COMPLETE_TYPE_P(base_type));

    gcc_assert(is_struct_or_union(base_type));
    fprintf(output_file, "%s(", RECORD_TYPE == TREE_CODE(base_type) ? "Struct" : "Union");
    if (NULL != name) {
        fprintf(output_file, "'%s'", name);
    } else {
        fprintf(output_file, "None");
    }
    fprintf(output_file, ", %ld, {\n", TREE_INT_CST_LOW(TYPE_SIZE(base_type)));

    for (tree field = TYPE_FIELDS(base_type); field; field = TREE_CHAIN(field)) {
        gcc_assert(TREE_CODE(field) == FIELD_DECL);

        debug_tree_helper(field, "field");

        tree field_type = TREE_TYPE(field);

        // field name
        const char *field_name;
        const_tree decl_name = DECL_NAME(field);
        bool anonymous = false;
        if (NULL != decl_name) {
            field_name = IDENTIFIER_POINTER(decl_name);
        } else {
            // unnamed bitfield, ignore and continue
            if (DECL_BIT_FIELD(field)) {
                continue;
            }

            // shouldn't be NULL, only allowed for anonymous unions.
            gcc_assert(UNION_TYPE == TREE_CODE(field_type));
            field_name = "(anonymous union)";
            anonymous = true;
        }

        // field offset
        tree t_offset = DECL_FIELD_OFFSET(field);
        gcc_assert(TREE_CODE(t_offset) == INTEGER_CST && TREE_CONSTANT(t_offset));
        size_t offset = TREE_INT_CST_LOW(t_offset) * 8;
        // add bit offset. there's an explanation about why it's required, see macro declaration in tree.h
        tree t_bit_offset = DECL_FIELD_BIT_OFFSET(field);
        gcc_assert(TREE_CODE(t_bit_offset) == INTEGER_CST && TREE_CONSTANT(t_bit_offset));
        offset += TREE_INT_CST_LOW(t_bit_offset);

        print_spaces((indent_level + 1) * 4);
        fprintf(output_file, "'%s': (%zu, ", field_name, offset);

        size_t type_depth = 0;

        // handle arrays and pointers, until we reach a "basic" type.
        while (!is_basic_type(field_type)) {
            const size_t field_type_size = get_field_size(field_type);

            switch (TREE_CODE(field_type)) {
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

        tree type_name = TYPE_IDENTIFIER(field_type);
        if (NULL == type_name && is_struct_or_union(field_type)) {
            // anonymous definition of struct/union, just dump it.
            fprintf(output_file, "StructField(%zu, ", field_size);
            dump_struct(field_type, NULL, indent_level + 1);
            fprintf(output_file, ")");
        } else {
            // is it another struct / union?
            if (TREE_CODE(field_type) == RECORD_TYPE || (TREE_CODE(field_type) == UNION_TYPE && !anonymous)) {
                // add to dump list, if not anonymous.

                // I assume that "tree" objects are alive basically forever.
                add_to_dump_list(field_type);
            }

            if (TREE_CODE(field_type) == VOID_TYPE) {
                fprintf(output_file, "Void()");
            } else if (DECL_BIT_FIELD(field)) {
                // bitfields TREE_TYPE has no TYPE_IDENTIFIER.
                fprintf(output_file, "Bitfield(%ld)", TREE_INT_CST_LOW(DECL_SIZE(field)));
            } else if (TREE_CODE(field_type) == FUNCTION_TYPE) {
                // function pointers
                // TODO: print type & args
                fprintf(output_file, "Function()");
            } else if (is_struct_or_union(field_type)) {
                const char *field_class;
                if (TREE_CODE(field_type) == RECORD_TYPE) {
                    field_class = "StructField";
                } else if (TREE_CODE(field_type) == UNION_TYPE) {
                    field_class = "UnionField";
                }
                fprintf(output_file, "%s(%zu, '%s')", field_class, field_size, IDENTIFIER_POINTER(type_name));
            } else {
                fprintf(output_file, "Scalar(%zu, '%s', %s)", field_size, IDENTIFIER_POINTER(type_name),
                    TYPE_UNSIGNED(field_type) ? "False" : "True");
            }
        }

        for (size_t i = 0; i < type_depth; ++i) {
            fprintf(output_file, ")");
        }

        fprintf(output_file, "),\n");
    }

    print_spaces(indent_level * 4);
    fprintf(output_file, "})");
    if (indent_level == 0) {
        fputc('\n', output_file);
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

    const char *name = ORIG_TYPE_NAME(type);
    if (NULL == name) {
        // anonymous, ignore.
        return;
    }
    if (strcmp(name, target_struct)) {
        // bye
        return;
    }

    dump_struct(type, name, 0);
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
            dump_struct(n->type, ORIG_TYPE_NAME(n->type), 0);
        }
    }

    fprintf(output_file, "# dumped structs:\n");

    struct list *iter = dumped_structs.list.next;
    while (NULL != iter) {
        struct dumped_list *n = container_of(iter, struct dumped_list, list);

        fprintf(output_file, "# %s\n", n->name);
        iter = iter->next;
    }

    fflush(output_file);
}

int plugin_init(struct plugin_name_args *plugin_info, struct plugin_gcc_version *version)
{
    const char *output = NULL;

    for (int i = 0; i < plugin_info->argc; ++i) {
        if (0 == strcmp(plugin_info->argv[i].key, "output")) {
            output = plugin_info->argv[i].value;
        }
        if (0 == strcmp(plugin_info->argv[i].key, "struct")) {
            target_struct = xstrdup(plugin_info->argv[i].value);
        }
    }

    if (NULL == output) {
        fprintf(stderr, "structlayout plugin: missing parameter: -fplugin-arg-struct_layout-output=<output>\n");
        exit(EXIT_FAILURE);
    }

    if (NULL == target_struct) {
        fprintf(stderr, "structlayout plugin: missing parameter: -fplugin-arg-struct_layout-struct=<struct>\n");
        exit(EXIT_FAILURE);
    }

    output_file = fopen(output, "w");
    if (NULL == output_file) {
        perror(output);
        exit(EXIT_FAILURE);
    }

    register_callback(plugin_info->base_name, PLUGIN_FINISH_TYPE, plugin_finish_type, NULL);
    register_callback(plugin_info->base_name, PLUGIN_FINISH, plugin_finish, NULL);

    return 0;
}
