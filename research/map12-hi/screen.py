"""Necessary-condition screen over every map12-hi dispatch configuration.

For a config+geometry to be able to produce a solution, *every* lane must be
able to emit its own target byte in isolation, with the shared cell
assignment empty (maximum freedom).  That is a strictly necessary condition
for the joint assignment the two recorded attempts were searching for, and
it is far cheaper to decide than the joint problem: it is 12 independent
single-lane questions instead of one 12-way constraint problem.

This screen answers that question for all 115 separating configs.  It exits
a config as soon as one lane is proved unable to emit its target, and exits
a lane as soon as its target is found, so live configs and dead configs are
both cheap.

Result semantics:
  live=12  -> the config passes the necessary condition; joint search is
              worth running on it.
  live<12  -> the config is dead for the whole two-stage family, and no
              amount of joint-assignment budget can rescue it.

Usage: python3 research/map12-hi/screen.py WORKER NWORKERS [MAXSPLITS] [NOFFS]
"""

from __future__ import annotations

import itertools
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from research.map12hi import base, geometry  # noqa: E402
from research.map12hi.geometry import SHAPES  # noqa: E402
from tools.hell_lite.ops import (  # noqa: E402
    crazy_word, rotate_right_word, NOP, CRAZY, OUT, HALT, MOVD, ROT,
)

INPUTS = [0xA5, 0xE0, 0x90, 0x9C, 0x84, 0xA1, 0xBD, 0xC8, 0xBE, 0xF9, 0x86, 0xDD]
TARGETS = {value: value ^ 0x51 for value in INPUTS}
base.INPUTS = INPUTS
base.TGT = TARGETS
geometry.INPUTS = INPUTS
geometry.TGT = TARGETS

MAX_K = 8

# MAP12HI_LANES=0x90 restricts the screen to one lane, which turns the
# question from "is this geometry fully live" into "can this one lane ever
# emit its target anywhere in the family" -- the sharper structural question
# once a single lane turns out to be the universal blocker.
LANES = [int(v, 0) for v in os.environ["MAP12HI_LANES"].split(",")] \
    if os.environ.get("MAP12HI_LANES") else INPUTS


def lane_can_emit(geo, x, tgt, max_k=MAX_K):
    """True iff lane x has any tail emitting tgt with an empty shared assign."""
    Jx, m = geo.lane_env(x)
    q = m + 49 - Jx
    nodes = [0]

    value, choices = geo.cell_value(q, x, {})
    p_opts = ([(value, {})] if choices is None and value is not None
              else [(vv, {q: b}) for b, vv in (choices or [])])
    for p, asg_p in p_opts:
        if not isinstance(p, int):
            continue
        r = p + 1
        if not (12 <= r < geo.proglen):
            continue
        a1 = dict(asg_p)
        v2, ch2 = geo.cell_value(r, x, a1)
        t_opts = ([(v2, {})] if ch2 is None and v2 is not None
                  else [(vv, {r: b}) for b, vv in (ch2 or [])])
        for T, asg_t in t_opts:
            L = T + 1
            if not (12 <= L < geo.proglen - 2):
                continue
            a2 = dict(a1)
            a2.update(asg_t)
            for k in range(max_k + 1):
                for shape in SHAPES:
                    ops = [NOP] * k + shape + [OUT, HALT]
                    cells = list(range(L, L + len(ops)))
                    code_delta = base.place_code(geo, list(zip(cells, ops)), a2)
                    if code_delta is None:
                        continue
                    a3 = dict(a2)
                    a3.update(code_delta)
                    if _walk(geo, x, Jx, tgt, ops, p + 2, a3, L - 1, nodes):
                        return True, nodes[0]
    return False, nodes[0]


def _walk(geo, x, Jx, tgt, ops, d0, assign, Tcell, nodes):
    extra_enc = (Tcell,)
    memo = set()

    def rec(i, a_val, d_cur, cur_assign):
        key = (i, a_val, d_cur)
        if key in memo:
            return False
        memo.add(key)
        nodes[0] += 1
        if i == len(ops):
            return False
        op = ops[i]
        if op == NOP:
            return rec(i + 1, a_val, d_cur + 1, cur_assign)
        if op == OUT:
            return a_val is not None and a_val % 256 == tgt
        if op == HALT:
            return False
        value, choices = geo.cell_value(d_cur, x, cur_assign, extra_enc)
        opts = ([(value, {})] if choices is None and value is not None
                else [(vv, {d_cur: b}) for b, vv in (choices or [])])
        for vv, dd in opts:
            na = dict(cur_assign)
            na.update(dd)
            if op == MOVD:
                if not (12 <= vv + 1 < geo.proglen):
                    continue
                if rec(i + 1, a_val, vv + 1, na):
                    return True
            elif op == ROT:
                if rec(i + 1, rotate_right_word(vv), d_cur + 1, na):
                    return True
            elif op == CRAZY:
                if a_val is None:
                    return False
                if rec(i + 1, crazy_word(a_val, vv), d_cur + 1, na):
                    return True
        return False

    return rec(0, Jx, d0, assign)


def geometries(values, max_splits, offsets):
    bounds = geometry.splittable_boundaries(values)
    masks = sorted((frozenset(c) for r in range(max_splits + 1)
                    for c in itertools.combinations(bounds, r)), key=len)
    for mask in masks:
        for offs in offsets:
            yield mask, offs


def main() -> int:
    worker = int(sys.argv[1])
    nworkers = int(sys.argv[2])
    max_splits = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    noffs = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    offsets = [(), (4,), (8,), (12,)][:noffs]

    configs = base.enum_configs()
    assigned = list(enumerate(configs))[worker::nworkers]
    print(f"[w{worker}] {len(assigned)}/{len(configs)} configs", flush=True)

    best = (0, None)
    for index, (cps, operands, landings) in assigned:
        values = sorted(landings.values())
        started = time.monotonic()
        for mask, offs in geometries(values, max_splits, offsets):
            geo = geometry.GeoV2(cps, operands, landings, mask, offs)
            if not getattr(geo, "ok", False) or not hasattr(geo, "base"):
                continue
            live = 0
            dead = []
            for x in LANES:
                ok, _ = lane_can_emit(geo, x, TARGETS[x])
                if ok:
                    live += 1
                else:
                    dead.append(x)
                    break
            if live > best[0]:
                best = (live, (index, sorted(mask), offs))
            print(f"[w{worker}] cfg{index} mask={sorted(mask)} offs={offs} "
                  f"live>={live} first_dead={[hex(d) for d in dead]}", flush=True)
            if not dead:
                print(f"[w{worker}] cfg{index} ALL-12-LIVE mask={sorted(mask)} "
                      f"offs={offs}", flush=True)
        print(f"[w{worker}] cfg{index} done {time.monotonic() - started:.1f}s "
              f"best={best}", flush=True)
    print(f"[w{worker}] complete best={best}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
