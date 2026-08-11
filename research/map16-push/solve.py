#!/usr/bin/env python3
"""Fast model-only (P, s) search, hard lanes first.

Per-lane feasibility only: the walk pattern is collision free, so the lanes are
independent and each is a 243-state backward DP over its K cells.  The three
lanes whose L* >= 162 must hold trit4 = 2 all the way, i.e. every operand must
be a byte >= 81; they are checked first because they are what fails.
"""
import sys, random
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import build as B
from model import INPUTS, legal_bytes  # noqa

CRT = {v: [B.cr5(a, v) for a in range(243)] for v in range(33, 127)}
LEG = {r: legal_bytes(r) for r in range(94)}


def lane_ok(b, P, s, want):
    addrs = [(B.ADDR[b] + 1 + s + p) % 94 for p in P]
    back = {want}
    for i in range(len(P) - 1, -1, -1):
        vals = LEG[addrs[i]]
        nb = set()
        for v in vals:
            t = CRT[v]
            for a in range(243):
                if t[a] in back:
                    nb.add(a)
        back = nb
        if not back:
            return False
    return (B.ADDR[b] % 243) in back


def evaluate(P, s, req):
    hard = [b for b in req if req[b][2] and req[b][0] >= 162]
    rest = [b for b in req if req[b][2] and req[b][0] < 162]
    for b in hard:
        if not lane_ok(b, P, s, req[b][0]):
            return None
    n = len(hard)
    miss = []
    for b in rest:
        if lane_ok(b, P, s, req[b][0]):
            n += 1
        else:
            miss.append(b)
    return n, miss


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    req = B.requirements(K)
    live = sum(1 for b in req if req[b][2])
    print("K=%d live=%d hard=%s" % (K, live,
          [hex(b) for b in req if req[b][2] and req[b][0] >= 162]), flush=True)
    rnd = random.Random(seed)
    D = B.DIFFS
    best = None
    tried = 0
    while tried < 4000:
        P = [0]
        for _ in range(K - 1):
            for _ in range(300):
                x = rnd.randrange(P[-1] + 1, P[-1] + cap)
                if all((x - p) not in D for p in P):
                    P.append(x); break
            else:
                break
        if len(P) != K:
            continue
        for s in range(94):
            tried += 1
            r = evaluate(P, s, req)
            if r is None:
                continue
            n, miss = r
            if best is None or n > best[0]:
                best = (n, list(P), s, miss)
                print("  %2d/16 P=%s s=%d miss=%s"
                      % (n, P, s, [hex(x) for x in miss]), flush=True)
                if n >= live:
                    raise SystemExit(0)
    print("done, best:", best)
