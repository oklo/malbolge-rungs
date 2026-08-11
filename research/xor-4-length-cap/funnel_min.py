#!/usr/bin/env python3
"""How much does the D-funnel of funnel.py actually cost?

The cost is the number of program cells it pins, because those cells are also
operand-table cells for the dispatch.  A source address a hops to t iff
(t-1+a) % 94 is an opcode, i.e. a lies in cover(t) -- a translate of the opcode
set, 8 residues of 94.  So the hop-1 landing set must be a set cover of Z/94 by
translates of OPS (>= ceil(94/8) = 12 cells), and every landing cell then needs
an outgoing edge into the tree rooted at the fixed point p.
"""
OPS = {4,5,23,39,40,62,68,81}
LO, HI = 34, 127
def valid_bytes(a): return [v for v in range(33,127) if (v+a)%94 in OPS]
def out_targets(a): return sorted(v+1 for v in valid_bytes(a))
def cover(t):  return frozenset(a for a in range(94) if t in out_targets(a))

cells = list(range(LO, HI+1))
covs = {t: cover(t) for t in cells}
assert all(len(c)==8 for c in covs.values())

best = None
for first in cells:                       # greedy set cover, restarted on each seed
    chosen=[first]; have=set(covs[first])
    while len(have) < 94:
        t = max((t for t in cells if t not in chosen), key=lambda t: len(covs[t]-have))
        chosen.append(t); have |= covs[t]
    if best is None or len(chosen) < len(best): best = sorted(chosen)
print(f"min hop-1 landing set: {len(best)} cells (information bound 12) -> {best}")


# --- close the cover into a tree, using the parent map of a BFS from p -------
fixed = [p for p in cells if p in out_targets(p)]
out = []
for p in fixed:
    parent = {p: p}                       # p self-loops: m[p] = p-1
    frontier = [p]
    while frontier:
        nxt = []
        for a in cells:
            if a in parent: continue
            for t in out_targets(a):
                if t in parent: parent[a] = t; nxt.append(a); break
        frontier = nxt
    depth = {}
    def dep(a):
        d = 0
        while a != p: a = parent[a]; d += 1
        return d
    T = set([p])
    for t in best:                        # add each landing cell and its path
        a = t
        while a not in T: T.add(a); a = parent[a]
    h = max(dep(t) for t in best)
    out.append((len(T), h, p, sorted(T)))
out.sort()
n,h,p,T = out[0]
print(f"\nsmallest closed funnel: {n} pinned cells, root p={p}, tree depth {h}")
print(f"  {h+1} MOVDs collapse every polluted D onto cell {p}; m[p]={p-1} self-loops")
print(f"  pinned: {T}")
print(f"  a 256-byte program has ~225 non-code cells; the funnel costs {n} of them")
