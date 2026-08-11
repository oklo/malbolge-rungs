#!/usr/bin/env python3
"""Stage 5: pick the (pattern, base residue) that solves with the shortest
program.  Program length = K0 + 1 + s + max(input) + span + 1, and
s = (R - (K0+1)) mod 94, so minimising s + span minimises the file.

usage: minimize.py [K0] [maxspan] [maxs]
"""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lowmodel import *
from stage2 import configs

K0 = int(sys.argv[1]) if len(sys.argv) > 1 else 1377
MAXSPAN = int(sys.argv[2]) if len(sys.argv) > 2 else 74
MAXS = int(sys.argv[3]) if len(sys.argv) > 3 else 12
K = 5

c = [x for x in configs(700) if x["K0"] == K0 and x["par"] == K % 2][0]
starts = {b: b + 81 * c["start_t4"] for b in INPUTS}
tgt = c["Lstar"]

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


ALLOWED = [d for d in range(1, MAXSPAN + 1) if d not in DIFFS]
PATS = []


def rec(P):
    if len(P) == K:
        PATS.append(tuple(P))
        return
    for g in ALLOWED:
        p = P[-1] + g
        if p > MAXSPAN:
            break
        if all((p - q) not in DIFFS for q in P):
            rec(P + [p])


rec([0])
PATS.sort(key=lambda P: P[-1])
print("%d patterns with span <= %d; scanning s = 0..%d" % (len(PATS), MAXSPAN, MAXS))

best = None
for P in PATS:
    for s in range(MAXS + 1):
        if best and s + P[-1] >= best[0]:
            break
        R = (K0 + 1 + s) % 94
        ok = True
        for b in INPUTS:
            m = 1 << starts[b]
            for p in P:
                m = step(m, (R + b + p) % 94)
            if not (m >> tgt[b] & 1):
                ok = False
                break
        if ok:
            best = (s + P[-1], s, R, P)
            print("  s=%-3d span=%-3d R=%-3d  bytes=%d  P=%s"
                  % (s, P[-1], R, K0 + 1 + s + max(INPUTS) + P[-1] + 1, list(P)))
            break
print()
if best:
    print("BEST: s=%d span=%d R=%d P=%s" % (best[1], best[3][-1], best[2], list(best[3])))
