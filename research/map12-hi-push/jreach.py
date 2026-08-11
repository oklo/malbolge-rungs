"""Which landing accumulators J can emit which output bytes?

ubound.py shows the ROT-seeded tail chain reaches only 201/256 output bytes,
and the 55 it misses are the contiguous window 0x9a..0xd0.  Four map12-hi
targets live in that window -- and they are exactly the four lanes every prior
attempt found dead.  Those lanes therefore cannot use ROT at all: they must be
realised by CRAZY^n applied directly to the landing accumulator a = J(x).

That chain is J-dependent, so the question is not "is the tail grammar wide
enough" (three widenings have failed) but "does the dispatch hand the hard
lanes a usable J".  This computes, for every candidate landing value J, the
set of output bytes reachable as  CRAZY^n(J)  with every operand a free choice
from [33,126] -- an upper bound over every pointer geometry in the family.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from tools.hell_lite.ops import crazy_word  # noqa: E402

PRINTABLE = list(range(33, 127))


def crazy_reach(a0, depth=5, operands=PRINTABLE):
    outs = {a0 % 256}
    cur = {a0}
    seen = set(cur)
    for _ in range(depth):
        nxt = set()
        for a in cur:
            for v in operands:
                nxt.add(crazy_word(a, v))
        nxt -= seen
        if not nxt:
            break
        seen |= nxt
        outs |= {a % 256 for a in nxt}
        cur = nxt
    return outs


if __name__ == "__main__":
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    hole = set(range(0x9A, 0xD1))
    # for each J, which hole bytes can it emit?
    tally = {}
    for J in range(0, hi):
        r = crazy_reach(J, depth)
        tally[J] = r
    sizes = sorted({len(r) for r in tally.values()})
    print(f"J in [0,{hi}) depth<={depth}: |reach| distinct sizes {sizes}")
    for t in (0xB1, 0xC1, 0xCD, 0xA8):
        good = [J for J in range(hi) if t in tally[J]]
        print(f"  target {t:#04x}: emittable from {len(good)}/{hi} landing values"
              + (f"  e.g. {good[:12]}" if good else "  -- NONE"))
    # union over all J of hole coverage
    cov = set()
    for J in range(hi):
        cov |= (tally[J] & hole)
    print(f"  hole bytes 0x9a..0xd0 reachable from SOME J: {len(cov)}/{len(hole)}")
    print(f"    {[hex(c) for c in sorted(cov)]}")
