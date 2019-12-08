from .fields import *

# I know it's weird to have such globals, but wrapping them in an object will make
# all the other classes cumbersome with the need to pass it around.
# anyway there's no reason we'll ever need more instances of these.
ACCESSORS = {}
STRUCTS = {}


def set_accessors(p8, p16, p32, p64):
    ACCESSORS[8] = p8
    ACCESSORS[16] = p16
    ACCESSORS[32] = p32
    ACCESSORS[64] = p64


def update_structs(structs):
    STRUCTS.update(structs)


def as_signed(n, bits):
    if n >= (1 << (bits - 1)) - 1:
        n -= (1 << bits)
    return n


def make_addr(base, offset, bitfield=False):
    return base + offset // 8


def lookup_struct(s):
    if isinstance(s, str):
        return STRUCTS[s]
    return s


def accessor(field, base, offset):
    if 0 == base:
        raise ValueError("NULL deref! offset {!r} type {!r}".format(offset, field))
    addr = make_addr(base, offset)

    if isinstance(field, Scalar):
        value = ACCESSORS[field.total_size](addr)
        if field.signed:
            value = as_signed(value, field.total_size)
        return value

    elif isinstance(field, Bitfield):
        # TODO
        return NotImplemented
    elif isinstance(field, Function):
        raise TypeError("Attempt to deref a function pointer!")
    elif isinstance(field, Void):
        raise TypeError("Attempt to deref a void pointer!")
    elif isinstance(field, Pointer):
        ptr = ACCESSORS[field.total_size](addr)
        pt = field.pointed_type
        if isinstance(pt, StructField):
            return StructPtr(lookup_struct(pt.type), ptr)
        elif isinstance(pt, Array):
            return ArrayPtr(ptr, pt.num_elem, pt.elem_type)
        else:
            return Ptr(pt, ptr)
    elif isinstance(field, StructField):
        return StructPtr(lookup_struct(field.type), addr)
    elif isinstance(field, Array):
        return ArrayPtr(addr, field.num_elem, field.elem_type)
    else:
        raise NotImplementedError("accessor for {!r}".format(field))


class Ptr(object):
    def __init__(self, type_, ptr):
        self._type = type_
        self._ptr = ptr

    def p(self):
        return accessor(self._type, self._ptr, 0)

    def __getitem__(self, key):
        return accessor(self._type, self._ptr, key * self._type.total_size)

    def __eq__(self, other):
        if not isinstance(other, Ptr):
            return NotImplemented

        return self._type == other._type and self._ptr == other._ptr

    def __repr__(self):
        return "Ptr({!r}, 0x{:x})".format(self._type, self._ptr)


class ArrayPtr(object):
    def __init__(self, base, num_elem, elem_type):
        self._base = base
        self._num_elem = num_elem
        self._elem_type = elem_type

    def __getitem__(self, key):
        if self._num_elem and not (0 <= key < self._num_elem):
            raise ValueError("Index {!r} not in range: 0 - {!r}".format(key, self._num_elem - 1))

        return accessor(self._elem_type, self._base, key * self._elem_type.total_size)

    def __eq__(self, other):
        if not isinstance(other, ArrayPtr):
            return NotImplemented

        return (self._base == other._base and self._num_elem == other._num_elem and
                self._elem_type == other._elem_type)

    def __repr__(self):
        return "ArrayPtr(0x{:x}, {!r}, {!r})".format(self._base, self._num_elem, self._elem_type)


class StructPtr(object):
    def __init__(self, struct, ptr):
        self.____struct = struct
        self.____ptr = ptr

    def __getattr__(self, attr):
        try:
            f = self.____struct.fields[attr]
        except KeyError:
            raise KeyError("No field named {!r} in {!r}"
                           .format(attr, self.____struct.name))

        return accessor(f[1], self.____ptr, f[0])

    def __dir__(self):
        # TODO fix this, doesn't really work
        return list(self.____struct.fields.keys())

    def __eq__(self, other):
        if not isinstance(other, StructPtr):
            return NotImplemented

        return self.____struct == other.____struct and self.____ptr == other.____ptr

    def __repr__(self):
        return "StructPtr(0x{:x}, {!r})".format(self.____ptr, self.____struct)


def partial_struct(struct):
    def p(ptr):
        return StructPtr(lookup_struct(struct), ptr)
    return p
