"""map7b two-stage builder v2.

Levers over the stock map6 builder:
  1. Cluster-boundary enumeration: the stock rule splits at every gap>=3,
     which on map7b's uniform gap-3 low band makes five singleton stations
     with colliding pointer cells. v2 enumerates split/merge masks over the
     splittable boundaries; the merge-all-low mask reproduces the map6
     winning geometry (one station, five distinct pointer cells).
  2. Station-offset sampling on top of the greedy stagger (band placement).
  3. Richer tails: MOVD allowed after ROT, up to 4 CRAZYs.
Search order: per config, masks ordered fewest-stations-first, offsets
default-first; first native-valid solution wins.
"""
# As run on 2026-08-07 (lightly edited: /tmp paths generalized to run
# from research/map7/ in the repo; algorithm unchanged).
import os as _os, sys as _sys
_REPO = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import sys, itertools, json, subprocess, random
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import build_map7b as B
from build_map7b import (INPUTS, TGT, E, nop_byte, enum_configs, intermediates,
                         place_code, solve_operands, assemble, simulate_all,
                         native_check)
from tools.hell_lite.ops import (source_byte_for_op, source_valid_bytes,
                                 NOP, CRAZY, OUT, HALT, MOVD, IN, JUMP, ROT)

FORCE_GAP = 30  # gaps this large always separate clusters


class GeoV2(B.Geo):
    def __init__(self, cps, ts, J, mask, offsets):
        self.cps, self.ts, self.J = cps, ts, J
        self.ok = True
        self.reserved = {40 + cp: t for cp, t in zip(cps, ts)}
        self.reserved[50] = 48
        base = {0: 40, 1: source_byte_for_op(IN, 1)}
        for i in range(2, 10):
            base[i] = source_byte_for_op(CRAZY if i in cps else NOP, i)
        base[10] = source_byte_for_op(MOVD, 10)
        base[11] = source_byte_for_op(JUMP, 11)
        for cell, b in self.reserved.items():
            base[cell] = b

        vs = sorted(J.values())
        bnds = splittable_boundaries(vs)
        clusters = [[vs[0]]]
        for i, j in enumerate(vs[1:]):
            gap = j - clusters[-1][-1]
            if gap >= FORCE_GAP or (i in bnds and i in mask):
                clusters.append([j])
            else:
                clusters[-1].append(j)

        self.station_of = {}
        next_free_ptr = 51
        offs = list(offsets) + [0] * len(clusters)
        for ci, cl in enumerate(clusters):
            lo, hi = cl[0], cl[-1]
            budget = (clusters[ci + 1][0] - 1 - (hi + 2)) if ci + 1 < len(clusters) else 40
            if budget < 0:
                self.ok = False
                return
            want = next_free_ptr - 51
            o = min(max(want, 0) + offs[ci], budget)
            if o < 0:
                self.ok = False
                return
            m = hi + 2 + o
            for j in cl:
                self.station_of[j] = m
            for cell in range(lo + 1, m):
                base.setdefault(cell, nop_byte(cell))
            base[m] = source_byte_for_op(MOVD, m)
            base[m + 1] = source_byte_for_op(JUMP, m + 1)
            next_free_ptr = m + 49 - lo + 1
        last_station = max(self.station_of.values())
        self.proglen = max(last_station + 2, 150)
        self.base = base


def splittable_boundaries(vs):
    out = []
    run_last = vs[0]
    for i, j in enumerate(vs[1:]):
        gap = j - run_last
        if 3 <= gap < FORCE_GAP:
            out.append(i)
        run_last = j
    return out


# richer tail shapes: [NOP*k] + shape + [OUT, HALT]
SHAPES = []
for movd1 in (0, 1):
    for rot in (0, 1):
        for movd2 in (0, 1):
            if movd2 and not rot:
                continue
            for n in range(0, 5):
                if not rot and n == 0:
                    continue
                SHAPES.append([MOVD] * movd1 + [ROT] * rot +
                              [MOVD] * movd2 + [CRAZY] * n)


def tails_from_v2(geo, x, Jx, L, d0, assign, acc_delta, max_k, max_n):
    tgt = TGT[x]
    Tcell = L - 1
    for k in range(0, max_k + 1):
        for shape in SHAPES:
            ops = [NOP] * k + shape + [OUT, HALT]
            cells = list(range(L, L + len(ops)))
            code_delta = place_code(geo, list(zip(cells, ops)), assign)
            if code_delta is None:
                continue
            a3 = dict(assign)
            a3.update(code_delta)
            yield from solve_operands(geo, x, Jx, tgt, ops, d0, a3,
                                      {**acc_delta, **code_delta}, Tcell)


B.tails_from = tails_from_v2  # tail_plans() in B now uses the richer shapes


def geometries_for(vs):
    """(mask, offsets) pairs, most promising first."""
    bnds = splittable_boundaries(vs)
    masks = sorted((frozenset(c) for r in range(len(bnds) + 1)
                    for c in itertools.combinations(bnds, r)),
                   key=len)  # fewest splits (fewest stations) first
    offset_sets = [(), (4,), (8,), (12,), (4, 4), (0, 6), (8, 4), (16,)]
    for mask in masks:
        for offs in offset_sets:
            yield mask, offs


def solve_config(cps, ts, J, node_budget=60000, seed=0):
    vs = sorted(J.values())
    rng = random.Random(seed)
    for mask, offs in geometries_for(vs):
        geo = GeoV2(cps, ts, J, mask, offs)
        if not geo.ok:
            continue
        counts = {}
        bad = False
        for x in INPUTS:
            cnt = sum(1 for _ in B.tail_plans(geo, x, {}, cap=60))
            counts[x] = cnt
            if cnt == 0:
                bad = True
                break
        if bad:
            continue
        order = sorted(INPUTS, key=lambda x: counts[x])
        nst = len(set(geo.station_of.values()))
        print(f"  geo mask={sorted(mask)} offs={offs} stations={nst} "
              f"counts={ {hex(k): v for k, v in counts.items()} }", flush=True)
        sol = [None]
        nodes = [0]

        def bt(i, assign):
            if sol[0] is not None or nodes[0] > node_budget:
                return
            if i == len(order):
                sol[0] = dict(assign)
                return
            x = order[i]
            plans = list(B.tail_plans(geo, x, assign, cap=400))
            if i <= 1:
                rng.shuffle(plans)
            for delta in plans:
                nodes[0] += 1
                na = dict(assign)
                na.update(delta)
                bt(i + 1, na)
                if sol[0] is not None:
                    return

        bt(0, {})
        if sol[0] is None:
            continue
        prog = assemble(geo, sol[0])
        ok, badx, st, out = simulate_all(prog)
        if ok:
            return prog, geo
        print(f"  simfail at {badx:#x} {st} {out}", flush=True)
    return None, None


if __name__ == "__main__":
    configs = enum_configs()
    # prefer configs whose low band has the larger min-gap (3 beats 2)
    def lowgap(J):
        vs = sorted(J.values())
        gaps = [b - a for a, b in zip(vs, vs[1:]) if b - a < FORCE_GAP]
        return min(gaps) if gaps else 99
    configs.sort(key=lambda c: (-lowgap(c[2]), -min(c[2].values())))
    print(f"{len(configs)} configs", flush=True)
    for idx, (cps, ts, J) in enumerate(configs):
        print(f"config {idx}: pos={cps} t={ts} J={sorted(J.values())}", flush=True)
        prog, geo = solve_config(cps, ts, J, seed=idx)
        if prog is not None:
            print(f"SOLVED(sim) pos={cps} t={ts} len={len(prog)}", flush=True)
            okc, info = native_check(prog)
            print(f"native: {okc}/{len(INPUTS)} {info or ''}", flush=True)
            if okc == len(INPUTS):
                open("SOLUTION.mal", "wb").write(prog)
                print("*** NATIVE ALL -> SOLUTION.mal ***", flush=True)
                sys.exit(0)
    print("pass complete, no solution", flush=True)
