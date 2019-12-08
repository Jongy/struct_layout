from python.fields import Scalar, Bitfield, Function, Void, Pointer, StructField, Array

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


def _as_signed(n, bits):
    if n > (1 << (bits - 1)) - 1:
        n -= (1 << bits)
    return n


def _as_unsigned(n, bits):
    if n < 0:
        n += (1 << bits)
    return n


def _make_addr(base, offset, bitfield=False):
    return base + offset // 8


def _lookup_struct(s):
    if isinstance(s, str):
        return STRUCTS[s]
    return s


def _access_addr(field, base, offset):
    if 0 == base:
        raise ValueError("NULL deref! offset {!r} type {!r}".format(offset, field))
    return _make_addr(base, offset)


def _read_accessor(field, base, offset):
    addr = _access_addr(field, base, offset)

    if isinstance(field, Scalar):
        value = ACCESSORS[field.total_size](addr)
        if field.signed:
            value = _as_signed(value, field.total_size)
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
            return StructPtr(_lookup_struct(pt.type), ptr)
        elif isinstance(pt, Array):
            return ArrayPtr(ptr, pt.num_elem, pt.elem_type)
        else:
            return Ptr(pt, ptr)
    elif isinstance(field, StructField):
        return StructPtr(_lookup_struct(field.type), addr)
    elif isinstance(field, Array):
        return ArrayPtr(addr, field.num_elem, field.elem_type)
    else:
        raise NotImplementedError("_read_accessor for {!r}".format(field))


def _check_value_overflow(value, bits, signed):
    if signed:
        if not -(1 << bits) <= value < (1 << (bits - 1)):
            raise ValueError("{!r} doesn't fit in signed {}-bits!".format(value, bits))
    else:
        if not (0 <= value < (1 << bits)):
            raise ValueError("{!r} doesn't fit in unsigned {}-bits!".format(value, bits))


def _write_accessor(field, base, offset, value):
    addr = _access_addr(field, base, offset)

    if isinstance(field, Scalar):
        _check_value_overflow(value, field.total_size, field.signed)
        if field.signed:
            value = _as_unsigned(value, field.total_size)
        ACCESSORS[field.total_size](addr, value)
    elif isinstance(field, Bitfield):
        # TODO
        return NotImplemented
    elif isinstance(field, Pointer):
        _check_value_overflow(value, field.total_size, False)
        ACCESSORS[field.total_size](addr, value)
    # give more indicative errors for struct / array
    elif isinstance(field, StructField):
        # could be done with a memcpy though.
        raise TypeError("Can't set a struct! Please set its fields instead")
    elif isinstance(field, Array):
        raise TypeError("Can't set an array! Please set its elements instead")
    else:
        raise NotImplementedError("_write_accessor for {!r}".format(field))


class Ptr(object):
    def __init__(self, type_, ptr):
        self._type = type_
        self._ptr = ptr

    def p(self):
        return _read_accessor(self._type, self._ptr, 0)

    def __getitem__(self, key):
        return _read_accessor(self._type, self._ptr, key * self._type.total_size)

    def __setitem__(self, key, value):
        return _write_accessor(self._type, self._ptr, key * self._type.total_size, value)

    def __eq__(self, other):
        if not isinstance(other, Ptr):
            return NotImplemented

        return self._type == other._type and self._ptr == other._ptr

    def __repr__(self):
        return "Ptr({!r}, 0x{:x})".format(self._type, self._ptr)


class ArrayPtr(object):
    def __init__(self, base, num_elem, elem_type):
        self._base = base
        self._num_elem = num_elem or None
        self._elem_type = elem_type

    def __check_index(self, key):
        if self._num_elem and not (0 <= key < self._num_elem):
            raise ValueError("Index {!r} not in range: 0 - {!r}".format(key, self._num_elem - 1))

    def __getitem__(self, key):
        self.__check_index(key)
        return _read_accessor(self._elem_type, self._base, key * self._elem_type.total_size)

    def __setitem__(self, key, value):
        self.__check_index(key)
        return _write_accessor(self._elem_type, self._base, key * self._elem_type.total_size, value)

    def __eq__(self, other):
        if not isinstance(other, ArrayPtr):
            return NotImplemented

        return (self._base == other._base and self._num_elem == other._num_elem and
                self._elem_type == other._elem_type)

    def __len__(self):
        return self._num_elem

    def __repr__(self):
        return "ArrayPtr(0x{:x}, {!r}, {!r})".format(self._base, self._num_elem, self._elem_type)


def _get_sp_struct(sp):
    return super(StructPtr, sp).__getattribute__("____struct")


def _get_sp_ptr(sp):
    return super(StructPtr, sp).__getattribute__("____ptr")


def _get_struct_field(sp, attr):
    struct = _get_sp_struct(sp)

    try:
        return struct.fields[attr]
    except KeyError:
        raise KeyError("No field named {!r} in {!r}".format(attr, struct.name))


class StructPtr(object):
    """
    this class is pure python hell
    """

    def __init__(self, struct, ptr):
        super(StructPtr, self).__setattr__("____struct", struct)
        super(StructPtr, self).__setattr__("____ptr", ptr)

    def __getattr__(self, attr):
        f = _get_struct_field(self, attr)
        return _read_accessor(f[1], _get_sp_ptr(self), f[0])

    def __setattr__(self, attr, value):
        f = _get_struct_field(self, attr)
        return _write_accessor(f[1], _get_sp_ptr(self), f[0], value)

    def __dir__(self):
        # TODO fix this, doesn't really work
        return list(_get_sp_struct(self).fields.keys())

    def __eq__(self, other):
        if not isinstance(other, StructPtr):
            return NotImplemented

        return (_get_sp_struct(self) == _get_sp_struct(other)
                and _get_sp_ptr(self) == _get_sp_ptr(other))

    def __repr__(self):
        return "StructPtr(0x{:x}, {!r})".format(_get_sp_ptr(self), _get_sp_struct(self))


def partial_struct(struct):
    def p(ptr):
        return StructPtr(_lookup_struct(struct), ptr)
    return p


def sizeof(struct, field_name=None):
    if field_name:
        if isinstance(struct.fields[field_name][1], Bitfield):
            raise TypeError("Can't take the size of bit fields!")

        n = struct.fields[field_name][1].total_size
    else:
        n = struct.total_size

    return n // 8


def offsetof(struct, field_name):
    if isinstance(struct.fields[field_name][1], Bitfield):
        raise TypeError("Can't take the offset of bit fields!")

    return struct.fields[field_name][0] // 8
