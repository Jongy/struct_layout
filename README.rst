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
