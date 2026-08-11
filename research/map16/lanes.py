#!/usr/bin/env python3
"""L2.FM3.xor51-map16: spaced-walk table search.

Architecture is cov48/map12-low's data-dispatch table (see
docs/attempts/2026-08-10-claude-map12-low.md) with that record's item 2 --
"the K CRAZYs need not be consecutive" -- actually implemented.

    IN                  A = b
    CRZ W1, CRZ W2      A = (b mod 243) + K0, parked in a cell
    MOVD on that cell   D = (b mod 243) + K0 + 1     <- the input IS the index
    walk of K CRZ ops separated by NOPs
                        lane b consumes cells base_b + o_1 .. base_b + o_K
                        where base_b = K0 + (b mod 243) and O is the same
                        offset pattern for every lane
    OUT, HALT

Two things differ from map12-low:

  * K0 is a multiple of 243, not 81: this rung's inputs reach 0xf6 = 246, so
    trits 0..4 must survive the dispatch and trit 5 must be crushed to a
    constant (the sixteen inputs stay distinct mod 243, so that is free).
  * lane windows are disjoint by construction.  Collisions happen exactly when
    an input difference lies in O - O, so O is chosen against the pairwise
    difference set of the reduced inputs.  With disjoint windows the joint
    table problem decomposes into sixteen independent 243-state DPs.

usage: lanes.py            sweep (K0, K, O) and report live/solved lanes
       lanes.py emit K0 K  print "addr byte" for the best table
"""
import sys

OPS = [4, 5, 23, 39, 40, 62, 68, 81]
INPUTS = [0x02, 0x06, 0x09, 0x30, 0x82, 0x6f, 0xa7, 0xc0,
          0xc5, 0xf6, 0x1c, 0x87, 0xf0, 0x2d, 0x4a, 0x85]
TARGETS = [b ^ 0x51 for b in INPUTS]
RED = [b % 243 for b in INPUTS]
assert len(set(RED)) == 16

T = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]          # T[d][a]


def crazy_word(a, d):
    o, f = 0, 1
    for _ in range(10):
        o += T[d % 3][a % 3] * f
        a //= 3
        d //= 3
        f *= 3
    return o


def legal_byte(addr, op):
    b = (op - addr) % 94
    return b + 94 if b < 33 else b


def cands(addr):
    return [legal_byte(addr, op) for op in OPS]


def high_part(K0, K):
    """Trits 5..9 after K crazy layers with operands < 243 (their high trits
    are 0), i.e. the part of the accumulator no table byte can touch."""
    h = K0 // 243
    for _ in range(K):
        n, f = 0, 1
        for _i in range(5):
            n += T[0][h % 3] * f
            h //= 3
            f *= 3
        h = n
    return h * 243


DIFFS = {abs(a - b) for a in RED for b in RED if a != b}


def offsets(K, limit=400):
    """K offsets, pairwise differences avoiding every input difference."""
    out = []

    def rec(cur):
        if len(cur) == K:
            out.append(list(cur))
            return True
        start = cur[-1] + 1 if cur else 1
        for o in range(start, limit):
            if all((o - c) not in DIFFS for c in cur):
                cur.append(o)
                if rec(cur):
                    return True
                cur.pop()
        return False

    rec([])
    return out[0] if out else None


def lane_dp(base, O, start, want_low):
    """Reachability of want_low over the K cells base+o, 8 bytes each.
    Returns the chosen byte list or None."""
    reach = {start: None}
    for o in O:
        nxt = {}
        for st, hist in reach.items():
            for byte in cands(base + o):
                v = crazy_word(st, byte) % 243
                if v not in nxt:
                    nxt[v] = (hist, byte)
        reach = nxt
    if want_low not in reach:
        return None
    chain, node = [], reach[want_low]
    while node is not None:
        chain.append(node[1])
        node = node[0]
    return chain[::-1]


def evaluate(K0, K, O):
    H = high_part(K0, K)
    live, sol = 0, {}
    for br, tgt in zip(RED, TARGETS):
        want = (tgt - H) % 256
        if want > 242:
            continue
        live += 1
        chain = lane_dp(K0 + br, O, br, want)
        if chain:
            sol[br] = chain
    return H, live, sol


def sweep():
    best = None
    for K0 in range(243, 3646, 243):
        for K in range(2, 9):
            O = offsets(K)
            if O is None:
                continue
            if K0 + max(RED) + O[-1] >= 4096:
                continue
            H, live, sol = evaluate(K0, K, O)
            if live == 0:
                continue
            print(f"K0={K0:5d} K={K} H%256={H % 256:3d} span={O[-1]:3d} "
                  f"live={live:2d}/16 solved={len(sol):2d}/16 O={O}")
            if best is None or len(sol) > best[0]:
                best = (len(sol), K0, K, O)
    print("best:", best)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "emit":
        K0, K = int(sys.argv[2]), int(sys.argv[3])
        O = offsets(K)
        H, live, sol = evaluate(K0, K, O)
        sys.stderr.write(f"K0={K0} K={K} O={O} live={live} solved={len(sol)}\n")
        for br, chain in sorted(sol.items()):
            for o, byte in zip(O, chain):
                print(K0 + br + o, byte)
    else:
        sweep()
