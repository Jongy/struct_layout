all: struct_layout.so

struct_layout.so: struct_layout.c
	g++ -g -I`gcc -print-file-name=plugin`/include -fpic -shared -o $@ $<
