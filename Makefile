all: struct_layout.so

struct_layout.so: struct_layout.c
	g++ -g -I`gcc -print-file-name=plugin`/include -fpic -shared -o $@ $<

run: struct_layout.so tests/test_struct.c
	gcc -fplugin=./struct_layout.so -fplugin-arg-struct_layout-output=layout.txt -fplugin-arg-struct_layout-struct=test_struct tests/test_struct.c -c
	cat layout.txt

test: struct_layout.so
	python -m pytest -v tests
