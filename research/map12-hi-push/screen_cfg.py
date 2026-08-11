"""Screen every separating dispatch config against the landing-band condition.

Necessary condition derived in ubound.py / jreach.py:
  - a lane whose target lies OUTSIDE the 55-byte hole 0x9a..0xd0 can always be
    realised by a ROT-seeded tail, from any landing.
  - a lane whose target lies INSIDE the hole cannot use ROT at all, so it must
    be realised as CRAZY^n(J(x)); that needs J(x) in a band.
map12-hi has exactly four in-hole lanes: 0xe0->0xb1, 0x90->0xc1, 0x9c->0xcd,
0xf9->0xa8 -- precisely the lanes every prior attempt found dead.
"""
from __future__ import annotations
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from research.map12hi import base  # noqa: E402
from jreach import crazy_reach  # noqa: E402

INPUTS = [0xA5, 0xE0, 0x90, 0x9C, 0x84, 0xA1, 0xBD, 0xC8, 0xBE, 0xF9, 0x86, 0xDD]
TGT = {x: x ^ 0x51 for x in INPUTS}
base.INPUTS = INPUTS
base.TGT = TGT
HOLE = set(range(0x9A, 0xD1))
HARD = [x for x in INPUTS if TGT[x] in HOLE]

DEPTH = int(sys.argv[1]) if len(sys.argv) > 1 else 5

cfgs = base.enum_configs()
print(f"{len(cfgs)} separating configs; hard lanes {[hex(x) for x in HARD]}")

cache = {}
def ok(J, t):
    key = (J, t)
    if key not in cache:
        cache[key] = t in crazy_reach(J, DEPTH)
    return cache[key]

rows = []
for i, (cps, ts, J) in enumerate(cfgs):
    live = [x for x in HARD if ok(J[x], TGT[x])]
    rows.append((len(live), i, cps, ts, J, live))

rows.sort(key=lambda r: -r[0])
best = rows[0][0]
print(f"max hard lanes satisfiable by any config: {best}/{len(HARD)}")
from collections import Counter
print("distribution:", dict(Counter(r[0] for r in rows)))
for n, i, cps, ts, J, live in rows[:12]:
    vs = sorted(J.values())
    print(f"  cfg{i:3d} hard-live={n} cps={cps} ts={ts} landings={vs} "
          f"live={[hex(x) for x in live]}")
