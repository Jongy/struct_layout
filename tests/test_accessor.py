import struct
import pytest

from .test_struct_layout import dump_struct_layout

from python.fields import Scalar, Function, Void
from python.struct_accessor import (partial_struct, set_accessors, update_structs, Ptr, StructPtr,
                                    ArrayPtr, sizeof, offsetof)


MEM_BASE = 0x10000


def make_accessors(data):
    def p8(p, v=None):
        if v is not None:
            print("u8 @ 0x{:x} = {:x}".format(p, v))
            data[p-MEM_BASE:p-MEM_BASE+1] = struct.pack(">B", v)
        else:
            print("u8 @ 0x{:x}".format(p))
            return struct.unpack_from(">B", data, p - MEM_BASE)[0]

    def p16(p, v=None):
        if v is not None:
            print("u16 @ 0x{:x} = {:x}".format(p, v))
            data[p-MEM_BASE:p-MEM_BASE+2] = struct.pack(">H", v)
        else:
            print("u16 @ 0x{:x}".format(p))
            return struct.unpack_from(">H", data, p - MEM_BASE)[0]

    def p32(p, v=None):
        if v is not None:
            print("u32 @ 0x{:x} = {:x}".format(p, v))
            data[p-MEM_BASE:p-MEM_BASE+4] = struct.pack(">L", v)
        else:
            print("u32 @ 0x{:x}".format(p))
            return struct.unpack_from(">L", data, p - MEM_BASE)[0]

    def p64(p, v=None):
        if v is not None:
            print("u64 @ 0x{:x} = {:x}".format(p, v))
            data[p-MEM_BASE:p-MEM_BASE+8] = struct.pack(">Q", v)
        else:
            print("u64 @ 0x{:x}".format(p))
            return struct.unpack_from(">Q", data, p - MEM_BASE)[0]

    return p8, p16, p32, p64


def set_memory_struct(fmt, *args):
    data = bytearray(struct.pack(fmt, *args))
    set_accessors(*make_accessors(data))
    return data


def test_accessor_scalar():
    set_memory_struct(">LBBh", 12345678, 5, 8, -4387)

    s = partial_struct(dump_struct_layout(
        "struct x { int n; char a; char b; short sign; };", "x")["x"])(MEM_BASE)

    assert s.n == 12345678
    assert s.a == 5
    assert s.b == 8
    assert s.sign == -4387


@pytest.mark.skip("TODO")
def test_accessor_bitfield():
    # not implemented in accessors yet
    pass


def test_accessor_array_scalar():
    set_memory_struct(">LHHHH", 1, 0, 1, 2, 3)

    s = partial_struct(dump_struct_layout("struct x { int n; short arr[4]; };", "x")["x"])(MEM_BASE)

    assert s.arr[0] == 0
    assert s.arr[1] == 1
    assert s.arr[2] == 2
    assert s.arr[3] == 3


def test_accessor_array_struct():
    set_memory_struct(">QLHBxLHBxLHBx", 0, 3, 2, 1, 30, 20, 10, 300, 200, 100)

    s = partial_struct(dump_struct_layout(
        "struct x { long n; struct { int n; short s; char c; } a[3]; };", "x")["x"])(MEM_BASE)

    for i in range(0, 3):
        assert s.a[i].n == 3 * 10 ** i
        assert s.a[i].s == 2 * 10 ** i
        assert s.a[i].c == 1 * 10 ** i


def test_accessor_pointer():
    set_memory_struct(">QL", MEM_BASE + 8, 5)

    s = partial_struct(dump_struct_layout("struct x { int *ptr; int x; };", "x")["x"])(MEM_BASE)

    assert s.x == 5
    assert s.ptr == Ptr(Scalar(32, "int", True), MEM_BASE + 8)
    assert s.ptr.p() == 5


def test_accessor_invalid_pointer_deref():
    set_memory_struct(">QQQ", 4, 8, 0)

    s = partial_struct(dump_struct_layout(
        "struct x { int (*fptr)(void); void *void_ptr; void *nullptr; };", "x")["x"])(MEM_BASE)

    assert s.fptr == Ptr(Function(), 4)
    with pytest.raises(TypeError):
        # can't deref a function pointer
        s.fptr.p()

    assert s.void_ptr == Ptr(Void(), 8)
    with pytest.raises(TypeError):
        # can't deref a void pointer
        s.void_ptr.p()

    assert s.nullptr == Ptr(Void(), 0)
    with pytest.raises(ValueError):
        # can't deref a null pointer
        s.nullptr.p()


def test_accessor_pointer_to_array():
    set_memory_struct(">Q3L", MEM_BASE + 8, 0, 1, 2)

    s = partial_struct(dump_struct_layout("struct x { int (*aptr)[3]; };", "x")["x"])(MEM_BASE)

    assert s.aptr == ArrayPtr(MEM_BASE + 8, 3, Scalar(32, "int", True))
    assert s.aptr[0] == 0
    assert s.aptr[1] == 1
    assert s.aptr[2] == 2


def test_accessor_pointer_struct():
    set_memory_struct(">QLB3x", MEM_BASE + 8, 555, 2)

    structs = dump_struct_layout("struct y { int n; char c; }; struct x { struct y *yptr; };", None)
    update_structs(structs)

    s = StructPtr(structs["x"], MEM_BASE)

    assert s.yptr == StructPtr(structs["y"], MEM_BASE + 8)
    assert s.yptr.n == 555
    assert s.yptr.c == 2


def test_accessor_set_scalar():
    set_memory_struct(">Bxh", 0, 0)

    s = partial_struct(dump_struct_layout(
        "struct x { unsigned char a; short sign; };", "x")["x"])(MEM_BASE)

    assert s.a == 0
    assert s.sign == 0

    s.a = 200  # unsigned
    s.sign = -3254  # signed

    assert s.a == 200
    assert s.sign == -3254


def test_accessor_set_array():
    mem = set_memory_struct(">BBBBB", 0, 0, 0, 0, 0)
    print(mem)
    s = partial_struct(dump_struct_layout("struct x { char arr[5] };", "x")["x"])(MEM_BASE)

    for i in range(0, len(s.arr)):
        s.arr[i] = i + 1

    assert mem == b"\x01\x02\x03\x04\x05"


def test_accessor_set_pointer():
    set_memory_struct(">QL", 0, 5)

    s = partial_struct(dump_struct_layout("struct x { int *ptr; int x; };", "x")["x"])(MEM_BASE)

    assert s.ptr == Ptr(Scalar(32, "int", True), 0)

    s.ptr = MEM_BASE + 8

    assert s.ptr[0] == s.x


def test_accessor_set_invalid():
    set_memory_struct("")

    s = partial_struct(dump_struct_layout(
        "struct x { struct { int a; } b; int arr[5]; };", "x")["x"])(MEM_BASE)

    with pytest.raises(TypeError):
        s.b = 5

    with pytest.raises(TypeError):
        s.arr = 5


def test_accessor_sizeof():
    x = dump_struct_layout("struct x { int x; char c; int arr[3]; void *p; };", "x")["x"]

    assert sizeof(x, "x") == 4
    assert sizeof(x, "c") == 1
    assert sizeof(x, "arr") == 12
    assert sizeof(x, "p") == 8

    # padding, twice :(
    assert sizeof(x) == 4 + 1 + 3 + 12 + 4 + 8


def test_accessor_offsetof():
    x = dump_struct_layout("struct x { int x; char c; int arr[3]; void *p; };", "x")["x"]

    assert offsetof(x, "x") == 0
    assert offsetof(x, "c") == 4
    assert offsetof(x, "arr") == 8
    assert offsetof(x, "p") == 24
