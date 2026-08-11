#!/usr/bin/env python3
"""Enumerate every admissible per-trit dispatch spec and score it.

A spec is a choice of g_i (one of the eight two-CRAZY trit maps) for trits 0..5
plus the constant g_i(0) for trits 6..9.  It fixes

    A0(b) = sum_i g_i(b_i) 3^i      (the lane's table address)
    the frozen high part H_b        (through trit 5 of A0 and the constants)
    the lane's starting trit 4      (g_4 applied to the input's trit 4)

and therefore the whole ceiling.  This is the search the earlier record did only
along one axis (it fixed identity on trits 0..3 and a crushed trit 5).
"""
import sys
from itertools import product

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from model import INPUTS, TARGETS, trits  # noqa: E402

CR = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]
COMPOSE = {}
for w1 in range(3):
    for w2 in range(3):
        COMPOSE.setdefault(tuple(CR[w2][CR[w1][a]] for a in range(3)),
                           []).append((w1, w2))
MAPS = sorted(COMPOSE)                      # the eight realisable trit maps
CONST_PAIRS = {c: [(w1, w2) for w1 in range(3) for w2 in range(3)
                   if tuple(CR[w2][CR[w1][a]] for a in range(3))[0] == c]
               for c in range(3)}

IT = {b: trits(b, 6) for b in INPUTS}
MAXADDR = 3850


def enum_low():
    """all (g0..g5) with 16 distinct low addresses; yields (spec, lows, a4)."""
    out = []
    # incremental DFS over trits, pruning on partial collisions is not sound
    # (later trits can separate), so just brute force with a fast inner loop.
    pre = [[[MAPS[m][IT[b][i]] * 3 ** i for b in INPUTS] for m in range(8)]
           for i in range(6)]
    for m0 in range(8):
        a0 = pre[0][m0]
        for m1 in range(8):
            a1 = [x + y for x, y in zip(a0, pre[1][m1])]
            for m2 in range(8):
                a2 = [x + y for x, y in zip(a1, pre[2][m2])]
                for m3 in range(8):
                    a3 = [x + y for x, y in zip(a2, pre[3][m3])]
                    for m4 in range(8):
                        a4v = [x + y for x, y in zip(a3, pre[4][m4])]
                        for m5 in range(8):
                            lows = [x + y for x, y in zip(a4v, pre[5][m5])]
                            if len(set(lows)) == 16:
                                out.append(((m0, m1, m2, m3, m4, m5), tuple(lows)))
    return out


def score_spec(lows, m4, ct, K, min_addr):
    g4 = MAPS[m4]
    C = sum(ct[i] * 3 ** (6 + i) for i in range(4))
    lo, hi = C + min(lows), C + max(lows)
    if lo < min_addr or hi > MAXADDR:
        return None
    hbase = sum(((min(ct[i], 1) + K) % 2) * 3 ** (i + 1) for i in range(4))
    h = [(243 * (((min(u, 1) + K) % 2) + hbase)) % 256 for u in range(3)]
    ok, dead, need = 0, [], {}
    for idx, b in enumerate(INPUTS):
        Ls = (TARGETS[b] - h[lows[idx] // 243]) % 256
        if Ls > 242:
            dead.append(b); continue
        st = g4[IT[b][4]]
        A = C + lows[idx]
        want4 = Ls // 81
        good = False
        if st in (0, 1):
            good = want4 == (st + K) % 2
        elif want4 in (0, 1):
            good = True                      # drop out of trit4=2 at a chosen step
        else:
            # holding trit4 = 2 forces every operand byte >= 81, and such bytes
            # have trit3 in {0,1} only -- so trit 3 obeys the same law one level
            # down: pinned unless it starts at 2.
            a3 = (A // 27) % 3
            w3 = (Ls // 27) % 3
            good = (a3 == 2) if w3 == 2 else (a3 == 2 or w3 == (a3 + K) % 2)
        if good:
            ok += 1
            need[b] = (A, Ls, st)
        else:
            dead.append(b)
    return ok, dead, need, C, lo, hi


def main():
    min_addr = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    lowspecs = enum_low()
    print("low specs with 16 distinct addresses: %d of %d" % (len(lowspecs), 8 ** 6))
    best = []
    for spec, lows in lowspecs:
        for ct in product(range(3), repeat=4):
            for K in range(2, 10):
                r = score_spec(lows, spec[4], ct, K, min_addr)
                if r and r[0] >= 14:
                    best.append((r[0], spec, ct, K, [hex(x) for x in r[1]],
                                 r[4], r[5]))
    best.sort(key=lambda x: -x[0])
    print("configurations reaching >=14/16: %d" % len(best))
    seen = set()
    for r in best[:400]:
        key = (r[0], MAPS[r[1][4]], r[3] % 2, tuple(r[4]))
        if key in seen:
            continue
        seen.add(key)
        print("  live=%2d/16 g=%s ct=%s K=%d dead=%s addr=[%d..%d]"
              % (r[0], [MAPS[m] for m in r[1]], r[2], r[3], r[4], r[5], r[6]))
        if len(seen) > 12:
            break
    print("\nbest live overall: %d" % (best[0][0] if best else -1))


if __name__ == "__main__":
    main()
