#!/usr/bin/env python3
"""Find a dispatch spec that is both high-scoring AND buildable.

For every spec that reaches `--want` live lanes, expand the per-trit (w1,w2)
pair choices into the product set of concrete words (W1, W2), then ask whether
the prefix chain can actually put them in two distinct memory cells:

    W1 reachable from a = 0                       (BFS over the chain graph)
    W2 reachable from W1 with a CRAZY as the first op of leg 2
      -- otherwise leg 2 would ROT the cell holding W1 and destroy it.

Prints the cheapest realisable (spec, W1, W2) with the full op list.
"""
import sys
from itertools import product

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from model import INPUTS, TARGETS, crazy, trits  # noqa: E402
import spec as S  # noqa: E402

WORDS = 59049
BYTES = list(range(33, 127))
WANT = int(sys.argv[1]) if len(sys.argv) > 1 else 15
MIN_ADDR = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
LEG2_DEPTH = int(sys.argv[3]) if len(sys.argv) > 3 else 4


def bfs(src, crazy_first=False, limit=12):
    dist = [-1] * WORDS
    prev = [None] * WORDS
    dist[src] = 0
    frontier = [src]
    depth = 0
    while frontier and depth < limit:
        depth += 1
        nxt = []
        for a in frontier:
            if not (crazy_first and depth == 1):
                r = a // 3 + (a % 3) * 3 ** 9
                if dist[r] < 0:
                    dist[r] = depth; prev[r] = (a, None); nxt.append(r)
            for v in BYTES:
                w = crazy(a, v)
                if dist[w] < 0:
                    dist[w] = depth; prev[w] = (a, v); nxt.append(w)
        frontier = nxt
    return dist, prev


def path(prev, src, dst):
    ops = []
    cur = dst
    while cur != src:
        p, v = prev[cur]
        ops.append(v); cur = p
    return ops[::-1]


def words_for(spec, ct):
    """product set of (W1, W2) realising the spec; returns dict W1 -> [W2...]"""
    per = []
    for i in range(6):
        per.append([(w1 * 3 ** i, w2 * 3 ** i)
                    for w1, w2 in S.COMPOSE[S.MAPS[spec[i]]]])
    for i in range(4):
        per.append([(w1 * 3 ** (6 + i), w2 * 3 ** (6 + i))
                    for w1, w2 in S.CONST_PAIRS[ct[i]]])
    out = {}
    acc = [(0, 0)]
    for opts in per:
        acc = [(a + x, b + y) for a, b in acc for x, y in opts]
    for a, b in acc:
        out.setdefault(a, []).append(b)
    return out


def main():
    lowspecs = S.enum_low()
    configs = []
    for sp, lows in lowspecs:
        for ct in product(range(3), repeat=4):
            for K in range(2, 10):
                r = S.score_spec(lows, sp[4], ct, K, MIN_ADDR)
                if r and r[0] >= WANT:
                    configs.append((r[0], sp, ct, K, lows, r))
    print("configs at >=%d live: %d" % (WANT, len(configs)))

    dist0, prev0 = bfs(0, limit=14)
    # candidate W1 words, cheapest first
    cand = {}
    for ci, (live, sp, ct, K, lows, r) in enumerate(configs):
        for w1, w2s in words_for(sp, ct).items():
            if dist0[w1] < 0:
                continue
            cand.setdefault(w1, []).append((dist0[w1], ci, w2s))
    print("reachable W1 words across all configs: %d" % len(cand))
    order = sorted(cand, key=lambda w: dist0[w])
    best = None
    for n, w1 in enumerate(order):
        if best is not None and dist0[w1] + 1 >= best[0]:
            break
        d1, p1 = bfs(w1, crazy_first=True, limit=LEG2_DEPTH)
        for _, ci, w2s in cand[w1]:
            for w2 in w2s:
                if d1[w2] < 0:
                    continue
                cost = dist0[w1] + d1[w2]
                if best is None or cost < best[0]:
                    live, sp, ct, K, lows, r = configs[ci]
                    best = (cost, w1, w2, live, sp, ct, K, r,
                            path(prev0, 0, w1), path(p1, w1, w2))
        if n % 25 == 0:
            print("  ... %d/%d W1 tried, best=%s" % (n, len(order),
                                                     best[0] if best else None))
    if best is None:
        print("NO BUILDABLE PAIR at live>=%d within leg2 depth %d" % (WANT, LEG2_DEPTH))
        return
    cost, w1, w2, live, sp, ct, K, r, leg1, leg2 = best
    print("\nBEST: live=%d/16 ops=%d W1=%d W2=%d K=%d" % (live, cost, w1, w2, K))
    print("  g(trits 0..5) =", [S.MAPS[m] for m in sp], " consts =", ct)
    print("  dead lanes:", [hex(x) for x in r[1]])
    print("  addr range: [%d..%d]" % (r[4], r[5]))
    print("  leg1 (0 -> W1):", leg1)
    print("  leg2 (W1 -> W2):", leg2)
    print("  needs:", {hex(b): v for b, v in sorted(r[2].items())})


if __name__ == "__main__":
    main()
