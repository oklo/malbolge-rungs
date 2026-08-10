"""Cluster-boundary geometry and richer tail shapes for the map8 search.

Adapted from the map7b builder developed by Fable 5 (Claude Code); map8 adds
the eighth lane, bounded search strata, and complete-layout execution checks.

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
import itertools

from . import base as B
from .base import TGT, nop_byte, place_code, solve_operands
from tools.hell_lite.ops import (source_byte_for_op, NOP, CRAZY, OUT, HALT,
                                 MOVD, IN, JUMP, ROT)

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
            if B._ATTEMPT_BUDGET[0] is not None and B._ATTEMPTS[0] >= B._ATTEMPT_BUDGET[0]:
                return
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
