"""Rank map12-hi dispatch configs by *tail-placement window*, not landing size.

Structural observation this attempt is built on
-----------------------------------------------
In the two-stage dispatch family (research/map12hi/base.py) a lane's tail
starts at ``L = T + 1`` where ``T = mem[p+1]`` and ``p = mem[q]`` are both
*source-valid bytes of the cells they sit in*.  Source-valid bytes are
printable, so ``p, T in [33, 126]``.  Therefore:

    every lane's tail body must start in the address window [34, 127],
    and its operand trail starts at d0 = p + 2 in [35, 128].

That window is fixed by the encoding, not by the search.  The only thing a
dispatch config changes is *how much of that window is free* -- cells below
the lowest landing (and outside the fixed prefix/reserved cells) are
assignable; cells from a landing up to its station are base NOPs.

So the quantity that governs whether twelve private tails can coexist is

    W(config) = |{c in [34, 127] : c is free in the geometry}|

and the prior recorded attempts ordered configs *smallest-landing-first*
(2026-08-09) or took config 0 (2026-08-10), which is exactly the ordering
that minimises W.  This script inverts that ordering.

Usage:  python3 research/map12-hi/window_analysis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from research.map12hi import base, geometry  # noqa: E402

INPUTS = [0xA5, 0xE0, 0x90, 0x9C, 0x84, 0xA1, 0xBD, 0xC8, 0xBE, 0xF9, 0x86, 0xDD]
TARGETS = {value: value ^ 0x51 for value in INPUTS}
base.INPUTS = INPUTS
base.TGT = TARGETS
geometry.INPUTS = INPUTS
geometry.TGT = TARGETS

WINDOW_LO, WINDOW_HI = 34, 127


def free_window(geo) -> list[int]:
    return [c for c in range(WINDOW_LO, WINDOW_HI + 1) if geo.zone(c) == "free"]


def main() -> int:
    configs = base.enum_configs()
    rows = []
    for index, (cps, operands, landings) in enumerate(configs):
        values = sorted(landings.values())
        geo = geometry.GeoV2(cps, operands, landings, frozenset(), ())
        if not geo.ok:
            rows.append((index, values, None, cps, operands))
            continue
        rows.append((index, values, len(free_window(geo)), cps, operands))

    rows.sort(key=lambda r: (-(r[2] or -1), r[0]))
    print(f"{len(configs)} separating configs")
    print(f"{'idx':>5} {'W':>4} {'minJ':>5} {'maxJ':>5}  landings")
    for index, values, width, cps, operands in rows:
        print(f"{index:5d} {str(width):>4} {values[0]:5d} {values[-1]:5d}  {values}")
    widths = [r[2] for r in rows if r[2] is not None]
    print(f"\nW distribution: max={max(widths)} min={min(widths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
