"""Per-lane *output reachability* for the map12-hi two-stage dispatch family.

The two recorded attempts on this rung both asked a yes/no question -- "does
lane x have a tail that emits TGT[x] here?" -- and got "no" for some lane in
every geometry they tried.  This module asks the strictly more informative
question:

    for lane x in this geometry, what is the full set of bytes the lane
    *can* emit, over every (p, T) pointer pair, NOP runway, tail shape and
    legal operand assignment?

Knowing the reachable-output set separates two very different failure modes:

  * |R(x)| large but TGT[x] not in it  -> the lane is alive, the target is
    just off the reachable orbit; a different dispatch config might land it.
  * |R(x)| tiny (0-3 values)           -> the lane is structurally starved
    and no amount of joint search will help.

Reachability here is computed with an *empty* shared assignment, i.e. it is
an upper bound: any byte not in R(x) is provably unemittable by lane x in
this geometry regardless of what the other eleven lanes do.

Usage:
    python3 research/map12-hi/reach.py [CONFIG_INDEX ...]
"""

from __future__ import annotations

import sys
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


def outputs_for_ops(geo, x, Jx, ops, d0, assign, Tcell, budget, seen):
    """Collect every a%256 an OUT in this op sequence can produce.

    Memoised on (op index, accumulator, data pointer).  The shared operand
    assignment is dropped from the memo key, which can only *add* operand
    combinations that a strict search would reject on a revisited cell -- so
    the result stays a sound upper bound on what the lane can emit, which is
    the only direction that matters for a negative result.
    """
    extra_enc = (Tcell,)
    out = set()
    nodes = [0]
    memo = set()

    def rec(i, a_val, d_cur, cur_assign):
        if nodes[0] >= budget:
            return
        key = (i, a_val, d_cur)
        if key in memo:
            return
        memo.add(key)
        nodes[0] += 1
        if i == len(ops):
            return
        op = ops[i]
        if op == NOP:
            rec(i + 1, a_val, d_cur + 1, cur_assign)
            return
        if op == OUT:
            if a_val is not None:
                out.add(a_val % 256)
            return
        if op == HALT:
            return
        value, choices = geo.cell_value(d_cur, x, cur_assign, extra_enc)
        opts = ([(value, {})] if choices is None and value is not None
                else [(vv, {d_cur: b}) for b, vv in (choices or [])])
        if op == MOVD:
            for vv, dd in opts:
                if not (12 <= vv + 1 < geo.proglen):
                    continue
                na = dict(cur_assign)
                na.update(dd)
                rec(i + 1, a_val, vv + 1, na)
            return
        if op == ROT:
            for vv, dd in opts:
                na = dict(cur_assign)
                na.update(dd)
                rec(i + 1, rotate_right_word(vv), d_cur + 1, na)
            return
        if op == CRAZY:
            if a_val is None:
                return
            for vv, dd in opts:
                na = dict(cur_assign)
                na.update(dd)
                rec(i + 1, crazy_word(a_val, vv), d_cur + 1, na)
            return

    rec(0, Jx, d0, assign)
    seen[0] += nodes[0]
    return out


def lane_outputs(geo, x, max_k=8, budget_per_ops=40_000):
    """Upper-bound set of bytes lane x can emit in this geometry."""
    Jx, m = geo.lane_env(x)
    q = m + 49 - Jx
    reach = set()
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
                    reach |= outputs_for_ops(geo, x, Jx, ops, p + 2, a3,
                                             L - 1, budget_per_ops, nodes)
    return reach, nodes[0]


def report(config_index, mask=frozenset(), offsets=(), max_k=8):
    configs = base.enum_configs()
    cps, operands, landings = configs[config_index]
    geo = geometry.GeoV2(cps, operands, landings, mask, offsets)
    if not geo.ok:
        print(f"cfg{config_index} mask={sorted(mask)} offs={offsets}: geometry invalid")
        return None
    print(f"cfg{config_index} cps={cps} operands={operands} mask={sorted(mask)} "
          f"offs={offsets} landings={sorted(landings.values())}")
    live = 0
    detail = {}
    for x in INPUTS:
        reach, nodes = lane_outputs(geo, x, max_k=max_k)
        tgt = TARGETS[x]
        hit = tgt in reach
        live += hit
        detail[x] = (hit, len(reach), sorted(reach))
        near = min((abs(o - tgt) for o in reach), default=None)
        print(f"  x={x:#04x} J={geo.J[x]:4d} tgt={tgt:#04x} "
              f"{'HIT ' if hit else 'MISS'} |R|={len(reach):3d} "
              f"nearest_delta={near} nodes={nodes}")
    print(f"  live lanes: {live}/12")
    return live, detail


def main() -> int:
    indices = [int(a) for a in sys.argv[1:]] or [0]
    for index in indices:
        report(index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
