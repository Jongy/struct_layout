PLUGIN = struct_layout.so

ifeq ($(DEBUG),1)
CFLAGS_DEBUG = -g
else
CFLAGS_DEBUG = -O2 -DNDEBUG
endif

all: $(PLUGIN)

$(PLUGIN): gcc_plugin/struct_layout.c
	$(CXX) $(CFLAGS_DEBUG) -Wall -Werror -I`$(CC) -print-file-name=plugin`/include -fpic -shared -o $@ $<

run: $(PLUGIN) tests/test_struct.c
	$(CC) -fplugin=./$(PLUGIN) -fplugin-arg-struct_layout-output=layout.txt -fplugin-arg-struct_layout-struct=test_struct tests/test_struct.c -c
	@echo
	@cat layout.txt

all.py: linux/include_all.c all
	KDIR=$(KDIR) python3 linux/dump_structs.py $@

linux_all: all.py

test: $(PLUGIN)
	python3 -m pytest -v tests

clean:
	rm -f $(PLUGIN) all.py

format:
	python3 -m ruff format
