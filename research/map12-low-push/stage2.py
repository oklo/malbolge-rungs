#!/usr/bin/env python3
"""Stage 2: enumerate the buildable (K0, K-parity, start_t4) configurations and
measure how fast a lane's reachable trit-0..4 set grows when the walk's address
residues are free (which NOP-spacing makes them).

K0 = 243*hi_src + 81*start_t4   (K0 = 81*m, m = 3*hi_src + start_t4)
hi_final trit j = (min(hi_src trit j, 1) + K) mod 2
H = 243 * hi_final ;  out = (H + Lstar) mod 256 ; Lstar in [0,242] required.
"""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lowmodel import *

import os
CODE_FLOOR = int(os.environ.get("MLP_FLOOR", "700"))
PROG_CAP = 4096


def trits(v, n=5):
    return [(v // 3 ** j) % 3 for j in range(n)]


def configs(CODE_FLOOR=CODE_FLOOR):
    out = []
    for hi_src in range(0, 17):
        for start_t4 in (0, 1, 2):
            K0 = 243 * hi_src + 81 * start_t4
            if K0 < CODE_FLOOR or K0 > PROG_CAP - 400:
                continue
            for par in (0, 1):
                hi_final = sum(((min(t, 1) + par) % 2) * 3 ** j
                               for j, t in enumerate(trits(hi_src)))
                H = 243 * hi_final
                req = lane_requirements(H)
                if req is None:
                    continue
                t4s = sorted({r[0] for r in req.values()})
                # start trit4 must be able to reach every needed t4
                if start_t4 in (0, 1):
                    reach_t4 = {(start_t4 + par) % 2} if True else None
                    # deterministic: final t4 = (start + K) mod 2 for any K>=0
                    ok = set(t4s) <= reach_t4
                else:
                    ok = True  # start 2 can hold 2 or drop to 0/1 (K >= 2)
                if not ok:
                    continue
                out.append(dict(K0=K0, hi_src=hi_src, start_t4=start_t4,
                                par=par, hi_final=hi_final, H=H,
                                Lstar={b: 81 * v[0] + v[1] for b, v in req.items()},
                                t4s=t4s))
    return out


CFG = configs()
print("buildable configs (K0 >= %d):" % CODE_FLOOR)
for c in CFG:
    print("  K0=%-5d start_t4=%d K_parity=%d  H=%-6d H%%256=%-3d t4needed=%s"
          % (c["K0"], c["start_t4"], c["par"], c["H"], c["H"] % 256, c["t4s"]))
print("  total: %d" % len(CFG))
print()

# --- saturation probe: free residues, one lane -------------------------------
TR = [[0] * 243 for _ in range(243)]
for a in range(243):
    for v in range(243):
        o, f = 0, 1
        x, y = a, v
        for _ in range(5):
            o += CR[y % 3][x % 3] * f
            x //= 3
            y //= 3
            f *= 3
        TR[a][v] = o

BY = [legal_bytes(u) for u in range(94)]

print("reachable-set growth for start state s, walking residues u1,u2,... :")
for start in (8, 8 + 81, 8 + 162):
    cur = {start}
    sizes = []
    for step in range(6):
        u = (37 * step + 11) % 94          # an arbitrary residue sequence
        cur = {TR[a][v] for a in cur for v in BY[u]}
        sizes.append(len(cur))
    print("   start=%3d -> sizes %s (of 243)" % (start, sizes))
