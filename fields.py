class Type(object):
    def __init__(self, total_size):
        self.total_size = total_size


class Basic(Type):
    def __init__(self, total_size, type_):
        super(Basic, self).__init__(total_size)
        self.type = type_


class Pointer(Type):
    def __init__(self, total_size, pointed_type):
        super(Pointer, self).__init__(total_size)
        self.pointed_type = pointed_type


class Array(Type):
    def __init__(self, total_size, num_elem, elem_type):
        super(Array, self).__init__(total_size)
        self.num_elem = num_elem
        self.elem_type = elem_type
