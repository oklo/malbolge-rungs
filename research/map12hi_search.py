"""Breadth-first search for the twelve-lane XOR 0x51 finite map (map12-hi).

Directly extends research/map8_search.py's two-stage CRAZY-dispatch /
station / private-tail architecture (research/map8/base.py,
research/map8/geometry.py, copied into research/map12hi/) to the rung
L2.FM2h.xor51-map12-hi's twelve published high-range inputs. The
construction primitives are input-count-agnostic (INPUTS/TGT are module
globals patched at import time), so no logic changes were needed beyond the
input list and a 12-wide native check -- except one addition: map12-hi's
larger landing spread (up to addr 249, vs map8's ~150) makes solve_operands'
per-lane exhaustive-failure search (proving a lane has *zero* valid tails in
a geometry) blow up badly, since that proof has no native node bound. The
map12hi copies of base.py/geometry.py add an optional attempt_budget to
tail_plans() that caps total backtracking nodes and treats "budget exceeded"
the same as "confirmed exhausted" (both already mean "skip this geometry"
to every caller here).

Usage: python3 research/map12hi_search.py WORKER NWORKERS MAXSPLITS NODE_BUDGET [NOFFS] [MIN_CONFIG] [MINSPLITS]
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
WORK_DIR = Path(tempfile.gettempdir()) / "malbolge-rungs-map12hi"
WORK_DIR.mkdir(parents=True, exist_ok=True)

from research.map12hi import base, geometry  # noqa: E402


INPUTS = [0xA5, 0xE0, 0x90, 0x9C, 0x84, 0xA1, 0xBD, 0xC8, 0xBE, 0xF9, 0x86, 0xDD]
TARGETS = {value: value ^ 0x51 for value in INPUTS}

base.INPUTS = INPUTS
base.TGT = TARGETS
geometry.INPUTS = INPUTS
geometry.TGT = TARGETS

PRECHECK_BUDGET = 150_000
BACKTRACK_BUDGET = 300_000


def native_check(program: bytes, worker: int) -> tuple[int, object | None]:
    candidate = WORK_DIR / f"map12hi-worker-{worker}.mal"
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
            counts[value] = sum(
                1 for _ in base.tail_plans(geo, value, {}, cap=300, attempt_budget=PRECHECK_BUDGET)
            )
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
            plans = list(
                base.tail_plans(geo, value, assignment, cap=400, attempt_budget=BACKTRACK_BUDGET)
            )
            if 1 <= index <= 4:
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

    # Smallest-landing-first: map12-hi's large address range (up to ~250 vs
    # map8's ~150) is what made exhaustive-failure proofs slow, so prefer
    # the cheaper configs first instead of map8's largest-min-landing bias.
    configs.sort(key=lambda config: (-low_gap(config), min(config[2].values())))
    assigned = [
        item
        for item in list(enumerate(configs))[worker::worker_count]
        if item[0] >= minimum_config
    ]
    print(f"[w{worker}] {len(assigned)}/{len(configs)} configs", flush=True)

    for index, (cps, operands, landings) in assigned:
        started = time.monotonic()
        print(
            f"[w{worker}] cfg{index} start landings={sorted(landings.values())}",
            flush=True,
        )
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
        print(f"[w{worker}] cfg{index} done in {time.monotonic() - started:.1f}s", flush=True)
        if program is None:
            continue
        count, detail = native_check(program, worker)
        print(f"[w{worker}] cfg{index} native {count}/{len(INPUTS)} {detail or ''}", flush=True)
        if count == len(INPUTS):
            destination = WORK_DIR / f"MAP12HI-SOLUTION-worker-{worker}.mal"
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
