#!/usr/bin/env python3
"""Beam search over the offset pattern O for L2.FM3.xor51-map16.

research/map16/lanes.py shows that with disjoint lane windows the sixteen
lanes decouple, so the only shared object left is the offset pattern O: the
positions of the CRZ instructions inside the NOP-padded walk.  O decides, for
every lane simultaneously, which eight loader-valid bytes each table cell may
hold (the candidate set is a function of the address, and the address is
base_b + o).  Reachability of a lane's required low-5-trit value is therefore
a function of O, and O is what this searches.

The DP is a prefix computation -- reachable sets after o_1..o_j do not depend
on o_{j+1} -- so the search is a beam over prefixes, scored by how many lanes
are still alive times how much reach they have.

usage: search.py K0 K [beam] [limit]
"""
import sys
from lanes import (INPUTS, TARGETS, RED, DIFFS, OPS, crazy_word, legal_byte,
                   cands, high_part)

CR = {}


def step(states, addr):
    """states: frozenset of low-5 values -> reachable after one CRZ at addr."""
    key = (states, addr)
    got = CR.get(key)
    if got is None:
        byts = cands(addr)
        got = frozenset(crazy_word(s, b) % 243 for s in states for b in byts)
        CR[key] = got
    return got


def run(K0, K, beam=400, limit=None):
    H = high_part(K0, K)
    want, live = [], []
    for br, tgt in zip(RED, TARGETS):
        w = (tgt - H) % 256
        want.append(w if w <= 242 else None)
        live.append(w <= 242)
    nlive = sum(live)
    if limit is None:
        limit = min(900, 4095 - K0 - max(RED))
    sys.stderr.write(f"K0={K0} K={K} H%256={H % 256} live={nlive}/16 limit={limit}\n")

    # beam entries: (offsets, tuple of per-lane frozensets)
    cur = [([], tuple(frozenset([br]) for br in RED))]
    for depth in range(K):
        nxt = {}
        for offs, sets in cur:
            lo = offs[-1] + 1 if offs else 1
            for o in range(lo, limit + 1):
                if any((o - c) in DIFFS for c in offs):
                    continue
                ns = tuple(step(s, K0 + br + o) for s, br in zip(sets, RED))
                if depth == K - 1:
                    score = sum(1 for i in range(16)
                                if live[i] and want[i] in ns[i])
                else:
                    score = sum(len(s) for i, s in enumerate(ns) if live[i])
                nxt[tuple(offs + [o])] = (score, ns)
        ranked = sorted(nxt.items(), key=lambda kv: -kv[1][0])[:beam]
        cur = [(list(k), v[1]) for k, v in ranked]
        best = ranked[0]
        sys.stderr.write(f"  depth {depth + 1}: best score {best[1][0]} "
                         f"O={list(best[0])}\n")
    o, (score, sets) = ranked[0][0], ranked[0][1]
    return score, list(o)


if __name__ == "__main__":
    K0, K = int(sys.argv[1]), int(sys.argv[2])
    beam = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    lim = int(sys.argv[4]) if len(sys.argv) > 4 else None
    score, O = run(K0, K, beam, lim)
    print(f"K0={K0} K={K} solved={score}/16 O={O}")
