"""
very simplistic "pahole" based on the pythonic objects struct_layout creates.
iterates over a list of structs and prints adjacent fields which have padding
in between them.
"""


def pahole_struct(s):
    cur = 0
    prev_field = None
    prev_size = 0
    prev_ofs = 0
    for k, v in s.fields.items():
        ofs, entry = v
        # we assume the dicts are ordered (python 3.7+), but let's ensure it here...
        # do allow multiple fields on the same offsets - these are unions
        assert cur <= ofs or ofs == prev_ofs, (f"ordered dict or what, in {s.name}, {prev_field}"
                                               f" was at {prev_ofs} but now {k} is at {ofs}")

        if cur != ofs:
            print(f"{s.name}: {prev_field} at {prev_ofs} with size {prev_size}, followed by {k} at"
                  f" {ofs} size {entry.total_size}")
            cur = ofs

        cur += entry.total_size

        prev_ofs = ofs
        prev_size = entry.total_size
        prev_field = k


def pahole(structs):
    for s in structs.values():
        pahole_struct(s)
