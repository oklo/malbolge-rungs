#!/usr/bin/env python3
"""Prefix-chain search for the map16 dispatch words W1, W2.

The 2026-08-10 record died here: its chain search had no notion of *which cell*
each op acts on, so leg 2 came back as a rotation of W1 in the same cell and the
two operands could not coexist.  This version models the cell explicitly.

Effective op set (see docs/attempts/2026-08-11-claude-push-map16.md):

  * every prefix cell in 34..127 is a NOP in the initial sled, so by the time D
    reaches it the cell holds xval(q) = ENC[codebyte(q,NOP)-33].  xval is a
    bijection on 34..127, so "CRZ with byte v" is available at exactly one cell,
    for every printable v -- and therefore every CRZ in the chain must use a
    *distinct* operand byte.
  * ROT is re-navigated to the cell the previous op wrote, so it rotates the
    accumulator: a <- rot_r(a).
  * leg 2 must open with a CRZ into a fresh cell, otherwise it would rotate the
    cell holding W1 and destroy it.

So the search is a shortest path in the graph
    a -> rot_r(a)            (rotate the current cell)
    a -> crazy(a, v)         (crazy against a fresh cell holding v)
from 0 to W1, then from W1 to W2 with a crazy first.
"""
import sys
from collections import deque

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from model import crazy, rot_r, xval, trits, from_trits, PAIRS, M  # noqa: E402

WORDS = 59049
BYTES = list(range(33, 127))

# precompute transition tables ------------------------------------------------
ROT = [w // 3 + (w % 3) * 3 ** 9 for w in range(WORDS)]


def crazy_table(v):
    """crazy(a, v) for all a, as a list."""
    vt = trits(v)
    tab = [0] * WORDS
    for a in range(WORDS):
        at = trits(a)
        tab[a] = from_trits([[[1, 0, 0], [1, 0, 2], [2, 2, 1]][vt[i]][at[i]]
                             for i in range(10)])
    return tab


def crazy_apply(a, v):
    return crazy(a, v)


def bfs(src, crazy_first_only=False, limit=6):
    """shortest chain length from src; move = ('rot',) or ('crz', v)."""
    dist = bytearray([255]) * WORDS
    prev = [None] * WORDS
    dist[src] = 0
    frontier = [src]
    depth = 0
    while frontier and depth < limit:
        depth += 1
        nxt = []
        for a in frontier:
            if not (crazy_first_only and depth == 1):
                r = ROT[a]
                if dist[r] == 255:
                    dist[r] = depth
                    prev[r] = (a, ("rot",))
                    nxt.append(r)
            for v in BYTES:
                w = crazy(a, v)
                if dist[w] == 255:
                    dist[w] = depth
                    prev[w] = (a, ("crz", v))
                    nxt.append(w)
        frontier = nxt
    return dist, prev


def path(prev, src, dst):
    ops = []
    cur = dst
    while cur != src:
        p, op = prev[cur]
        ops.append(op)
        cur = p
    return ops[::-1]


# ------------------------------------------------------------- word constraints
def word_candidates(gspec):
    """gspec: list of 10 desired g-triples (or None = any).  Returns the list of
    (W1, W2) pairs realising it, as (w1_trits, w2_trits) products."""
    per_trit = []
    for g in gspec:
        opts = PAIRS[g]
        per_trit.append(opts)
    return per_trit


def enumerate_words(per_trit):
    """all (W1, W2) pairs; per_trit[i] is a list of (w1,w2) trit pairs."""
    w1s = [0]
    w2s = [0]
    out = [(0, 0)]
    for i, opts in enumerate(per_trit):
        f = 3 ** i
        nxt = []
        for a, b in out:
            for x, y in opts:
                nxt.append((a + x * f, b + y * f))
        out = nxt
    return out


def gspec_for(K0, g4, g0_3=(0, 1, 2), crush=None):
    """desired per-trit dispatch maps.
    trits 0..3: g0_3 (default identity), trit 4: g4,
    trit 5: crush to K0's trit 5, trits 6..9: constant = K0's trits."""
    kt = trits(K0)
    spec = [tuple(g0_3)] * 4 + [tuple(g4)]
    # trit 5: g(0) = g(1) = kt[5]
    c5 = kt[5] if crush is None else crush
    opts5 = [g for g in PAIRS if g[0] == c5 and g[1] == c5]
    spec.append(opts5)
    for i in range(6, 10):
        spec.append([g for g in PAIRS if g[0] == kt[i]])
    return spec


def expand_spec(spec):
    """spec entries may be a single triple or a list; yield per_trit pair-lists."""
    per_trit = []
    for e in spec:
        if isinstance(e, tuple):
            per_trit.append(PAIRS[e])
        else:
            opts = []
            for g in e:
                opts.extend(PAIRS[g])
            per_trit.append(opts)
    return per_trit


def search(K0, g4, top=12, verbose=True):
    spec = gspec_for(K0, g4)
    per_trit = expand_spec(spec)
    pairs = enumerate_words(per_trit)
    if verbose:
        print("K0=%d g4=%s: %d (W1,W2) pairs" % (K0, g4, len(pairs)))
    dist0, prev0 = bfs(0, limit=6)
    cands = sorted({w1 for w1, _ in pairs if dist0[w1] < 255},
                   key=lambda w: dist0[w])
    if verbose:
        print("  reachable W1 candidates: %d (best dist %s)"
              % (len(cands), dist0[cands[0]] if cands else None))
    best = None
    for w1 in cands[:top]:
        compat = sorted({w2 for a, w2 in pairs if a == w1})
        d1, p1 = bfs(w1, crazy_first_only=True, limit=5)
        for w2 in compat:
            if d1[w2] == 255:
                continue
            cost = dist0[w1] + d1[w2]
            if best is None or cost < best[0]:
                leg1 = path(prev0, 0, w1)
                leg2 = path(p1, w1, w2)
                best = (cost, w1, w2, leg1, leg2)
        if best and best[0] <= dist0[cands[0]] + 1:
            break
    return best


if __name__ == "__main__":
    K0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2916
    g4 = tuple(int(x) for x in sys.argv[2]) if len(sys.argv) > 2 else (2, 2, 1)
    r = search(K0, g4)
    if r is None:
        print("no chain")
    else:
        cost, w1, w2, leg1, leg2 = r
        print("  W1=%d W2=%d total ops=%d" % (w1, w2, cost))
        print("  leg1:", leg1)
        print("  leg2:", leg2)
