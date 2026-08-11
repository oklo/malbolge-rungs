"""Geometry-free upper bound on per-lane emittability for map12-hi.

The prior record (docs/attempts/2026-08-10-claude-map12-hi.md) proves lanes
0x90/0x9c/0xf9 dead across 1611 geometries of the two-stage family, and names
"widen the tail window / three-hop pointer chain" as the next lever.  Before
spending budget building a wider pointer chain, ask the question the chain is
supposed to answer, with the chain removed:

    a lane enters its tail with a = J(x) and some data pointer d.
    Every operand it ever reads is mem[d] for some d.  In the whole
    two-stage family every such cell is a *source-valid byte of its own
    address*, hence printable, hence in [33,126].

So the most generous model of any pointer geometry whatsoever -- 2-hop, 3-hop,
n-hop, MOVD-repositioned, shared tails, anything -- is: every operand is an
INDEPENDENT free choice from [33,126].  If a lane's target is not emittable
under that, no pointer widening can rescue it.

Grammar: since ROT overwrites a with rot(mem[d]) it discards J(x) entirely, so
any op string reduces to  CRAZY^n  applied to either J(x) or to rot(v).
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.hell_lite.ops import crazy_word, rotate_right_word  # noqa: E402

PRINTABLE = list(range(33, 127))
INPUTS = [0xA5, 0xE0, 0x90, 0x9C, 0x84, 0xA1, 0xBD, 0xC8, 0xBE, 0xF9, 0x86, 0xDD]
TGT = {x: x ^ 0x51 for x in INPUTS}

# precompute crazy(a, v) for v printable
def step(words):
    out = set()
    for a in words:
        for v in PRINTABLE:
            out.add(crazy_word(a, v))
    return out


def reach_outputs(a0, depth=8, operands=PRINTABLE):
    """{a % 256} reachable from accumulator a0 with <=depth CRAZY/ROT ops,
    every operand an independent free choice from `operands`."""
    outs = {a0 % 256}
    # chain with no ROT
    cur = {a0}
    for _ in range(depth):
        cur = {crazy_word(a, v) for a in cur for v in operands}
        outs |= {a % 256 for a in cur}
    # chain that begins with a ROT (ROT wipes a, so this is J-independent)
    rot0 = {rotate_right_word(v) for v in operands}
    outs |= {a % 256 for a in rot0}
    cur = set(rot0)
    for _ in range(depth):
        cur = {crazy_word(a, v) for a in cur for v in operands}
        outs |= {a % 256 for a in cur}
    return outs


if __name__ == "__main__":
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    # J-independent part first
    rot_chain = reach_outputs(-1, depth=0)  # dummy
    print(f"free-printable operand model, CRAZY depth <= {depth}")
    # the ROT-seeded chain is the same for every lane; report it once
    rot0 = {rotate_right_word(v) for v in PRINTABLE}
    outs = {a % 256 for a in rot0}
    cur = set(rot0)
    for k in range(depth):
        cur = {crazy_word(a, v) for a in cur for v in PRINTABLE}
        outs |= {a % 256 for a in cur}
        print(f"  ROT-seeded, depth {k+1}: |reachable outputs| = {len(outs)}")
    print(f"  ROT-seeded closure covers {len(outs)}/256 output bytes")
    missing = sorted(set(range(256)) - outs)
    print(f"  missing: {[hex(m) for m in missing]}")
