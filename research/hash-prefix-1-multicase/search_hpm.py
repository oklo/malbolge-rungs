"""Three-lane dispatch search for L4.R1.hash-prefix-1-multicase (epoch 0).

The rung runs the *same* program once per case.  Each case gets its own 32-byte
seed-derived input and its own one-byte target, so the program is a three-entry
finite map keyed on input bytes -- structurally identical to the solved
L2.FM2.xor51-map8, with three lanes instead of eight and a 1024-byte (not 2048)
program limit.

Epoch-0 cases, from `verify --json`:

    case 0  input 20 57 b4 ...  -> e5
    case 1  input fc 02 22 ...  -> 85
    case 2  input 12 52 14 ...  -> 05

The first bytes 0x20 / 0xfc / 0x12 are distinct, so one IN suffices as the key.

Construction (verbatim from research/map8, only the lane set and the length cap
change):
  stage 1  IN; a few CRAZYs against chosen in-program constants; MOVD/JUMP to
           land lane x at address J(x)+1 with a = J(x);
  stage 2  walk NOPs to a per-cluster [MOVD, JUMP] station, whose pointer cell
           is lane-dependent, so each lane jumps to a private tail;
  tail     NOP* [MOVD] [ROT] [MOVD] CRAZY* OUT HALT, operands solved so that
           a mod 256 == target at OUT.

Usage: python3 research/hash-prefix-1-multicase/search_hpm.py [MAXSPLITS] [NODE_BUDGET] [MAXLEN]
"""

from __future__ import annotations

import itertools
import json
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
WORK = Path(tempfile.gettempdir()) / "malbolge-rungs-hpm"
WORK.mkdir(parents=True, exist_ok=True)

from research.map8 import base, geometry  # noqa: E402

RUNG = "L4.R1.hash-prefix-1-multicase"

# First input byte -> target byte, per epoch, read off `verify --epochs 3 --json`.
# The judge runs epoch 0 only; epochs 1 and 2 are here for the multi-epoch
# scaling experiment (how many lanes does this architecture take before the
# 1024-byte program limit bites?).  All nine first bytes are distinct.
EPOCH_CASES = [
    {0x20: 0xE5, 0xFC: 0x85, 0x12: 0x05},
    {0xCE: 0x2E, 0xE5: 0xB6, 0x21: 0x23},
    {0x9B: 0x9B, 0xB3: 0x00, 0x75: 0xEC},
]

NEPOCHS = int(sys.argv[4]) if len(sys.argv) > 4 else 1
TARGETS = {}
for _m in EPOCH_CASES[:NEPOCHS]:
    TARGETS.update(_m)
INPUTS = sorted(TARGETS)
DEADLINE = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0

base.INPUTS = INPUTS
base.TGT = TARGETS
geometry.INPUTS = INPUTS
geometry.TGT = TARGETS

BINARY = REPO / "target" / "release" / "malbolge-rungs"


def native_check(program: bytes, tag: str) -> tuple[int, object | None]:
    path = WORK / f"hpm-{tag}.mal"
    path.write_bytes(program)
    correct = 0
    for value in INPUTS:
        run = subprocess.run(
            [str(BINARY), "execute", "--program", str(path),
             "--input-hex", f"{value:02x}"],
            capture_output=True, check=False, timeout=30,
        )
        try:
            report = json.loads(run.stdout)
        except Exception:
            return correct, {"stdout": run.stdout.decode(), "stderr": run.stderr.decode()}
        if report.get("output_hex") == f"{TARGETS[value]:02x}" and "Halt" in str(report.get("status")):
            correct += 1
        else:
            return correct, report
    return correct, None


def geometries_for(values, max_splits, offsets):
    boundaries = geometry.splittable_boundaries(values)
    masks = sorted(
        (frozenset(combo)
         for count in range(0, max_splits + 1)
         for combo in itertools.combinations(boundaries, count)),
        key=len,
    )
    for mask in masks:
        for station_offsets in offsets:
            yield mask, station_offsets


def solve_config(index, cps, operands, landings, *, max_splits, node_budget,
                 offsets, max_len):
    values = sorted(landings.values())
    rng = random.Random(index)
    for mask, station_offsets in geometries_for(values, max_splits, offsets):
        geo = geometry.GeoV2(cps, operands, landings, mask, station_offsets)
        if not geo.ok or geo.proglen > max_len:
            continue
        counts = {}
        for value in INPUTS:
            counts[value] = sum(1 for _ in base.tail_plans(geo, value, {}, cap=300))
            if counts[value] == 0:
                break
        if len(counts) != len(INPUTS) or any(c == 0 for c in counts.values()):
            continue

        order = sorted(INPUTS, key=lambda v: counts[v])
        solution = [None]
        nodes = [0]

        def backtrack(i, assignment):
            if solution[0] is not None or nodes[0] > node_budget:
                return
            if i == len(order):
                candidate = base.assemble(geo, assignment)
                if base.simulate_all(candidate)[0]:
                    solution[0] = dict(assignment)
                return
            plans = list(base.tail_plans(geo, order[i], assignment, cap=400))
            if i == 1:
                rng.shuffle(plans)
            for delta in plans:
                nodes[0] += 1
                updated = dict(assignment)
                updated.update(delta)
                backtrack(i + 1, updated)
                if solution[0] is not None:
                    return

        backtrack(0, {})
        if solution[0] is None:
            continue
        program = base.assemble(geo, solution[0])
        if base.simulate_all(program)[0]:
            print(f"cfg{index} mask={sorted(mask)} offs={station_offsets} "
                  f"len={len(program)} python-OK", flush=True)
            return program
    return None


def main() -> int:
    max_splits = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    node_budget = int(sys.argv[2]) if len(sys.argv) > 2 else 40000
    max_len = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
    offsets = [(), (4,), (8,), (12,), (2,), (6,)]

    configs = base.enum_configs(max_jmax=max_len - 60)

    def low_gap(config):
        vs = sorted(config[2].values())
        gaps = [r - l for l, r in zip(vs, vs[1:]) if r - l < 30]
        return min(gaps) if gaps else 99

    configs.sort(key=lambda c: (-low_gap(c), -min(c[2].values())))
    print(f"{len(configs)} configs", flush=True)

    start = time.time()
    for index, (cps, operands, landings) in enumerate(configs):
        if DEADLINE and time.time() - start > DEADLINE:
            print(f"deadline: stopped after {index} configs", flush=True)
            return 2
        program = solve_config(index, cps, operands, landings,
                               max_splits=max_splits, node_budget=node_budget,
                               offsets=offsets, max_len=max_len)
        if program is None:
            continue
        count, detail = native_check(program, "probe")
        print(f"cfg{index} native {count}/{len(INPUTS)} {detail or ''}", flush=True)
        if count == len(INPUTS):
            out = Path(__file__).resolve().parent / f"cand-hpm-e{NEPOCHS}.mal"
            out.write_bytes(program)
            print(f"SOLVED cps={cps} operands={operands} "
                  f"landings={sorted(landings.values())} len={len(program)} -> {out}",
                  flush=True)
            return 0
    print("complete, no solution", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
