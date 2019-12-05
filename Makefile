PLUGIN = struct_layout.so

all: $(PLUGIN)

$(PLUGIN): struct_layout.c
	g++ -g -Wall -Werror -I`gcc -print-file-name=plugin`/include -fpic -shared -o $@ $<

run: $(PLUGIN) tests/test_struct.c
	gcc -fplugin=./$(PLUGIN) -fplugin-arg-struct_layout-output=layout.txt -fplugin-arg-struct_layout-struct=test_struct tests/test_struct.c -c
	cat layout.txt

test: $(PLUGIN)
	python -m pytest -v tests

clean:
	rm -f $(PLUGIN)
