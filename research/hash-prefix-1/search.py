#!/usr/bin/env python3
"""BFS over the straight-line A-register algebra for L4.R0.hash-prefix-1.

The rung asks for one exact byte (epoch 0: 0x5e) and a halt, so the whole
problem is: reach a word A with A % 256 == target using the ops a
straight-line classic-Malbolge program can apply to A.

Ops modelled (matching docs/classic-malbolge-51-v0.md):
  CRZ at a fresh data cell q : A <- crazy(A, x(q)); cell q now holds A
  ROT at the cell holding A  : A <- rotate_right(A)   (10-trit word rotate)

x(q) is the post-encipher value of a prefix NOP cell, so the reachable
operand alphabet is exactly {xval(q) : q in 34..127}.
"""
ENC = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CODE_NOP = 68
T = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]  # T[d_trit][a_trit]


def codebyte(addr, code):
    b = (code - addr) % 94
    if b < 33:
        b += 94
    return b


def xval(addr):
    return ENC[codebyte(addr, CODE_NOP) - 33]


def trits(w):
    out = []
    for _ in range(10):
        out.append(w % 3)
        w //= 3
    return out


def untrits(ts):
    w = 0
    for i, t in enumerate(ts):
        w += t * 3 ** i
    return w


def crazy(a, d):
    ta, td = trits(a), trits(d)
    return untrits([T[td[i]][ta[i]] for i in range(10)])


def rotr(w):
    ts = trits(w)
    return untrits(ts[1:] + ts[:1])


def operands():
    """Distinct fresh-cell operand values, with one representative address each."""
    seen = {}
    for q in range(34, 128):
        v = xval(q)
        seen.setdefault(v, q)
    return seen


def bfs(target_mod256, max_depth=6):
    ops = operands()
    start = 0
    seen = {start: []}
    frontier = [start]
    hits = []
    for _ in range(max_depth):
        nxt = []
        for a in frontier:
            path = seen[a]
            cands = [(rotr(a), ("rot", None))] if path else []
            for v, q in ops.items():
                cands.append((crazy(a, v), ("crz", v)))
            for b, step in cands:
                if b in seen:
                    continue
                seen[b] = path + [step]
                nxt.append(b)
                if b % 256 == target_mod256:
                    hits.append((b, seen[b]))
        frontier = nxt
        if hits:
            break
    return hits, seen


if __name__ == "__main__":
    import sys
    target = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x5e
    hits, seen = bfs(target)
    print(f"reachable words within depth bound: {len(seen)}")
    for w, path in hits[:5]:
        print(f"A={w} (mod256={w % 256}) len={len(path)} path={path}")
