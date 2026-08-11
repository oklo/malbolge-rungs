#!/usr/bin/env python3
"""Stage 3b: exhaustive search over *compact* collision-free walk patterns.

Span matters twice: it is executed as NOPs (steps) and, more importantly, the
code pointer C and the data pointer D advance in lockstep during the walk, so
the code's spacing NOPs march forward at the same rate as the table walk.  For
the code never to run into the table we need

    D - C  at walk start  >  span            i.e.  K0 + 9 > code_before + span

so a shorter span buys a smaller K0 and a shorter program.

usage: search2.py [K] [maxspan]
"""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lowmodel import *
from stage2 import configs

K = int(sys.argv[1]) if len(sys.argv) > 1 else 5
MAXSPAN = int(sys.argv[2]) if len(sys.argv) > 2 else 140
FLOOR = int(sys.argv[3]) if len(sys.argv) > 3 else 700
CFG = configs(FLOOR)

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


def patterns(K, maxspan):
    out = []

    def rec(P):
        if len(P) == K:
            out.append(tuple(P))
            return
        for g in ALLOWED:
            p = P[-1] + g
            if p > maxspan:
                break
            if all((p - q) not in DIFFS for q in P):
                rec(P + [p])
    rec([0])
    return out


PATS = patterns(K, MAXSPAN)
print("K=%d maxspan=%d -> %d collision-free patterns" % (K, MAXSPAN, len(PATS)))

best = (0, None)
sols = []
for c in CFG:
    if K % 2 != c["par"]:
        continue
    starts = {b: b + 81 * c["start_t4"] for b in INPUTS}
    tgt = c["Lstar"]
    for P in PATS:
        for R in range(94):
            n = 0
            for b in INPUTS:
                m = 1 << starts[b]
                for p in P:
                    m = step(m, (R + b + p) % 94)
                if m >> tgt[b] & 1:
                    n += 1
                elif n + (12 - len(INPUTS)) < 0:
                    break
            if n > best[0]:
                best = (n, (c["K0"], c["par"], c["start_t4"], R, P))
                print("  %2d/12  K0=%-5d R=%-3d span=%-4d P=%s"
                      % (n, c["K0"], R, P[-1], list(P)))
            if n == 12:
                sols.append((c["K0"], R, P))
                if len(sols) >= 8:
                    break
        if len(sols) >= 8:
            break
    if len(sols) >= 8:
        break

print()
print("solutions (K0, R, P):")
for s in sols:
    print("  K0=%-5d R=%-3d span=%-4d P=%s" % (s[0], s[1], s[2][-1], list(s[2])))
