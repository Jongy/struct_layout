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


class Basic(Type):
    def __init__(self, total_size, type_):
        super(Basic, self).__init__(total_size)
        self.type = type_

    def __eq__(self, other):
        if not isinstance(other, Basic):
            return NotImplemented

        return self.type == other.type and super(Basic, self).__eq__(other)


class Function(Basic):
    def __init__(self, total_size, type_):
        super(Function, self).__init__(total_size, type_)


class Pointer(Type):
    def __init__(self, total_size, pointed_type):
        super(Pointer, self).__init__(total_size)
        self.pointed_type = pointed_type

    def __eq__(self, other):
        if not isinstance(other, Pointer):
            return NotImplemented

        return self.pointed_type == other.pointed_type and super(Pointer, self).__eq__(other)


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
