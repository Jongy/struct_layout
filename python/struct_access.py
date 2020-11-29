# MP imports this file w/o the package. make it work for both.
try:
    from python.fields import Scalar, Bitfield, Function, Void, Pointer, StructField, Array, Struct
except ImportError:
    from fields import Scalar, Bitfield, Function, Void, Pointer, StructField, Array, Struct

# I know it's weird to have such globals, but wrapping them in an object will make
# all the other classes cumbersome with the need to pass it around.
# anyway there's no reason we'll ever need more instances of these.
ACCESSORS = {}
STRUCTS = {}


def cast_struct(struct, ptr):
    return StructPtr(struct, ptr)


Struct.__call__ = cast_struct


# pycpy - memcpy from python objects
def set_accessors(pycpy, p8, p16, p32, p64):
    ACCESSORS[0] = pycpy
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


def _make_addr(base, offset):
    return base + offset // 8


def lookup_struct(s):
    if isinstance(s, str):
        return STRUCTS[s]
    assert isinstance(s, Struct)
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
        # attempt to use the smallest access size that's
        # 1. aligned (to native size)
        # 2. covers the bitfield size
        if offset % 8 + field.total_size <= 8:
            size = 8
        elif offset % 16 + field.total_size <= 16:
            size = 16
        elif offset % 32 + field.total_size <= 32:
            size = 32
        elif offset % 64 + field.total_size <= 64:
            size = 64
        else:
            raise NotImplementedError("cross-word bitfield! base {:#x} offset {} size {}".format(
                                      base, offset, field.total_size))

        addr = _access_addr(field, base, (offset // size) * size)
        val = ACCESSORS[size](addr)

        bitfield_offset = offset - (addr - base) * 8
        shift = size - (bitfield_offset + field.total_size)
        val = (val >> shift) & ((1 << field.total_size) - 1)
        if field.signed:
            val = _as_signed(val, field.total_size)
        return val

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
        raise NotImplementedError("bitfield write")
    elif isinstance(field, Pointer):
        _check_value_overflow(value, field.total_size, False)
        ACCESSORS[field.total_size](addr, value)
    # give more indicative errors for struct / array
    elif isinstance(field, StructField):
        raise TypeError("Can't set a struct! Please set its fields instead")
    elif isinstance(field, Array):
        if isinstance(value, (str, bytes)):
            if isinstance(value, str):
                value = value.encode("ascii")
            if len(value) > field.total_size // 8:
                raise ValueError("Buffer overflow!")
            ACCESSORS[0](addr, value, len(value))
        else:
            raise TypeError("Can't set an array! Please set its elements instead")
    else:
        raise NotImplementedError("_write_accessor for {!r}".format(field))


class Ptr(object):
    def __init__(self, type_, ptr):
        self._type = type_
        self.___ptr = ptr

    def p(self):
        return _read_accessor(self._type, self.___ptr, 0)

    def __getitem__(self, key):
        return _read_accessor(self._type, self.___ptr, key * self._type.total_size)

    def __setitem__(self, key, value):
        return _write_accessor(self._type, self.___ptr, key * self._type.total_size, value)

    def __eq__(self, other):
        if not isinstance(other, Ptr):
            return NotImplemented

        return self._type == other._type and self.___ptr == other.___ptr

    def __repr__(self):
        return "Ptr({!r}, 0x{:x})".format(self._type, self.___ptr)

    def __int__(self):
        return self.___ptr

    def __add__(self, other):
        if not isinstance(other, int):
            return NotImplemented

        return self.___ptr + other


class ArrayPtr(object):
    CHAR_TYPE = Scalar(8, "char", True)

    def __init__(self, base, num_elem, elem_type):
        self.___ptr = base
        self._num_elem = num_elem or None
        self._elem_type = elem_type

    def __check_index(self, key):
        if self._num_elem and not (0 <= key < self._num_elem):
            raise IndexError("Index {!r} not in range: 0 - {!r}".format(key, self._num_elem - 1))

    def __getitem__(self, key):
        self.__check_index(key)
        return _read_accessor(self._elem_type, self.___ptr, key * self._elem_type.total_size)

    def __setitem__(self, key, value):
        self.__check_index(key)
        return _write_accessor(self._elem_type, self.___ptr, key * self._elem_type.total_size, value)

    def __eq__(self, other):
        if not isinstance(other, ArrayPtr):
            return NotImplemented

        return (self.___ptr == other.___ptr and self._num_elem == other._num_elem and
                self._elem_type == other._elem_type)

    def __len__(self):
        return self._num_elem

    def __repr__(self):
        return "ArrayPtr(0x{:x}, {!r}, {!r})".format(self.___ptr, self._num_elem, self._elem_type)

    def __int__(self):
        return self.___ptr

    def read(self, n=None):
        n = n if n is not None else self._num_elem
        items = []
        for i in range(n):
            items.append(self[i])

        if self._elem_type == ArrayPtr.CHAR_TYPE:
            # special case: if type is "char", convert to string
            s = "".join(map(chr, items))
            if s.find('\x00') != -1:
                s = s[:s.find('\x00')]
            return s
        else:
            return items


def _get_sp_struct(sp):
    return sp.____struct


def _get_sp_ptr(sp):
    return sp.____ptr


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
        object.__setattr__(self, "____struct", struct)
        object.__setattr__(self, "____ptr", ptr)

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

    def __int__(self):
        return _get_sp_ptr(self)

    def __repr__(self):
        return "StructPtr(0x{:x}, {!r})".format(_get_sp_ptr(self), _get_sp_struct(self))


def to_int(p):
    if isinstance(p, int):
        return p

    n = getattr(p, "____ptr", None)
    if n is not None:
        return n

    raise ValueError("Can't handle object of type {}".format(type(p)))


def partial_struct(struct):
    struct = lookup_struct(struct)

    def p(ptr):
        return StructPtr(struct, ptr)

    return p


def sizeof(struct, field_name=None):
    struct = lookup_struct(struct)

    if field_name:
        if isinstance(struct.fields[field_name][1], Bitfield):
            raise TypeError("Can't take the size of bit fields!")

        n = struct.fields[field_name][1].total_size
    else:
        n = struct.total_size

    return n // 8


def offsetof(struct, field_name):
    struct = lookup_struct(struct)

    if isinstance(struct.fields[field_name][1], Bitfield):
        raise TypeError("Can't take the offset of bit fields!")

    return struct.fields[field_name][0] // 8


def container_of(ptr, struct, field_name):
    struct = lookup_struct(struct)
    return StructPtr(struct, to_int(ptr) - offsetof(struct, field_name))


def is_struct_type(sp, struct):
    return sp.____struct == struct


def dump_struct(sp, levels=1, indent=0):

    def _print_indented(s):
        print(' ' * indent + s)

    def _print_field_simple(field, val):
        _print_indented(field + ' = ' + str(val))

    fields = sp.____struct.fields
    ordered_fields = sorted(fields.keys(), key=lambda k: fields[k][0])

    for field in ordered_fields:
        try:
            val = getattr(sp, field)
        except Exception as e:
            print(' ' * indent + field + ' : ' + repr(e))
            continue

        # is it a struct?
        if (isinstance(val, StructPtr)
            # and not pointing to same type (probably a list of some sort...)
            and not is_struct_type(val, fields[field][1])
            # and we should go deeper
            and levels > 0
            # and not NULL
           and val.____ptr != 0):

            _print_field_simple(field, val)
            dump_struct(val, levels=levels - 1, indent=indent + 4)
        elif isinstance(fields[field][1], Scalar):
            _print_indented(fields[field][1].type + ' ' + field + ' = ' + str(val) + ' ' + hex(val))
        else:
            _print_field_simple(field, val)
