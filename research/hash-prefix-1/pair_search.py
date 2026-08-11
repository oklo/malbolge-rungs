#!/usr/bin/env python3
"""Can one straight-line program serve two epochs at once?

Epoch 0 feeds input byte 0x74 and wants 0x5e; epoch 1 feeds 0x62 and wants
0xc8.  A constant program cannot do both, so the program must be a function of
the input byte.  This BFS runs both epochs' A-registers in lockstep through the
same op sequence (IN, then CRZ with fresh-cell constants / ROT) and looks for a
pair state whose two words both hit their target mod 256.
"""
import sys
from search import crazy, rotr, operands

CASES = [(0x74, 0x5e), (0x62, 0xc8)]


def bfs(depth=3):
    ops = list(operands().items())
    start = tuple(b for b, _ in CASES)
    seen = {start: []}
    frontier = [start]
    for d in range(depth):
        nxt = []
        for st in frontier:
            path = seen[st]
            cands = []
            if path:
                cands.append((tuple(rotr(a) for a in st), ("rot", None)))
            for v, q in ops:
                cands.append((tuple(crazy(a, v) for a in st), ("crz", v)))
            for ns, step in cands:
                if ns in seen:
                    continue
                seen[ns] = path + [step]
                nxt.append(ns)
                if all(ns[i] % 256 == CASES[i][1] for i in range(len(CASES))):
                    return ns, seen[ns], len(seen)
        frontier = nxt
        print(f"depth {d+1}: {len(seen)} distinct pair states", file=sys.stderr)
    return None, None, len(seen)


if __name__ == "__main__":
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    st, path, n = bfs(depth)
    print("hit:", st, path) if st else print(f"no hit within depth {depth}; {n} pair states explored")
