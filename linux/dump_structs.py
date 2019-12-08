import os.path
import shutil
import argparse
import subprocess


def make_dummy(header, wd):
    if not header:
        shutil.copy(os.path.join(wd, "include_all.c"), os.path.join(wd, "dummy.c"))
    else:
        with open(os.path.join(wd, "dummy.c"), "w") as f:
            f.write("/* Autogenerated! */\n")
            f.write("#include <{}>\n".format(header))


def run_make(struct, output, wd):
    args = ["make", "LAYOUT_OUTPUT={}".format(os.path.abspath(output))]
    if struct:
        args.append("TARGET_STRUCT={}".format(struct))
    subprocess.check_call(args, cwd=wd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dump the layout of kernel structs")
    parser.add_argument("output", help="output file")
    parser.add_argument("--struct", help="name of the struct to dump (e.g 'sk_buff')."
                                         " leave empty for *all* structs from processed files")
    parser.add_argument("--header", help="header file to include for this struct"
                                         " (e.g 'linux/skbuff.h'). leave empty for *all* headers")

    args = parser.parse_args()

    wd = os.path.abspath(os.path.dirname(__file__))

    make_dummy(args.header, wd)
    run_make(args.struct, args.output, wd)
