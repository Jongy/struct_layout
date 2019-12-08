PLUGIN = struct_layout.so

ifeq ($(DEBUG),1)
CFLAGS_DEBUG = -g
else
CFLAGS_DEBUG = -O2 -DNDEBUG
endif

all: $(PLUGIN)

$(PLUGIN): gcc_plugin/struct_layout.c
	g++ $(CFLAGS_DEBUG) -Wall -Werror -I`gcc -print-file-name=plugin`/include -fpic -shared -o $@ $<

run: $(PLUGIN) tests/test_struct.c
	gcc -fplugin=./$(PLUGIN) -fplugin-arg-struct_layout-output=layout.txt -fplugin-arg-struct_layout-struct=test_struct tests/test_struct.c -c
	@echo
	@cat layout.txt

test: $(PLUGIN)
	python3 -m pytest -v tests

clean:
	rm -f $(PLUGIN)
