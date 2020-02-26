class Type(object):
    def __init__(self, total_size):
        self.total_size = total_size

    def __eq__(self, other):
        if not isinstance(other, Type):
            return NotImplemented

        return self.total_size == other.total_size


class Void(Type):
    def __init__(self):
        super(Void, self).__init__(0)

    def __eq__(self, other):
        if not isinstance(other, Void):
            return NotImplemented

        return super(Void, self).__eq__(other)

    def __repr__(self):
        return "Void()"


class Bitfield(Type):
    def __init__(self, total_size, signed):
        super(Bitfield, self).__init__(total_size)
        self.signed = signed

    def __eq__(self, other):
        if not isinstance(other, Bitfield):
            return NotImplemented

        return self.signed == other.signed and super(Bitfield, self).__eq__(other)

    def __repr__(self):
        return "Bitfield({!r}, {})".format(self.total_size, self.signed)


class Scalar(Type):
    def __init__(self, total_size, type_, signed):
        super(Scalar, self).__init__(total_size)
        self.type = type_
        self.signed = signed

    def __eq__(self, other):
        print(self, other)
        if not isinstance(other, Scalar):
            return NotImplemented

        return (self.type == other.type and self.signed == other.signed
                and super(Scalar, self).__eq__(other))

    def __repr__(self):
        return "Scalar({!r}, {!r}, {!r})".format(self.total_size, self.type, self.signed)


class StructField(Type):
    def __init__(self, total_size, type_):
        super(StructField, self).__init__(total_size)
        self.type = type_

    def __eq__(self, other):
        if not isinstance(other, StructField):
            return NotImplemented

        return self.type == other.type and super(StructField, self).__eq__(other)

    def __repr__(self):
        return "StructField({!r}, {!r})".format(self.total_size, self.type)


class Function(Type):
    def __init__(self, type_=None):
        super(Function, self).__init__(0)
        self.type = type_

    def __eq__(self, other):
        if not isinstance(other, Function):
            return NotImplemented

        return self.type == other.type and super(Function, self).__eq__(other)

    def __repr__(self):
        return "Function({!r})".format(self.type)


class Pointer(Type):
    def __init__(self, total_size, pointed_type):
        super(Pointer, self).__init__(total_size)
        self.pointed_type = pointed_type

    def __eq__(self, other):
        if not isinstance(other, Pointer):
            return NotImplemented

        return self.pointed_type == other.pointed_type and super(Pointer, self).__eq__(other)

    def __repr__(self):
        return "Pointer({!r}, {!r})".format(self.total_size, self.pointed_type)


class Array(Type):
    def __init__(self, total_size, num_elem, elem_type):
        super(Array, self).__init__(total_size)
        self.num_elem = num_elem
        self.elem_type = elem_type

    def __eq__(self, other):
        if not isinstance(other, Array):
            return NotImplemented

        return (self.num_elem == other.num_elem and self.elem_type == other.elem_type
                and super(Array, self).__eq__(other))

    def __repr__(self):
        return "Array({!r}, {!r}, {!r})".format(self.total_size, self.num_elem, self.elem_type)


class Struct(Type):
    def __init__(self, name, total_size, fields):
        super(Struct, self).__init__(total_size)
        self.name = name
        self.fields = fields

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented

        return (self.name == other.name and self.fields == other.fields
                and super(Struct, self).__eq__(other))

    def __repr__(self):
        # fields are too much, don't print them
        return "Struct({!r}, {!r}, ...)".format(self.total_size, self.name, self.fields)
