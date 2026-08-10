"""Test the one lever the reachable-set data points at: a second ROT.

`ROT` sets `a = rot(mem[d])` -- it *overwrites* the accumulator with a
function of a cell value, so it severs the dependence on the landing address
J(x) entirely.  The stock tail catalog (`research/map12hi/geometry.SHAPES`)
allows at most one ROT, which is why every lane's reachable-output set is an
orbit anchored at J(x) and why low-J lanes top out at 209 of 256 bytes.

This script widens the catalog to allow two ROTs (and a MOVD between them)
and re-asks whether the lanes that the necessary-condition screen proved dead
can now emit their targets.

Usage: python3 research/map12-hi/tworot.py [CONFIG ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from research.map12hi import base, geometry  # noqa: E402
from tools.hell_lite.ops import CRAZY, MOVD, ROT  # noqa: E402

WIDE_SHAPES = []
for movd1 in (0, 1):
    for rot1 in (0, 1):
        for movd2 in (0, 1):
            for rot2 in (0, 1):
                for n in range(0, 5):
                    if rot2 and not rot1:
                        continue
                    if not (rot1 or rot2) and n == 0:
                        continue
                    WIDE_SHAPES.append(
                        [MOVD] * movd1 + [ROT] * rot1 + [MOVD] * movd2
                        + [ROT] * rot2 + [CRAZY] * n)

geometry.SHAPES[:] = WIDE_SHAPES

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "map12hi_screen", Path(__file__).with_name("screen.py"))
_screen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_screen)
INPUTS, TARGETS, lane_can_emit = _screen.INPUTS, _screen.TARGETS, _screen.lane_can_emit


def main() -> int:
    indices = [int(a) for a in sys.argv[1:]] or [0]
    configs = base.enum_configs()
    for index in indices:
        cps, operands, landings = configs[index]
        for offs in [(), (4,), (0, 6)]:
            geo = geometry.GeoV2(cps, operands, landings, frozenset(), offs)
            if not getattr(geo, "ok", False) or not hasattr(geo, "base"):
                continue
            live = []
            for x in INPUTS:
                ok, nodes = lane_can_emit(geo, x, TARGETS[x])
                live.append((hex(x), ok))
            print(f"cfg{index} offs={offs} shapes={len(geometry.SHAPES)} "
                  f"live={sum(1 for _, ok in live if ok)}/12 "
                  f"dead={[n for n, ok in live if not ok]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
