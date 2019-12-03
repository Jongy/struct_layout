A GCC plugin to dump the final layout of a struct.

This is totally WIP.

Build
=====

Just hit ``make``.

Using
=====

.. code-block:: bash

    $ gcc -fplugin=./struct_layout.so -fplugin-arg-struct_layout-output=layout.txt -fplugin-arg-struct_layout-struct=test_struct tests/test_struct.c -c

You'll have your results in ``layout.txt``. With a lot of debug information printed to stderr as well :)

For a Linux kernel struct
-------------------------

.. code-block:: bash

    $ cd linux
    $ python dump_struct.py task_struct linux/sched.h layout.txt

You can set the ``KDIR`` environment variable to run against a specific kernel tree (by default, runs against your local).

.. code-block:: bash

    $ KDIR=/path/to/kernel python dump_struct.py ...

It will take some more work for this plugin to handle complex structs such as ``task_struct``, though.
