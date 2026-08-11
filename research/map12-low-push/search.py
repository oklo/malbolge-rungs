#!/usr/bin/env python3
"""Stage 3: search for a NOP-spaced walk pattern that makes all twelve lanes
land simultaneously.

Because every walk gap >= 52 is larger than the largest pairwise input
difference (51), a pattern whose gaps are all >= 52 is *collision free*: no two
lanes ever share a table cell.  The twelve lanes are then twelve independent
problems and the joint DP that the 2026-08-10 attempt found UNSAT disappears.

A gap of 52 + ((delta - 52) mod 94) realises any residue delta, so the design
variables are just K residues mod 94:

    R              the residue of the table base (set by the NOP shift s)
    P_2..P_K       the walk offsets mod 94

Lane b reads the cell at residue (R + b + P_i) mod 94 at step i.

usage: search.py [K] [samples] [seed]
"""
import sys, random
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lowmodel import *
from stage2 import CFG

K = int(sys.argv[1]) if len(sys.argv) > 1 else 5
NS = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
random.seed(int(sys.argv[3]) if len(sys.argv) > 3 else 1)

# --- transition tables on trits 0..4 (state 0..242) --------------------------
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
SUCC = [[0] * 243 for _ in range(94)]      # residue -> state -> bitmask of successors
PRE = [[0] * 243 for _ in range(94)]       # residue -> target -> bitmask of predecessors
for u in range(94):
    for a in range(243):
        m = 0
        for v in BY[u]:
            t = TR[a][v]
            m |= 1 << t
            PRE[u][t] |= 1 << a
        SUCC[u][a] = m


def step(mask, u):
    out = 0
    while mask:
        low = mask & -mask
        out |= SUCC[u][low.bit_length() - 1]
        mask ^= low
    return out


def try_cfg(c, K, NS):
    if K % 2 != c["par"]:
        return None
    starts = {b: b + 81 * c["start_t4"] for b in INPUTS}
    tgt = c["Lstar"]
    best = (0, None)
    for _ in range(NS):
        R = random.randrange(94)
        P = [0] + [random.randrange(94) for _ in range(K - 2)]
        S = {b: 1 << starts[b] for b in INPUTS}
        for i in range(K - 1):
            for b in INPUTS:
                S[b] = step(S[b], (R + b + P[i]) % 94)
        # last step: one shared residue offset must work for all twelve lanes
        for q in range(94):
            n = 0
            for b in INPUTS:
                if S[b] & PRE[(R + b + q) % 94][tgt[b]]:
                    n += 1
            if n > best[0]:
                best = (n, (R, P + [q]))
                if n == 12:
                    return best
    return best


print("K = %d, %d samples per config" % (K, NS))
overall = (0, None, None)
for c in CFG:
    if K % 2 != c["par"]:
        continue
    r = try_cfg(c, K, NS)
    if r is None:
        continue
    n, sol = r
    print("  K0=%-5d par=%d  best lanes = %2d/12   %s"
          % (c["K0"], c["par"], n, "R=%d P=%s" % sol if sol else ""))
    if n > overall[0]:
        overall = (n, c, sol)
    if n == 12:
        break
print()
n, c, sol = overall
if c:
    print("BEST: %d/12  K0=%d par=%d start_t4=%d H=%d" %
          (n, c["K0"], c["par"], c["start_t4"], c["H"]))
    print("      R=%d  P=%s" % sol)
