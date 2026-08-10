"""Build a maximal *partial* map12-hi program: satisfy as many lanes as possible.

The two prior attempts on this rung reported no candidate at all, because the
joint search is all-or-nothing: it only emits a program when all twelve lanes
are simultaneously routable.  That throws away a verifiable datum.  A program
that dispatches all twelve inputs correctly and emits the right byte for k of
them is a real, natively checkable measurement of how far the two-stage
family actually gets on this rung.

Strategy: build the geometry exactly as the full search does, then run the
joint assignment over the lanes with the option to *skip* a lane, keeping the
assignment that satisfies the most lanes.  Unsatisfied lanes still dispatch
and still terminate (their tail cells default to NOPs), they just emit the
wrong byte -- which is what a partial score means.

Usage: python3 research/map12-hi/partial_build.py [CONFIG] [NODE_BUDGET]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
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

PLAN_CAP = 400
PLAN_BUDGET = 400_000
BINARY = REPO / "target" / "release" / "malbolge-rungs"


def native_score(program: bytes, path: Path) -> tuple[int, list[str]]:
    path.write_bytes(program)
    correct = 0
    detail = []
    for value in INPUTS:
        run = subprocess.run(
            [str(BINARY), "execute", "--program", str(path),
             "--input-hex", f"{value:02x}"],
            capture_output=True, check=False, timeout=60,
        )
        try:
            report = json.loads(run.stdout)
        except Exception:
            detail.append(f"{value:#04x}:parse-error")
            continue
        got = report.get("output_hex")
        status = str(report.get("status"))
        if got == f"{TARGETS[value]:02x}" and "alt" in status:
            correct += 1
            detail.append(f"{value:#04x}:ok")
        else:
            detail.append(f"{value:#04x}:{got}/{status}")
    return correct, detail


def build(config_index: int, node_budget: int):
    configs = base.enum_configs()
    cps, operands, landings = configs[config_index]
    best_overall = (0, None, None)

    pinned = os.environ.get("MAP12HI_OFFS")
    geoms = ([(frozenset(), tuple(int(v) for v in pinned.split(",") if v != ""))]
             if pinned is not None
             else geometry.geometries_for(sorted(landings.values())))
    for mask, offs in geoms:
        geo = geometry.GeoV2(cps, operands, landings, mask, offs)
        if not getattr(geo, "ok", False) or not hasattr(geo, "base"):
            continue

        counts = {}
        for x in INPUTS:
            counts[x] = sum(1 for _ in base.tail_plans(
                geo, x, {}, cap=64, attempt_budget=PLAN_BUDGET))
        live = [x for x in INPUTS if counts[x] > 0]
        print(f"cfg{config_index} mask={sorted(mask)} offs={offs} "
              f"individually-live={len(live)}/12 "
              f"counts={ {hex(k): v for k, v in counts.items()} }", flush=True)
        if len(live) < best_overall[0]:
            continue

        order = sorted(live, key=lambda x: counts[x])
        best = [0, None]
        nodes = [0]

        def backtrack(index: int, assignment: dict, satisfied: int):
            if nodes[0] > node_budget:
                return
            if satisfied > best[0]:
                best[0] = satisfied
                best[1] = dict(assignment)
                print(f"  satisfied={satisfied} nodes={nodes[0]}", flush=True)
            if index == len(order):
                return
            if satisfied + (len(order) - index) <= best[0]:
                return
            x = order[index]
            plans = list(base.tail_plans(geo, x, assignment, cap=PLAN_CAP,
                                         attempt_budget=PLAN_BUDGET))
            for delta in plans:
                nodes[0] += 1
                if nodes[0] > node_budget:
                    return
                updated = dict(assignment)
                updated.update(delta)
                backtrack(index + 1, updated, satisfied + 1)
            backtrack(index + 1, assignment, satisfied)

        backtrack(0, {}, 0)
        if best[1] is None:
            continue
        program = base.assemble(geo, best[1])
        if best[0] > best_overall[0]:
            best_overall = (best[0], program, (sorted(mask), offs))
            print(f"  -> best so far claimed={best[0]} geometry={best_overall[2]}",
                  flush=True)
    return best_overall


def main() -> int:
    config_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    node_budget = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
    started = time.monotonic()
    claimed, program, geo_key = build(config_index, node_budget)
    if program is None:
        print("no program built")
        return 1
    out = REPO / "docs" / "attempts" / os.environ.get("MAP12HI_OUT", "2026-08-10-claude-map12-hi.best.mal")
    correct, detail = native_score(program, out)
    print(f"cfg{config_index} geometry={geo_key} claimed={claimed} "
          f"native={correct}/12 len={len(program)} "
          f"wall={time.monotonic() - started:.1f}s")
    print("  " + "  ".join(detail))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
