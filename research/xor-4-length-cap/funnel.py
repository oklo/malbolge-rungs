#!/usr/bin/env python3
"""Settle the open question left by 2026-08-11-claude-xor-2-multicase.md item 1:

After a dispatch walk, D is input-dependent (D = b + delta, 256 consecutive
addresses).  Only MOVD writes D, and MOVD does D = m[D] (+1 from the
post-increment).  So a "funnel" is a fixed number H of MOVDs whose composition
maps every source address in the polluted range to one common address.

Program bytes are 33..126, so one hop always lands in 34..127 -- exactly 94
consecutive addresses, i.e. one full residue system mod 94.  A byte v is
loader-legal at address a iff (v+a)%94 is an opcode, so each address has exactly
8 legal values, hence 8 possible hop targets.

This is a pure reachability question on a 94-node graph.  Model it exactly.
"""
OPS = {4, 5, 23, 39, 40, 62, 68, 81}
def code_of(v, a): return (v + a) % 94
def valid_bytes(a): return [v for v in range(33, 127) if code_of(v, a) in OPS]
def targets(a): return sorted(v + 1 for v in valid_bytes(a))   # 8 addrs in 34..127

LO, HI = 34, 127                      # every reachable hop target

def bfs(p):
    """Levels of the funnel tree rooted at fixed point p, over 34..127."""
    assert p in targets(p), "p is not a fixed point"
    level = {p: 0}
    frontier = [p]
    while frontier:
        nxt = []
        for a in range(LO, HI + 1):
            if a in level: continue
            for t in targets(a):
                if t in level and level[t] == level[frontier[0]]:
                    pass
        # plain BFS by level
        nxt = [a for a in range(LO, HI + 1)
               if a not in level and any(t in level for t in targets(a))]
        if not nxt: break
        d = max(level.values()) + 1
        for a in nxt: level[a] = d
        frontier = nxt
    return level

def main():
    fixed = [p for p in range(LO, HI + 1) if p in targets(p)]
    print(f"fixed points p with m[p] = p-1 legal: {fixed}")
    best = None
    for p in fixed:
        lv = bfs(p)
        cov = len(lv)
        H = max(lv.values())
        print(f"  p={p:3d}  covered {cov}/94 of 34..127, depth {H}")
        if best is None or (cov, -H) > (best[1], -best[2]):
            best = (p, cov, H, lv)
    if best is None:
        print("NO FIXED POINT -> no funnel of any depth.")
        return
    p, cov, H, lv = best
    print(f"\nbest root p={p}: {cov}/94 covered, max depth {H}")
    if cov < 94:
        missing = [a for a in range(LO, HI+1) if a not in lv]
        print(f"MISSING {len(missing)}: {missing}")
    # hop-1 reachability from the polluted source range: every source address
    # a (anywhere in the program) must have a legal byte pointing into the tree.
    bad = [a for a in range(0, 256) if not any(t in lv for t in targets(a))]
    print(f"source addresses 0..255 with no legal hop into the tree: {len(bad)}")
    # counting bound quoted in the xor-2 record, verified here
    print("\n-- counting check --")
    from collections import Counter
    c = Counter()
    for a in range(0, 94):
        for t in targets(a): c[t] += 1
    print("each hop target serves exactly", set(c.values()), "of the 94 source residues")
    print("=> a one-hop funnel over all 94 residues needs >= ceil(94/8) =",
          -(-94 // 8), "distinct landing cells")
    print("=> and each landing cell must hold the SAME value v*, but a fixed v*")
    print("   is legal at exactly 8 addresses in any 94-address window. 8 < 12.")

main()
