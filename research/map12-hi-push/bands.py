"""Structure of the emittable-landing bands, and the full-reach landings."""
from __future__ import annotations
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from jreach import crazy_reach  # noqa: E402

HI = int(sys.argv[1]) if len(sys.argv) > 1 else 1400
DEPTH = int(sys.argv[2]) if len(sys.argv) > 2 else 5

reach = {J: crazy_reach(J, DEPTH) for J in range(HI)}

def runs(vals):
    vals = sorted(vals); out = []
    for v in vals:
        if out and v == out[-1][1] + 1:
            out[-1][1] = v
        else:
            out.append([v, v])
    return [(a, b) for a, b in out]

for name, t in (("0xb1 (0xe0)", 0xB1), ("0xc1 (0x90)", 0xC1),
                ("0xcd (0x9c)", 0xCD), ("0xa8 (0xf9)", 0xA8)):
    good = [J for J in range(HI) if t in reach[J]]
    print(f"{name}: {len(good)} landings, runs={runs(good)}")

full = [J for J in range(HI) if len(reach[J]) == 256]
print(f"\nlandings with FULL 256-byte reach: {len(full)} runs={runs(full)}")
by_size = {}
for J in range(HI):
    by_size.setdefault(len(reach[J]), []).append(J)
print("\n|reach| histogram:")
for s in sorted(by_size):
    print(f"  {s:4d} bytes : {len(by_size[s]):5d} landings  runs(first few)={runs(by_size[s])[:6]}")
