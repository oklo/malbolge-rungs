"""Four-lane, two-output-byte dispatch search for L5.R1.future-hash-prefix.

Rung shape (registry + crates/harness/src/challenge.rs):

    family HashPrefix, transform Identity, 4 cases, output_bytes 2,
    max_program_len 2048, max_steps_per_case 2_000_000, max_output_len 2.

HashPrefix inputs are the 32-byte hash H("...:input", (seed, index)) and the
expected output is H("...:hash-prefix", (seed, input, index))[:2].  The seed is
never visible to the program, so no function of the input computes the output:
the only correct program is a lookup table keyed on the input bytes it reads.
Epoch-0 cases, read out of `verify --json`:

    case 0  ce6a...  -> c9 31
    case 1  46975... -> 86 91
    case 2  a2a1...  -> 5f 84
    case 3  f52b...  -> 96 1d

The four first bytes ce/46/a2/f5 are distinct, so a single IN is the whole key
and this is a 4-entry finite map -- but with **two** output bytes per entry,
which is what is new relative to L4.R0/R1/R2 (1 byte, 1-2 entries).

Construction is research/map8 (stage-1 crz dispatch -> per-cluster
[MOVD,JUMP] station -> private tails), reused unchanged for stages 1 and 2.
The new part is the tail solver: instead of

    NOP*k SHAPE OUT HALT

each tail must run

    NOP*k SHAPE1 OUT SHAPE2 OUT HALT

where SHAPE1 has to steer the accumulator onto the first target byte and
SHAPE2 onto the second, over the *same* d-trail, with the operand cells shared
between the two stages.  `tails_from_2out` / `solve_operands_2out` below
replace base.tails_from with that shape.

Usage:
  python3 research/future-hash-prefix/search_fhp.py \
      [MAXSPLITS] [NODE_BUDGET] [PROGLEN] [DEADLINE_S] [JMIN]
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
WORK = Path(tempfile.gettempdir()) / "malbolge-rungs-fhp"
WORK.mkdir(parents=True, exist_ok=True)

from research.map8 import base, geometry  # noqa: E402
from tools.hell_lite.ops import (  # noqa: E402
    crazy_word, source_valid_bytes, NOP, CRAZY, OUT, HALT, MOVD, ROT,
)
from tools.hell_lite.score import execute_python  # noqa: E402

RUNG = "L5.R1.future-hash-prefix"

# epoch-0 targets: first input byte -> (out0, out1)
TARGETS = {
    0xCE: (0xC9, 0x31),
    0x46: (0x86, 0x91),
    0xA2: (0x5F, 0x84),
    0xF5: (0x96, 0x1D),
}
INPUTS = sorted(TARGETS)

base.INPUTS = INPUTS
base.TGT = TARGETS
geometry.INPUTS = INPUTS
geometry.TGT = TARGETS

BINARY = REPO / "target" / "release" / "malbolge-rungs"

MAXSPLITS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
NODE_BUDGET = int(sys.argv[2]) if len(sys.argv) > 2 else 60000
PROGLEN = int(sys.argv[3]) if len(sys.argv) > 3 else 512
DEADLINE = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
JMIN = int(sys.argv[5]) if len(sys.argv) > 5 else 130

MAX_N = 4
MAX_K = 8


# ---------------------------------------------------------------- tail solver

def _shapes(max_n):
    out = []
    for movd1 in (0, 1):
        for rot in (0, 1):
            for movd2 in (0, 1):
                if movd2 and not rot:
                    continue
                for n in range(0, max_n + 1):
                    if not rot and n == 0:
                        continue
                    out.append([MOVD] * movd1 + [ROT] * rot +
                               [MOVD] * movd2 + [CRAZY] * n)
    return out


SHAPES1 = _shapes(MAX_N)
# second stage: same alphabet, and the empty shape is useless (the two target
# bytes always differ here), so it is excluded by the `not rot and n == 0` rule.
SHAPES2 = _shapes(MAX_N)


MAXDEPTH = 14


def tails_from_2out(geo, x, Jx, L, d0, assign, acc_delta, max_k, max_n):
    """Unified DFS over the tail instead of a SHAPE1 x SHAPE2 product.

    The product form (28 x 28 shapes x 9 NOP prefixes = ~7000 op sequences per
    landing, each re-solving its operands from scratch) measured ~18 s per
    dispatch config -- far too slow to sweep 17k configs.  This walks the tail
    cell by cell instead, choosing the op *and* its operand together and
    sharing every prefix: strictly more shapes, one traversal.
    """
    tgts = TARGETS[x]
    tcell = L - 1  # enciphered by the stage-2 jump before the tail runs
    extra_enc = (tcell,)
    results = []

    def rec(i, a_val, d_cur, cur_assign, cur_delta, emitted):
        if len(results) >= 24 or i > MAXDEPTH:
            return
        base._ATTEMPTS[0] += 1
        if (base._ATTEMPT_BUDGET[0] is not None
                and base._ATTEMPTS[0] >= base._ATTEMPT_BUDGET[0]):
            return
        cell = L + i
        z = geo.zone(cell)
        if z == "out":
            return
        if z == "fixed":
            ops = [base.decode_op(geo.base[cell], cell)]
        elif cell in cur_assign:
            ops = [base.decode_op(cur_assign[cell], cell)]
        else:
            ops = [OUT, CRAZY, ROT, MOVD, NOP, HALT]

        for op in ops:
            if op not in (OUT, CRAZY, ROT, MOVD, NOP, HALT):
                continue
            if z == "free" and cell not in cur_assign:
                b = base.source_byte_for_op(op, cell)
                asg = dict(cur_assign)
                asg[cell] = b
                dlt = dict(cur_delta)
                dlt[cell] = b
            else:
                asg, dlt = cur_assign, cur_delta

            if op == HALT:
                continue  # only reached via the emitted==2 shortcut below
            if op == NOP:
                rec(i + 1, a_val, d_cur + 1, asg, dlt, emitted)
                continue
            if op == OUT:
                if a_val is None or a_val % 256 != tgts[emitted]:
                    continue
                if emitted + 1 == len(tgts):
                    # place the HALT immediately after and record the tail
                    hcell = L + i + 1
                    hz = geo.zone(hcell)
                    if hz == "out":
                        continue
                    if hz == "fixed":
                        if base.decode_op(geo.base[hcell], hcell) != HALT:
                            continue
                        results.append(dict(dlt))
                    elif hcell in asg:
                        if base.decode_op(asg[hcell], hcell) == HALT:
                            results.append(dict(dlt))
                    else:
                        fin = dict(dlt)
                        fin[hcell] = base.source_byte_for_op(HALT, hcell)
                        results.append(fin)
                    continue
                rec(i + 1, a_val, d_cur + 1, asg, dlt, emitted + 1)
                continue

            # data ops read the operand cell at d
            v, choices = geo.cell_value(d_cur, x, asg, extra_enc)
            opts = ([(v, {})] if choices is None and v is not None else
                    [(vv, {d_cur: bb}) for bb, vv in (choices or [])])
            for vv, dd in opts:
                na = dict(asg)
                na.update(dd)
                nd = {**dlt, **dd}
                if op == MOVD:
                    if not (12 <= vv + 1 < geo.proglen):
                        continue
                    rec(i + 1, a_val, vv + 1, na, nd, emitted)
                elif op == ROT:
                    rec(i + 1, base.rotate_right_word(vv), d_cur + 1, na, nd,
                        emitted)
                elif op == CRAZY:
                    if a_val is None:
                        continue
                    rec(i + 1, crazy_word(a_val, vv), d_cur + 1, na, nd,
                        emitted)

    rec(0, Jx, d0, assign, acc_delta, 0)
    yield from results


def solve_operands_2out(geo, x, Jx, tgts, ops, d0, assign, acc_delta, tcell):
    """base.solve_operands with two OUT checkpoints instead of one.

    OUT does not touch a and does not stop the tail: it prints a % 256 and the
    machine advances c and d like any other instruction, so the second stage
    continues on the same accumulator over the next operand cells.
    """
    results = []
    extra_enc = (tcell,)

    def rec(i, a_val, d_cur, cur_assign, cur_delta, emitted):
        if len(results) >= 24:
            return
        base._ATTEMPTS[0] += 1
        if (base._ATTEMPT_BUDGET[0] is not None
                and base._ATTEMPTS[0] >= base._ATTEMPT_BUDGET[0]):
            return
        if i == len(ops):
            return
        op = ops[i]
        if op == NOP:
            rec(i + 1, a_val, d_cur + 1, cur_assign, cur_delta, emitted)
            return
        if op == OUT:
            if a_val is None or a_val % 256 != tgts[emitted]:
                return
            if emitted + 1 == len(tgts):
                results.append(cur_delta)
                return
            rec(i + 1, a_val, d_cur + 1, cur_assign, cur_delta, emitted + 1)
            return
        if op == HALT:
            return
        v, choices = geo.cell_value(d_cur, x, cur_assign, extra_enc)
        opts = ([(v, {})] if choices is None and v is not None else
                [(vv, {d_cur: b}) for b, vv in (choices or [])])
        if op == MOVD:
            for vv, dd in opts:
                if not (12 <= vv + 1 < geo.proglen):
                    continue
                na = dict(cur_assign)
                na.update(dd)
                rec(i + 1, a_val, vv + 1, na, {**cur_delta, **dd}, emitted)
            return
        if op == ROT:
            for vv, dd in opts:
                na = dict(cur_assign)
                na.update(dd)
                rec(i + 1, base.rotate_right_word(vv), d_cur + 1, na,
                    {**cur_delta, **dd}, emitted)
            return
        if op == CRAZY:
            if a_val is None:
                return
            for vv, dd in opts:
                na = dict(cur_assign)
                na.update(dd)
                rec(i + 1, crazy_word(a_val, vv), d_cur + 1, na,
                    {**cur_delta, **dd}, emitted)
            return

    rec(0, Jx, d0, assign, acc_delta, 0)
    yield from results


base.tails_from = tails_from_2out  # base.tail_plans() now builds 2-out tails


# ---------------------------------------------------------------- geometry

class GeoLen(geometry.GeoV2):
    """GeoV2 with the program length pinned (map8 caps it at 150)."""

    def __init__(self, cps, ts, J, mask, offsets):
        super().__init__(cps, ts, J, mask, offsets)
        if not self.ok:
            return
        last_station = max(self.station_of.values())
        if last_station + 2 > PROGLEN:
            self.ok = False
            return
        self.proglen = PROGLEN


def enum_configs_n(max_jmax, jmin):
    out = []
    for extra in (1, 3):
        for pos in itertools.combinations(range(2, 9), extra):
            cps = list(pos) + [9]
            alphabets = [source_valid_bytes(40 + p) for p in cps]
            for ts in itertools.product(*alphabets):
                J = {}
                for x in INPUTS:
                    a = x
                    for t in ts:
                        a = crazy_word(a, t)
                    J[x] = a
                vs = sorted(J.values())
                if len(set(vs)) != len(INPUTS) or vs[0] < jmin or vs[-1] > max_jmax:
                    continue
                out.append((tuple(cps), ts, J))
    return out


# ---------------------------------------------------------------- validation

def simulate_all(prog):
    for x in INPUTS:
        r = execute_python(prog, bytes([x]), max_steps=20000, max_output_len=2)
        if not (r.status == "halt" and tuple(r.output) == TARGETS[x]):
            return False, x, r.status, r.output
    return True, None, None, None


def native_check(program: bytes, tag: str):
    path = WORK / f"fhp-{tag}.mal"
    path.write_bytes(program)
    correct = 0
    for value in INPUTS:
        run = subprocess.run(
            [str(BINARY), "execute", "--program", str(path),
             "--input-hex", f"{value:02x}"],
            capture_output=True, check=False, timeout=60,
        )
        try:
            report = json.loads(run.stdout)
        except Exception:
            return correct, {"stdout": run.stdout.decode(),
                             "stderr": run.stderr.decode()}
        want = "%02x%02x" % TARGETS[value]
        if report.get("output_hex") == want and "Halt" in str(report.get("status")):
            correct += 1
        else:
            return correct, report
    return correct, None


# ---------------------------------------------------------------- driver

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
                 offsets, plan_cap=400):
    values = sorted(landings.values())
    rng = random.Random(index)
    for mask, station_offsets in geometries_for(values, max_splits, offsets):
        geo = GeoLen(cps, operands, landings, mask, station_offsets)
        if not geo.ok:
            continue
        counts = {}
        for value in INPUTS:
            counts[value] = sum(1 for _ in base.tail_plans(
                geo, value, {}, max_k=MAX_K, cap=40, attempt_budget=120000))
            if counts[value] == 0:
                break
        if len(counts) != len(INPUTS) or any(c == 0 for c in counts.values()):
            continue
        print(f"  cfg{index} mask={sorted(mask)} offs={station_offsets} "
              f"plans={[counts[v] for v in INPUTS]}", flush=True)

        order = sorted(INPUTS, key=lambda v: counts[v])
        solution = [None]
        nodes = [0]

        def backtrack(i, assignment):
            if solution[0] is not None or nodes[0] > node_budget:
                return
            if i == len(order):
                candidate = base.assemble(geo, assignment)
                if simulate_all(candidate)[0]:
                    solution[0] = dict(assignment)
                return
            plans = list(base.tail_plans(geo, order[i], assignment,
                                         max_k=MAX_K, cap=plan_cap,
                                         attempt_budget=400000))
            if i >= 1:
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
        if simulate_all(program)[0]:
            print(f"cfg{index} mask={sorted(mask)} offs={station_offsets} "
                  f"len={len(program)} python-OK", flush=True)
            return program
    return None


def main() -> int:
    offsets = [(), (4,), (8,), (12,), (2,), (6,), (16,), (0, 6)]
    configs = enum_configs_n(max_jmax=PROGLEN - 6, jmin=JMIN)
    # Highest landings first: tails can only live at addresses 34..127 (the
    # stage-2 pointer and jump target are both source-valid bytes), so the
    # further the landing band sits above 127 the more tail space survives.
    configs.sort(key=lambda c: -min(c[2].values()))
    print(f"{len(configs)} configs  jmin={JMIN} proglen={PROGLEN}", flush=True)
    if configs:
        lo = [min(c[2].values()) for c in configs]
        print(f"landing floor range {min(lo)}..{max(lo)}", flush=True)

    start = time.time()
    for index, (cps, operands, landings) in enumerate(configs):
        if DEADLINE and time.time() - start > DEADLINE:
            print(f"deadline: stopped after {index}/{len(configs)} configs",
                  flush=True)
            return 2
        program = solve_config(index, cps, operands, landings,
                               max_splits=MAXSPLITS, node_budget=NODE_BUDGET,
                               offsets=offsets)
        if program is None:
            continue
        count, detail = native_check(program, "probe")
        print(f"cfg{index} native {count}/{len(INPUTS)} {detail or ''}",
              flush=True)
        if count == len(INPUTS):
            out = Path(__file__).resolve().parent / "cand-fhp.mal"
            out.write_bytes(program)
            print(f"SOLVED cps={cps} operands={operands} "
                  f"landings={sorted(landings.values())} len={len(program)} "
                  f"-> {out}", flush=True)
            return 0
    print("complete, no solution", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
