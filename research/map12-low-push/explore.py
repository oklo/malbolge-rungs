#!/usr/bin/env python3
"""Stage 1: what the trit algebra allows before any search runs."""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lowmodel import *

print("inputs sorted:", [hex(x) for x in sorted(INPUTS)])
print("targets      :", {hex(b): hex(t) for b, t in sorted(TARGETS.items())})
print()
print("pairwise input differences (%d):" % len(DIFFS), sorted(DIFFS))
allowed = [d for d in range(1, 80) if d not in DIFFS]
print("ALLOWED walk gaps (<80):", allowed)
print()

print("frozen high part H = 243 * subset-of-{1,3,9,27,81}; which give all 12 lanes live?")
good = []
for mask in range(32):
    hi = sum(((mask >> j) & 1) * 3 ** j for j in range(5))
    H = 243 * hi
    req = lane_requirements(H)
    if req is None:
        continue
    t4s = sorted({v[0] for v in req.values()})
    good.append((hi, H, H % 256, t4s, req))
    print("  hi=%-4d H=%-6d H%%256=%-3d  t4 needed: %s%s" %
          (hi, H, H % 256, t4s, "   <-- uniform" if len(t4s) == 1 else ""))
print("total live-H options: %d of 32" % len(good))
