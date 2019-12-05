import os.path
import subprocess
import tempfile

from ..fields import Type, Basic, Pointer, Array


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

        load_globals = {"Basic": Basic, "Pointer": Pointer, "Array": Array}
        struct_def = tf2.read()
        print(struct_def)  # for debugging
        # hehe :(
        exec(struct_def, load_globals)
        return load_globals[struct_name]


def test_struct_basic():
    s = dump_struct_layout("struct x { int y; char z; };", "x")
    assert len(s.keys()) == 2
    assert s["y"] == (0, Basic(32, "int"))
    assert s["z"] == (32, Basic(8, "char"))


def test_struct_pointer():
    s = dump_struct_layout("struct x { void *p; void **h; const int ***z; };", "x")
    assert len(s.keys()) == 3
    assert s["p"] == (0, Pointer(64, Basic(0, "void")))
    assert s["h"] == (64, Pointer(64, Pointer(64, Basic(0, "void"))))
    assert s["z"] == (128, Pointer(64, Pointer(64, Pointer(64, Basic(32, "int")))))


def test_struct_array():
    s = dump_struct_layout("struct x { int arr[5]; void *p[2]; };", "x")
    assert len(s.keys()) == 2
    assert s["arr"] == (0, Array(5 * 32, 5, Basic(32, "int")))
    assert s["p"] == (5 * 32 + 32, Array(2 * 64, 2, Pointer(64, Basic(0, "void"))))
