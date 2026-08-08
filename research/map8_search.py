"""Breadth-first search for the eight-lane XOR 0x51 finite map.

This is the map7b two-stage/merged-cluster builder extended to require both
0xa7 and 0xc0. The construction primitives are checked in beside this script,
so the search that produced the leaderboard artifact is reproducible.

Usage: python3 research/map8_search.py WORKER NWORKERS MAXSPLITS NODE_BUDGET [NOFFS] [MIN_CONFIG] [MINSPLITS]
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
WORK_DIR = Path(tempfile.gettempdir()) / "malbolge-rungs-map8"
WORK_DIR.mkdir(parents=True, exist_ok=True)

from research.map8 import base, geometry  # noqa: E402


INPUTS = [0x02, 0x06, 0x09, 0x30, 0x82, 0x6F, 0xA7, 0xC0]
TARGETS = {value: value ^ 0x51 for value in INPUTS}

# The imported functions read these module globals at execution time.
base.INPUTS = INPUTS
base.TGT = TARGETS
geometry.INPUTS = INPUTS
geometry.TGT = TARGETS


def native_check(program: bytes, worker: int) -> tuple[int, object | None]:
    candidate = WORK_DIR / f"map8-worker-{worker}.mal"
    candidate.write_bytes(program)
    binary = REPO / "target" / "debug" / "malbolge-rungs"
    correct = 0
    for value in INPUTS:
        run = subprocess.run(
            [
                str(binary),
                "execute",
                "--program",
                str(candidate),
                "--input-hex",
                f"{value:02x}",
            ],
            capture_output=True,
            check=False,
            timeout=30,
        )
        try:
            report = json.loads(run.stdout)
        except Exception:
            return correct, {"stdout": run.stdout.decode(), "stderr": run.stderr.decode()}
        if report.get("output_hex") == f"{TARGETS[value]:02x}" and "Halt" in str(
            report.get("status")
        ):
            correct += 1
        else:
            return correct, report
    return correct, None


def geometries_for(
    values: list[int],
    min_splits: int,
    max_splits: int,
    offsets: list[tuple[int, ...]],
):
    boundaries = geometry.splittable_boundaries(values)
    masks = sorted(
        (
            frozenset(combo)
            for count in range(min_splits, max_splits + 1)
            for combo in itertools.combinations(boundaries, count)
        ),
        key=len,
    )
    for mask in masks:
        for station_offsets in offsets:
            yield mask, station_offsets


def solve_config(
    config_index: int,
    cps,
    operands,
    landings,
    *,
    worker: int,
    min_splits: int,
    max_splits: int,
    node_budget: int,
    offsets: list[tuple[int, ...]],
):
    values = sorted(landings.values())
    rng = random.Random(config_index)
    for mask, station_offsets in geometries_for(values, min_splits, max_splits, offsets):
        geo = geometry.GeoV2(cps, operands, landings, mask, station_offsets)
        if not geo.ok:
            continue
        counts = {}
        for value in INPUTS:
            counts[value] = sum(1 for _ in base.tail_plans(geo, value, {}, cap=300))
            if counts[value] == 0:
                break
        if len(counts) != len(INPUTS) or any(count == 0 for count in counts.values()):
            continue

        order = sorted(INPUTS, key=lambda value: counts[value])
        print(
            f"[w{worker}] cfg{config_index} mask={sorted(mask)} offs={station_offsets} "
            f"minplans={order[0]:#x}:{counts[order[0]]}",
            flush=True,
        )
        solution = [None]
        nodes = [0]
        rejected_complete_layouts = [0]

        def backtrack(index: int, assignment: dict[int, int]) -> None:
            if solution[0] is not None or nodes[0] > node_budget:
                return
            if index == len(order):
                candidate = base.assemble(geo, assignment)
                if base.simulate_all(candidate)[0]:
                    solution[0] = dict(assignment)
                else:
                    rejected_complete_layouts[0] += 1
                return
            value = order[index]
            plans = list(base.tail_plans(geo, value, assignment, cap=400))
            if 1 <= index <= 2:
                rng.shuffle(plans)
            for delta in plans:
                nodes[0] += 1
                updated = dict(assignment)
                updated.update(delta)
                backtrack(index + 1, updated)
                if solution[0] is not None:
                    return

        backtrack(0, {})
        if solution[0] is None:
            print(
                f"[w{worker}] cfg{config_index} exhausted nodes={nodes[0]} "
                f"runtime_rejects={rejected_complete_layouts[0]}",
                flush=True,
            )
            continue
        program = base.assemble(geo, solution[0])
        passed, bad_input, status, output = base.simulate_all(program)
        if passed:
            return program
        print(
            f"[w{worker}] cfg{config_index} diagnostic mismatch "
            f"{bad_input:#x} {status} {output}",
            flush=True,
        )
    return None


def main() -> int:
    worker = int(sys.argv[1])
    worker_count = int(sys.argv[2])
    max_splits = int(sys.argv[3])
    node_budget = int(sys.argv[4])
    offset_count = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    minimum_config = int(sys.argv[6]) if len(sys.argv) > 6 else 0
    minimum_splits = int(sys.argv[7]) if len(sys.argv) > 7 else 0
    offsets = [(), (4,), (8,), (12,), (2,), (6,)][:offset_count]

    configs = base.enum_configs()

    def low_gap(config) -> int:
        values = sorted(config[2].values())
        gaps = [right - left for left, right in zip(values, values[1:]) if right - left < 30]
        return min(gaps) if gaps else 99

    configs.sort(key=lambda config: (-low_gap(config), -min(config[2].values())))
    assigned = [
        item
        for item in list(enumerate(configs))[worker::worker_count]
        if item[0] >= minimum_config
    ]
    print(f"[w{worker}] {len(assigned)}/{len(configs)} configs", flush=True)

    for index, (cps, operands, landings) in assigned:
        program = solve_config(
            index,
            cps,
            operands,
            landings,
            worker=worker,
            min_splits=minimum_splits,
            max_splits=max_splits,
            node_budget=node_budget,
            offsets=offsets,
        )
        if program is None:
            continue
        count, detail = native_check(program, worker)
        print(f"[w{worker}] cfg{index} native {count}/{len(INPUTS)} {detail or ''}", flush=True)
        if count == len(INPUTS):
            destination = WORK_DIR / f"MAP8-SOLUTION-worker-{worker}.mal"
            destination.write_bytes(program)
            print(
                f"[w{worker}] SOLVED pos={cps} operands={operands} "
                f"landings={sorted(landings.values())} len={len(program)} -> {destination}",
                flush=True,
            )
            return 0

    print(f"[w{worker}] complete, no solution", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
