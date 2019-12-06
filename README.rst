A GCC plugin to dump the final layout of a struct and all types it references.

Build
=====

Just hit ``make``.

Using
=====

.. code-block:: bash

    $ gcc -fplugin=./struct_layout.so -fplugin-arg-struct_layout-output=layout.txt -fplugin-arg-struct_layout-struct=test_struct tests/test_struct.c -c

You'll have your results in ``layout.txt``. With a lot of debug information printed to stderr as well :)

Using the output
----------------

Output is printed as Python objects, for easier handling later.

A ``Struct`` object (or ``Union``) is created for each item.
The object holds the name and size of the struct/union, plus a dictionary of the fields.
The dictionary maps field names to tuples of (offset, field type). For unions, the offset is always 0.

The objects & field types are defined in ``fields.py``.

All types (but ``Void``) have a ``total_size`` attribute, with their total size in bits. Other attributes vary between
field types:

* ``Scalar`` - scalars, they also have their basic type, like ``int`` or ``char`` or ``unsigned long int``.
* ``StructField`` - struct fields, these have the struct name they are referencing.
* ``UnionField`` - like ``StructField`` for unions.
* ``Pointer`` - for all types of pointers, these have their "pointee" type, which may be e.g ``Scalar`` or
* ``Void`` - ``void`` type, for example in ``void *``.
* ``Function`` - pointee type in case of function pointers.
  another ``Pointer`` or anything else.
* ``Array`` - for arrays, these have the number of elements and the type of each element (similar to the
  pointee type of ``Pointer``)

For example, the struct ``struct s { int x; char y; void *p; };`` on my x86-64 evaluates to:

.. code-block:: python

    s = Struct('s', 128, {
        'x': (0, Scalar(32, 'int')),
        'y': (32, Scalar(8, 'char')),
        'p': (64, Pointer(64, Void())),
    })


For a Linux kernel struct
-------------------------

.. code-block:: bash

    $ cd linux
    $ python dump_struct.py task_struct linux/sched.h layout.txt

You can set the ``KDIR`` environment variable to run against a specific kernel tree (by default, runs against your local).

.. code-block:: bash

    $ KDIR=/path/to/kernel python dump_struct.py ...

It will take some more work for this plugin to handle complex structs such as ``task_struct``, though.

Tests
=====

.. code-block:: bash

    $ make test
