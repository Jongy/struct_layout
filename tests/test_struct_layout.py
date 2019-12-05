import os.path
import subprocess
import tempfile

from ..fields import (Scalar, Bitfield, Pointer, Array, Void, StructField, UnionField,
                      Struct, Union)


STRUCT_LAYOUT_SO = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "struct_layout.so"))


def run_gcc(code_path, output_path, struct_name):
    subprocess.check_call(["gcc", "-fplugin={}".format(STRUCT_LAYOUT_SO),
                           "-fplugin-arg-struct_layout-output={}".format(output_path),
                           "-fplugin-arg-struct_layout-struct={}".format(struct_name),
                           "-c", "-o", "/dev/null", "-x", "c", code_path])


def dump_struct_layout(struct_code, struct_name):
    with tempfile.NamedTemporaryFile() as tf1, tempfile.NamedTemporaryFile("r") as tf2:
        tf1.write(struct_code.encode("ascii"))
        tf1.flush()

        run_gcc(tf1.name, tf2.name, struct_name)

        load_globals = {"Scalar": Scalar, "Bitfield": Bitfield, "Void": Void,
                        "StructField": StructField, "UnionField": UnionField,
                        "Pointer": Pointer, "Array": Array,
                        "Struct": Struct, "Union": Union}
        struct_def = tf2.read()
        print(struct_def)  # for debugging
        # hehe :(
        exec(struct_def, load_globals)
        return load_globals


def test_struct_basic():
    s = dump_struct_layout("struct x { int y; char z; };", "x")["x"].fields
    assert len(s.keys()) == 2
    assert s["y"] == (0, Scalar(32, "int"))
    assert s["z"] == (32, Scalar(8, "char"))


def test_struct_pointer():
    s = dump_struct_layout("struct x { void *p; void **h; const int ***z; };", "x")["x"].fields
    assert len(s.keys()) == 3
    assert s["p"] == (0, Pointer(64, Void()))
    assert s["h"] == (64, Pointer(64, Pointer(64, Void())))
    assert s["z"] == (128, Pointer(64, Pointer(64, Pointer(64, Scalar(32, "int")))))


def test_struct_array():
    s = dump_struct_layout("struct x { int arr[5]; void *p[2]; };", "x")["x"].fields
    assert len(s.keys()) == 2
    assert s["arr"] == (0, Array(5 * 32, 5, Scalar(32, "int")))
    assert s["p"] == (5 * 32 + 32, Array(2 * 64, 2, Pointer(64, Void())))


def test_struct_array_two_dimensions():
    s = dump_struct_layout("struct x { int arr[5][2]; };", "x")["x"].fields
    assert len(s.keys()) == 1
    assert s["arr"] == (0, Array(5 * 2 * 32, 5, Array(2 * 32, 2, Scalar(32, "int"))))


def test_struct_struct():
    s = dump_struct_layout("struct a { int x; }; struct b { struct a aa; int xx; };", "b")["b"].fields
    assert len(s.keys()) == 2
    assert s["aa"] == (0, StructField(32, "a"))
    assert s["xx"] == (32, Scalar(32, "int"))


def test_struct_union():
    decls = dump_struct_layout("union u { int x; char c; long l; }; struct c { union u u; };", "c")

    c = decls["c"].fields
    assert len(c.keys()) == 1
    assert c["u"] == (0, UnionField(64, "u"))

    u = decls["u"]
    assert u.total_size == 64
    u = u.fields
    assert len(u.keys()) == 3
    assert u["x"] == (0, Scalar(32, "int"))
    assert u["c"] == (0, Scalar(8, "char"))
    assert u["l"] == (0, Scalar(64, "long int"))


def test_struct_anonymous_union():
    s = dump_struct_layout("struct c { union { int x; float f; }; };", "c")["c"].fields
    assert len(s.keys()) == 1
    assert s["(anonymous union)"] == (0, UnionField(32, ""))


def test_struct_recursive_dump():
    decls = dump_struct_layout("struct a { int x; }; struct b { struct a a; }; ", "b")

    b = decls["b"].fields
    assert len(b.keys()) == 1
    assert b["a"] == (0, StructField(32, "a"))

    a = decls[b["a"][1].type].fields
    assert len(a.keys()) == 1
    assert a["x"] == (0, Scalar(32, "int"))


def test_struct_dump_only_necessary():
    decls = dump_struct_layout("struct a { int x; }; struct b { int y; };", "b")

    b = decls["b"].fields
    assert len(b.keys()) == 1
    assert b["y"] == (0, Scalar(32, "int"))

    assert "a" not in decls


def test_struct_bitfields():
    x = dump_struct_layout("struct x { int bf1: 3; int bf2: 1; int n; int bf3: 29; };", "x")["x"].fields

    assert len(x.keys()) == 4
    assert x["bf1"] == (0, Bitfield(3))
    assert x["bf2"] == (3, Bitfield(1))
    assert x["n"] == (32, Scalar(32, "int"))
    assert x["bf3"] == (64, Bitfield(29))
