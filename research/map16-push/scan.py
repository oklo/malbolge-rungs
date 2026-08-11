#!/usr/bin/env python3
"""Joint search for the dispatch pair (W1, W2) and the rung configuration.

A chain 0 -> W1 -> W2 is one chain from 0 with a split point, so this enumerates
the BFS tree from 0 and extends every node by one or two further ops, taking the
node as W1 and the extension as W2.  Leg 2 must open with a CRAZY into a fresh
cell, otherwise the ROT would rotate the cell holding W1 and destroy it -- that
is exactly the blocker the 2026-08-10 record stopped on.

Each candidate is scored with the full per-trit model:

    A0(b) = sum_i g_i(b_i) 3^i,   g_i = M[w2_i] o M[w1_i]
    trits 5..9 of A0 freeze to    hf_j = (min(A0_{5+j},1) + K) mod 2
    H_b = 243*hf,  L*_b = (target_b - H_b) mod 256   (needs <= 242)
    trit 4: start s = A0_4; s in {0,1} pins the final trit4 to (s+K) mod 2,
            s = 2 leaves it free (stay at 2, or drop out at a chosen step).

Nothing here assumes identity dispatch on trits 0..3 nor a crushed trit 5; both
were baked into the earlier records on this family.
"""
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from model import INPUTS, TARGETS, crazy, trits, from_trits  # noqa: E402

WORDS = 59049
BYTES = list(range(33, 127))
CR = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]
COMPOSE = [[tuple(CR[w2][CR[w1][a]] for a in range(3)) for w2 in range(3)]
           for w1 in range(3)]

MAXOPS = int(sys.argv[1]) if len(sys.argv) > 1 else 11
MAXADDR = int(sys.argv[2]) if len(sys.argv) > 2 else 3850

ITL = {b: trits(b, 6) for b in INPUTS}        # inputs are < 729


def bfs_tree(limit):
    dist = [-1] * WORDS
    prev = [None] * WORDS
    dist[0] = 0
    frontier = [0]
    depth = 0
    while frontier and depth < limit:
        depth += 1
        nxt = []
        for a in frontier:
            r = a // 3 + (a % 3) * 3 ** 9
            if dist[r] < 0:
                dist[r] = depth; prev[r] = (a, None); nxt.append(r)
            for v in BYTES:
                w = crazy(a, v)
                if dist[w] < 0:
                    dist[w] = depth; prev[w] = (a, v); nxt.append(w)
        frontier = nxt
    return dist, prev


def chain_of(prev, w):
    ops, nodes = [], [w]
    cur = w
    while prev[cur] is not None:
        p, v = prev[cur]
        ops.append(v); nodes.append(p); cur = p
    return nodes[::-1], ops[::-1]


# ---- low part of the address: depends only on (w1 mod 729, w2 mod 729) -------
_lowcache = {}


def low_part(l1, l2):
    key = (l1, l2)
    r = _lowcache.get(key, 0)
    if r != 0:
        return r
    t1, t2 = trits(l1, 6), trits(l2, 6)
    g = [COMPOSE[t1[i]][t2[i]] for i in range(6)]
    lows, a4 = [], []
    for b in INPUTS:
        bt = ITL[b]
        lows.append(sum(g[i][bt[i]] * 3 ** i for i in range(6)))
        a4.append(g[4][bt[4]])
    r = None if len(set(lows)) != 16 else (tuple(lows), tuple(a4))
    _lowcache[key] = r
    return r


_hicache = {}


def hi_part(h1, h2):
    """C = constant contribution of trits 6..9, and their frozen-trit inputs."""
    key = (h1, h2)
    if key in _hicache:
        return _hicache[key]
    t1, t2 = trits(h1, 4), trits(h2, 4)
    g = [COMPOSE[t1[i]][t2[i]] for i in range(4)]
    ct = [g[i][0] for i in range(4)]
    C = sum(ct[i] * 3 ** (6 + i) for i in range(4))
    r = (C, tuple(ct))
    _hicache[key] = r
    return r


def score(w1, w2, min_addr, Ks):
    lp = low_part(w1 % 729, w2 % 729)
    if lp is None:
        return None
    lows, a4 = lp
    C, ct = hi_part(w1 // 729, w2 // 729)
    lo, hi = C + min(lows), C + max(lows)
    if lo < min_addr or hi > MAXADDR:
        return None
    best = None
    for K in Ks:
        hbase = sum(((min(ct[i], 1) + K) % 2) * 3 ** (i + 1) for i in range(4))
        h = [(243 * (((min(u, 1) + K) % 2) + hbase)) % 256 for u in range(3)]
        ok, dead, need = 0, [], {}
        for idx, b in enumerate(INPUTS):
            u = lows[idx] // 243
            Ls = (TARGETS[b] - h[u]) % 256
            if Ls > 242:
                dead.append(b); continue
            st = a4[idx]
            if st == 2 or (Ls // 81) == (st + K) % 2:
                ok += 1
                need[b] = (C + lows[idx], Ls, st)
            else:
                dead.append(b)
        if best is None or ok > best[0]:
            best = (ok, K, dead, need, lo, hi)
    return best


def main():
    dist, prev = bfs_tree(MAXOPS)
    nodes = [w for w in range(WORDS) if dist[w] >= 0]
    print("bfs tree: %d words within %d ops" % (len(nodes), MAXOPS))
    results = []
    for w1 in nodes:
        d1 = dist[w1]
        if d1 < 1:
            continue
        for v in BYTES:
            w2 = crazy(w1, v)
            ops = d1 + 1
            s = score(w1, w2, 380 + 62 * ops, range(2, 9))
            if s is not None and s[0] >= 12:
                results.append((s[0], -ops, w1, w2, s[1], s[2], s[4], s[5], [v]))
            # one extra ROT on the leg-2 cell
            w3 = w2 // 3 + (w2 % 3) * 3 ** 9
            s = score(w1, w3, 380 + 62 * (ops + 1), range(2, 9))
            if s is not None and s[0] >= 12:
                results.append((s[0], -(ops + 1), w1, w3, s[1], s[2], s[4], s[5],
                                [v, None]))
    results.sort(key=lambda r: (r[0], r[1]), reverse=True)
    print("candidates with live>=12: %d" % len(results))
    seen = set()
    shown = 0
    for r in results:
        key = (r[0], r[1], r[4], tuple(r[5]))
        if key in seen:
            continue
        seen.add(key)
        print("  live=%2d/16 ops=%2d W1=%5d W2=%5d K=%d dead=%s addr=[%d..%d] leg2=%s"
              % (r[0], -r[1], r[2], r[3], r[4], [hex(x) for x in r[5]],
                 r[6], r[7], r[8]))
        shown += 1
        if shown >= 30:
            break


if __name__ == "__main__":
    main()
