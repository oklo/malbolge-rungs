#!/usr/bin/env python3
"""Base program + dispatch check for L2.R0.xor-1 under the stride-1 CODE dispatch.

Prior art on this rung (docs/attempts/2026-08-11-claude-xor-1.md) dispatched with
MOVD, so input b addressed a *data* table at b+1 and the whole program was one
straight line; that family's exact ceiling is 68/256.  The sibling rung
L2.R0d.xor-1-len4096 was pushed from 119 to 229 by changing the dispatch
instruction from MOVD to JMP, turning each input's private cells into private
*code*.  This file applies that change at stride 1.

    0        IN            A = b
    1,2,3    MOVD x3       D: 1 -> 40 -> 123 -> 71
    4,5      CRZ x2        operands m[71] = m[72] = 121, so m[72] = b exactly
    6,7      MOVD x2       D: 73 -> 62 -> 72
    8        JMP           c = m[72] = b   ==>  input b executes from b+1, D = 73

Entry state is therefore A = b, C = b+1, D = 73 for every input.  Unlike the
stride-9 rung the code region is shared: cell a is input a-1's first
instruction, input a-2's second, and so on, and every input reads the SAME
operand stream m[73], m[74], ... at the same step index.
"""
import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mal import XLAT2, VALID_CODES, code_of, byte_for, legal_bytes, crazy, run  # noqa

MASK = 0x51
L = 256
OPS = [23, 40, 40, 40, 62, 62, 40, 40, 4]          # prologue, byte 8 = JMP
P = len(OPS)
DATA = {40: 122, 62: 71, 71: 121, 72: 121, 73: 61, 123: 70}


def base_program(filler=None):
    """Program bytes; free cells get `filler(addr)` or the first legal byte."""
    prog = [None] * L
    for a, op in enumerate(OPS):
        prog[a] = byte_for(op, a)
        assert prog[a] is not None
    for a, v in DATA.items():
        assert a >= P, a
        assert code_of(v, a) in VALID_CODES, (a, v)
        prog[a] = v
    for a in range(L):
        if prog[a] is None:
            lb = legal_bytes(a)
            prog[a] = filler(a, lb) if filler else lb[VALID_CODES[0]]
    return bytes(prog)


if __name__ == "__main__":
    # NOP tape: does the dispatch land where the layout says it does?
    prog = base_program(lambda a, lb: lb[68])
    open(os.path.join(HERE, "base.mal"), "wb").write(prog)
    landed = {}
    for b in range(256):
        tr = []
        out, st, steps = run(list(prog), [b], trace=tr, max_steps=40)
        # the instruction executed right after the JMP at c=8
        after = [t for t in tr if t[0] == 9]
        landed[b] = (after[0][1] if after else None, after[0][3] if after else None, st)
    good = [b for b in range(256) if landed[b][0] == b + 1 and landed[b][1] == b]
    print(f"dispatch to c=b+1 with A=b: {len(good)}/256")
    bad = [b for b in range(256) if b not in good]
    print("not dispatched:", bad)
    for b in (8, 9, 70, 71, 72, 100, 200, 254, 255):
        print(f"  b={b:3d} -> {landed[b]}")
