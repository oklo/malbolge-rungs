#!/usr/bin/env python3
"""Exhaustive ceiling for the straight-line CRAZY/ROTATE family on xor51 coverage.

A straight-line classic-Malbolge data path (IN, then any sequence of
CRAZY-with-a-constant and ROTATE, then OUT) acts on the accumulator one trit
position at a time.  CRAZY with a constant applies, at position i, the unary
map m_{c_i} where

    m0 = (1,0,0)   m1 = (1,0,2)   m2 = (2,2,1)      (rows of the crazy table)

and ROTATE cyclically permutes positions.  Because the constant's trit at each
position is chosen independently, N CRAZY ops with R rotations realise exactly

    out = sum_{i=0..9} g_i( trit_{(i+R) mod 10}(b) ) * 3^i ,   g_i in M_N

where M_N is the set of length-N compositions of {m0,m1,m2}, chosen freely and
independently per position.  The output byte is out mod 256, and input trits
6..9 are always 0 (a byte is < 3^6), so those positions contribute a constant K.

This script enumerates that family exhaustively -- every N, every shift R, every
per-position map, every achievable K -- and reports the maximum number of the
256 inputs on which the output equals b XOR 0x51.

Result: the maximum is 34, attained at N in {2,4} with R = 0.  M_N stabilises at
twelve maps and alternates between two twelve-element sets for N >= 4, so
N = 0..5 covers every N.  The rung threshold of 32 is reachable; 36 is not.
Anything past 34 needs input-dependent branching, not a longer straight line.

    python3 research/cov32/family_ceiling.py        # needs numpy
"""

import itertools

import numpy as np

GENERATORS = [(1, 0, 0), (1, 0, 2), (2, 2, 1)]
P3 = [3 ** i for i in range(10)]


def compose(f, g):
    return tuple(f[g[i]] for i in range(3))


def maps_of_depth(n):
    cur = {(0, 1, 2)}
    for _ in range(n):
        cur = {compose(f, g) for g in cur for f in GENERATORS}
    return sorted(cur)


b = np.arange(256)
target = b ^ 0x51
trits = []
x = b.copy()
for _ in range(10):
    trits.append(x % 3)
    x //= 3


def best_for(n, shift):
    maps = maps_of_depth(n)
    var_pos = [i for i in range(10) if (i + shift) % 10 <= 5]
    fix_pos = [i for i in range(10) if (i + shift) % 10 > 5]
    zvals = sorted({g[0] for g in maps})
    ks = {sum(v * P3[i] for v, i in zip(combo, fix_pos)) % 256
          for combo in itertools.product(zvals, repeat=len(fix_pos))}
    allowed = np.zeros(256, dtype=bool)
    allowed[[(-k) % 256 for k in ks]] = True

    contrib = {}
    for i in var_pos:
        j = (i + shift) % 10
        arr = np.zeros((len(maps), 256), dtype=np.int64)
        for gi, g in enumerate(maps):
            arr[gi] = (np.array(g)[trits[j]] * P3[i]) % 256
        contrib[i] = arr

    def triples(ps):
        out = np.zeros((len(maps) ** 3, 256), dtype=np.int64)
        idx = 0
        for u in range(len(maps)):
            for v in range(len(maps)):
                base = contrib[ps[0]][u] + contrib[ps[1]][v]
                for w in range(len(maps)):
                    out[idx] = base + contrib[ps[2]][w]
                    idx += 1
        return out % 256

    lo, hi = triples(var_pos[:3]), triples(var_pos[3:])
    rows = hi.shape[0]
    offsets = (np.arange(rows) * 256)[:, None]
    best = -1
    for row in lo:
        residues = (row[None, :] + hi - target[None, :]) % 256
        counts = np.bincount((offsets + residues).ravel(),
                             minlength=rows * 256).reshape(rows, 256)
        counts[:, ~allowed] = -1
        best = max(best, int(counts.max()))
    return best


if __name__ == "__main__":
    overall = 0
    for n in range(6):
        for shift in range(10):
            score = best_for(n, shift)
            overall = max(overall, score)
            print(f"N={n} shift={shift} |M_N|={len(maps_of_depth(n))} best={score}", flush=True)
    print(f"\nceiling over the whole straight-line family: {overall}/256")
