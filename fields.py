class Field(object):
    def __init__(self, name, offset, total_size):
        self.name = name
        self.offset = offset
        self.total_size = total_size


class Basic(Field):
    def __init__(self, name, offset, total_size, type_):
        super(Basic, self).__init__(name, offset, total_size)
        self.type = type_


class Pointer(Field):
    def __init__(self, name, offset, total_size, pointed_type):
        super(Pointer, self).__init__(name, offset, total_size)
        self.pointed_type = pointed_type


class Array(Field):
    def __init__(self, name, offset, total_size, num_elem, elem_type):
        super(Pointer, self).__init__(name, offset, total_size)
        self.num_elem = num_elem
        self.elem_type = elem_type
