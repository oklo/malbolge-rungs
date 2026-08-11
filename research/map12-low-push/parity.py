#!/usr/bin/env python3
"""Why only an ODD walk depth solves this rung.

The frozen high part H depends on the parity of K, and on this input set the
even-parity H values (729 and 972) put some lanes' L* above 162, i.e. they
demand a final accumulator trit4 of 2.  Trit4 starts at 2 (K0/81 = 2 mod 3) and
CRAZY preserves a 2 there only when the operand's trit4 is 1, i.e. only when the
operand byte is >= 81.  So a t4 = 2 lane must take EVERY one of its K operands
from the >= 81 half of its address's eight legal bytes, and that residual
alphabet is what has to hit the exact 4-trit remainder.

This measures, per lane and with the address residues left completely free, how
often that is satisfiable -- separately for lanes needing t4 = 2 and t4 != 2.
"""
import sys, random
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lowmodel import *
from stage2 import configs

random.seed(3)
NS = int(sys.argv[1]) if len(sys.argv) > 1 else 4000

TR = [[0] * 127 for _ in range(243)]
for a in range(243):
    for v in range(33, 127):
        o, f = 0, 1
        x, y = a, v
        for _ in range(5):
            o += CR[y % 3][x % 3] * f
            x //= 3
            y //= 3
            f *= 3
        TR[a][v] = o
BY = [legal_bytes(u) for u in range(94)]
SUCC = [[0] * 243 for _ in range(94)]
for u in range(94):
    for a in range(243):
        m = 0
        for v in BY[u]:
            m |= 1 << TR[a][v]
        SUCC[u][a] = m


def step(mask, u):
    out = 0
    while mask:
        low = mask & -mask
        out |= SUCC[u][low.bit_length() - 1]
        mask ^= low
    return out


print("legal bytes >= 81 (trit4 = 1) per address residue:")
cnt = [sum(1 for v in BY[u] if v >= 81) for u in range(94)]
print("  min=%d max=%d mean=%.2f" % (min(cnt), max(cnt), sum(cnt) / 94.0))
print()

for K in (4, 5, 6):
    for c in configs(700):
        if K % 2 != c["par"] or c["K0"] != 2106:
            continue
        starts = {b: b + 81 * c["start_t4"] for b in INPUTS}
        tgt = c["Lstar"]
        need2 = [b for b in INPUTS if tgt[b] // 81 == 2]
        rate = {}
        for b in INPUTS:
            hit = 0
            for _ in range(NS):
                m = 1 << starts[b]
                for _ in range(K):
                    m = step(m, random.randrange(94))
                hit += (m >> tgt[b]) & 1
            rate[b] = hit / NS
        print("K=%d K0=%d H=%d  lanes needing t4=2: %s"
              % (K, c["K0"], c["H"], [hex(b) for b in need2] or "none"))
        print("   per-lane satisfiable rate over free residues:")
        for b in INPUTS:
            print("     %s t4=%d  %.3f%s" % (hex(b), tgt[b] // 81, rate[b],
                                             "   <-- t4=2" if tgt[b] // 81 == 2 else ""))
        print()
