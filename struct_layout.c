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

static void debug_tree_helper(tree t, const char *msg)
{
#ifndef NDEBUG
    printf("dumping tree: '%s'\n", msg);
    debug_tree(t);
    printf("\n\n");
    fflush(stdout);
#endif
}

struct name_list {
    struct name_list *next;
    char name[0];
};

static struct name_list dumped_structs;

static bool was_dumped(const char *name)
{
    const struct name_list *iter = dumped_structs.next;

    while (NULL != iter) {
        if (0 == strcmp(name, iter->name)) {
            return true;
        }
        iter = iter->next;
    }

    return false;
}

static void add_dumped(const char *name)
{
    const size_t len = strlen(name) + 1;
    struct name_list *n = (struct name_list*)xmalloc(sizeof(*n) + len);
    n->next = NULL;
    memcpy(n->name, name, len);

    struct name_list *iter = &dumped_structs;

    while (NULL != iter->next) {
        iter = iter->next;
    }

    iter->next = n;
}

// types that don't have another type beneath them.
static bool is_basic_type(tree type)
{
    switch (TREE_CODE(type)) {
    case INTEGER_TYPE:
    case BOOLEAN_TYPE:
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
    const size_t elem_size = TREE_INT_CST_LOW(TYPE_SIZE_UNIT(TREE_TYPE(field_type)));
    const size_t num_elem = TREE_INT_CST_LOW(TYPE_SIZE_UNIT(field_type)) / elem_size;

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

static void print_struct_ending(bool multi_part)
{
    fprintf(output_file, multi_part ? "})\n" : "}\n");
}

static void dump_struct(const_tree type, const char *name)
{
    if (was_dumped(name)) {
        return;
    }
    // add it immediately, so if we find any back references into current struct, we don't
    // dump it again.
    add_dumped(name);

    fprintf(output_file, "%s = {\n", name);
    bool multi_part = false;

    for (tree field = TYPE_FIELDS(type); field; field = TREE_CHAIN(field)) {
        gcc_assert(TREE_CODE(field) == FIELD_DECL);

        debug_tree_helper(field, "field");

        tree field_type = TREE_TYPE(field);

        // field name
        const char *field_name;
        const_tree decl = DECL_NAME(field);
        bool anonymous = false;
        if (NULL != decl) {
            field_name = IDENTIFIER_POINTER(decl);
        } else {
            // shouldn't be NULL, only allowed for anonymous unions.
            gcc_assert(UNION_TYPE == TREE_CODE(field_type));
            field_name = "(anonymous union)";
            anonymous = true;
        }

        // is it another struct / union?
        if (TREE_CODE(field_type) == RECORD_TYPE || (TREE_CODE(field_type) == UNION_TYPE && !anonymous)) {
            // dump it as well, if not anonymous.
            print_struct_ending(multi_part);
            dump_struct(field_type, ORIG_TYPE_NAME(field_type));
            fprintf(output_file, "%s.update({\n", name);
            multi_part = true; // from now on.
        }

        // field offset
        tree t_offset = DECL_FIELD_OFFSET(field);
        gcc_assert(TREE_CODE(t_offset) == INTEGER_CST && TREE_CONSTANT(t_offset));
        size_t offset = TREE_INT_CST_LOW(t_offset) * 8;
        // add bit offset. there's an explanation about why it's required, see macro declaration in tree.h
        tree t_bit_offset = DECL_FIELD_BIT_OFFSET(field);
        gcc_assert(TREE_CODE(t_bit_offset) == INTEGER_CST && TREE_CONSTANT(t_bit_offset));
        offset += TREE_INT_CST_LOW(t_bit_offset);

        fprintf(output_file, "    '%s': (%zu, ", field_name, offset);

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

        // TODO handle anonymous types better.
        // I think it in this case it'd be the best if we just print the type directly,
        // instead of its name.
        const char *field_type_name = "";
        tree type_name = TYPE_IDENTIFIER(field_type);
        if (NULL != type_name) {
            field_type_name = IDENTIFIER_POINTER(type_name);
        }

        const size_t field_size = get_field_size(field_type);

        if (TREE_CODE(field_type) == VOID_TYPE) {
            fprintf(output_file, "Void()");
        } else {
            const char *field_class;
            if (TREE_CODE(field_type) == FUNCTION_TYPE) {
                field_class = "Function";
            } else if (TREE_CODE(field_type) == RECORD_TYPE) {
                field_class = "Struct";
            } else if (TREE_CODE(field_type) == UNION_TYPE) {
                field_class = "Union";
            } else {
                field_class = "Basic";
            }

            fprintf(output_file, "%s(%zu, '%s')", field_class, field_size, field_type_name);
        }

        for (size_t i = 0; i < type_depth; ++i) {
            fprintf(output_file, ")");
        }

        fprintf(output_file, "),\n");
    }

    print_struct_ending(multi_part);

    fflush(output_file);
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

    dump_struct(type, name);

    // technically, by this point we're done. any struct / type referenced by our target struct
    // was already dumped as well.

    fprintf(output_file, "# dumped structs:\n");

    struct name_list *iter = dumped_structs.next;
    while (NULL != iter) {
        fprintf(output_file, "# %s\n", iter->name);
        iter = iter->next;
    }
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

    return 0;
}
