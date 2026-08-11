#!/usr/bin/env python3
"""chainfind, ranked by how many live lanes demand final trit4 = 2.

A lane whose L* lands in [162,242] starts at trit4 = 2 and must *stay* there,
which forces every one of its K walk operands to be a byte >= 81 (trit4 = 1).
Only 3..5 of the eight legal bytes at an address qualify, so those lanes are the
expensive ones -- the 13/16 build missed exactly two of them.  So rank the
15/16 specs by that count first, cost second.
"""
import sys
from itertools import product
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from model import INPUTS, TARGETS, crazy, trits  # noqa
import spec as S  # noqa
from chainfind import bfs, path, words_for  # noqa

WANT = int(sys.argv[1]) if len(sys.argv) > 1 else 15
MIN_ADDR = int(sys.argv[2]) if len(sys.argv) > 2 else 900

lowspecs = S.enum_low()
configs = []
for sp, lows in lowspecs:
    for ct in product(range(3), repeat=4):
        for K in range(2, 10):
            r = S.score_spec(lows, sp[4], ct, K, MIN_ADDR)
            if r and r[0] >= WANT:
                hard = sum(1 for b, (a, Ls, st) in r[2].items() if Ls >= 162)
                configs.append((r[0], hard, sp, ct, K, r))
configs.sort(key=lambda c: (-c[0], c[1]))
print("configs at >=%d live: %d ; min hard lanes = %d"
      % (WANT, len(configs), configs[0][1] if configs else -1), flush=True)

dist0, prev0 = bfs(0, limit=14)
cand = {}
for ci, c in enumerate(configs):
    if c[1] > configs[0][1] + 1:
        break
    for w1, w2s in words_for(c[2], c[3]).items():
        if dist0[w1] >= 0:
            cand.setdefault(w1, []).append((ci, w2s))
print("reachable W1 words: %d" % len(cand), flush=True)
best = None
for w1 in sorted(cand, key=lambda w: dist0[w]):
    if best is not None and dist0[w1] + 1 >= best[0]:
        break
    d1, p1 = bfs(w1, crazy_first=True, limit=4)
    for ci, w2s in cand[w1]:
        for w2 in w2s:
            if d1[w2] < 0:
                continue
            cost = dist0[w1] + d1[w2]
            key = (configs[ci][1], cost)
            if best is None or key < (best[3], best[0]):
                best = (cost, w1, w2, configs[ci][1], ci,
                        path(prev0, 0, w1), path(p1, w1, w2))
if best is None:
    print("none")
    raise SystemExit
cost, w1, w2, hard, ci, leg1, leg2 = best
live, hard, sp, ct, K, r = configs[ci]
print("\nBEST live=%d hard=%d ops=%d W1=%d W2=%d K=%d" % (live, hard, cost, w1, w2, K))
print("  spec g0..g5 =", [S.MAPS[m] for m in sp], " ct =", ct)
print("  dead:", [hex(x) for x in r[1]], " addr [%d..%d]" % (r[4], r[5]))
print("  leg1:", leg1)
print("  leg2:", leg2)
print("  needs:", {hex(b): v for b, v in sorted(r[2].items(), key=lambda kv: kv[1][0])})
