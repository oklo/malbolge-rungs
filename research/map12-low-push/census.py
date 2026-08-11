#!/usr/bin/env python3
"""Stage 4: how wide is the spaced-walk solution space?

A single 12/12 hit could be luck.  This samples (pattern, base residue) pairs
uniformly for each buildable offset and each walk depth K, and reports the
fraction that solve all twelve lanes, plus the smallest span that solves.

usage: census.py [samples] [maxspan]
"""
import sys, random
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lowmodel import *
from stage2 import configs

NS = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
MAXSPAN = int(sys.argv[2]) if len(sys.argv) > 2 else 140
random.seed(7)
CFG = configs(700)

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


print("%-5s %-6s %-8s %-9s %-8s %s" % ("K", "K0", "patterns", "sampled", "solve%", "min span solving"))
for K in (3, 4, 5, 6):
    PATS = patterns(K, MAXSPAN)
    if not PATS:
        continue
    for c in CFG:
        if K % 2 != c["par"]:
            continue
        starts = {b: b + 81 * c["start_t4"] for b in INPUTS}
        tgt = c["Lstar"]
        hit, minspan = 0, None
        for _ in range(NS):
            P = random.choice(PATS)
            R = random.randrange(94)
            ok = True
            for b in INPUTS:
                m = 1 << starts[b]
                for p in P:
                    m = step(m, (R + b + p) % 94)
                if not (m >> tgt[b] & 1):
                    ok = False
                    break
            if ok:
                hit += 1
                if minspan is None or P[-1] < minspan:
                    minspan = P[-1]
        print("%-5d %-6d %-8d %-9d %-8.2f %s"
              % (K, c["K0"], len(PATS), NS, 100.0 * hit / NS,
                 minspan if minspan is not None else "-"))
