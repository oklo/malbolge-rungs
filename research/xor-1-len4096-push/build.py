#!/usr/bin/env python3
"""Code-dispatch skeleton for L2.R0d.xor-1-len4096.

Prior art (research/xor-1-len4096) dispatches on D: 33 bytes of prologue leave
m[72] = 9b, then MOVD makes D = 9b+1 and seven CRAZYs walk a private DATA block.
Every operand there is a program byte < 243, which is what forces the top five
trits of the accumulator and caps that family at 194/256 (see
docs/attempts/2026-08-11-claude-xor-1-len4096.md).

This module changes one byte: the MOVD at address 32 becomes JMP, so
c = m[72] = 9b and each input starts executing at 9b+1.  The private block is
now nine bytes of CODE, one input per block, so each input picks its own
*instruction sequence* -- including ROT, which is the only instruction that can
put a controllable trit into position 9 and thereby escape the barrier.

Layout:
    0..32     prologue (byte 32 = JMP instead of MOVD)
    62,71,72,73  prologue data cells, forced to 71,121,121,61
    9b+1..9b+9   input b's private code block
    N = 2305
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mal import (byte_for, legal_bytes, code_of, run, VALID_CODES, NAMES)

PROLOGUE = b"u'&%:9\"!}}|zzywwvttsqqpnnmkkjhhgf"  # first 33 bytes of prior art's cand.mal
N = 2305
#   40 -> 122 and 123 -> 70 are the initial MOVD chain (d: 1 -> 40 -> 123 -> 71);
#   62 -> 71 and 73 -> 61 are the 3-instruction rotation cycle's pointers;
#   71, 72 -> 121 are the pair of M1-operands whose double CRAZY leaves m[72] = b.
FORCED = {40: 122, 62: 71, 71: 121, 72: 121, 73: 61, 123: 70}
JMP, OUT, IN, ROT, MOVD, CRZ, NOP, HLT = 4, 5, 23, 39, 40, 62, 68, 81


def block_addrs(b):
    return list(range(9 * b + 1, 9 * b + 10))


def free_cells():
    """Addresses in the block region we are free to choose (not prologue, not forced)."""
    return [a for a in range(33, N) if a not in FORCED]


def base_program(filler=NOP):
    prog = bytearray(N)
    prog[: len(PROLOGUE)] = PROLOGUE
    prog[32] = byte_for(JMP, 32)          # dispatch on C, not D
    for a in range(len(PROLOGUE), N):
        prog[a] = byte_for(filler, a)
    for a, v in FORCED.items():
        prog[a] = v
    return prog


def set_code(prog, addr, code):
    v = byte_for(code, addr)
    assert v is not None, (addr, code)
    prog[addr] = v


def check_source(prog):
    for a, b in enumerate(prog):
        assert 33 <= b <= 126, (a, b)
        assert code_of(b, a) in VALID_CODES, (a, b, code_of(b, a))


def main():
    prog = base_program()
    # dispatch smoke test: every block is just [OUT, HALT]
    for b in range(256):
        ad = block_addrs(b)
        for a, code in ((ad[0], OUT), (ad[1], HLT)):
            if a in FORCED or a < len(PROLOGUE):
                continue
            set_code(prog, a, code)
    check_source(prog)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dispatch.mal")
    open(path, "wb").write(bytes(prog))
    ok = 0
    for b in range(256):
        out, st, steps = run(bytes(prog), bytes([b]))
        want = (9 * b) % 256
        good = st == "Halted" and len(out) == 1 and out[0] == want
        ok += good
        if b < 12 or not good:
            print(f"b={b:3d} out={out.hex():4s} want={want:3d} {st} steps={steps} {'OK' if good else ''}")
    print(f"dispatch reaches its own block for {ok}/256 inputs -> {path}")


if __name__ == "__main__":
    main()
