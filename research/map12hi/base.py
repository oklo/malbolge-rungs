"""Shared two-stage dispatch primitives for the map8 construction search.

Adapted from the map7b builder developed by Fable 5 (Claude Code); see the
map7b leaderboard record and the map8 attempt report for provenance.

Geometry v2: one [MOVD,JUMP] station per landing *cluster*.
  - stage-1 crz-dispatch lands lane x at J(x)+1, a=J(x), d=50.
  - sorted J's are grouped into clusters (split where gap >= 3).
  - cluster k gets a station at m_k >= maxJ_k + 2 (staggered so pointer
    cells don't collide across clusters); cells between landings and the
    station are NOPs.  Lanes above a station never touch it; lanes below
    were already redirected at their own station.
  - at station m, lane x has d = m + 49 - J(x)  ~ 51..62: a never-executed
    cell whose byte we CHOOSE (8 loader-valid options) -> p.
  - JUMP reads mem[p+1] -> T (chosen if free), lane lands at T+1 with
    a = J(x), d = p + 2 -> private tail anywhere in dead space.
  - tails: NOP*k [MOVD]? [ROT]? CRAZY*n OUT HALT over the d-trail.

Full-program validation via tools.hell_lite execute_python, then native.
"""
import itertools

from tools.hell_lite.ops import (
    crazy_word, rotate_right_word, source_valid_bytes, source_byte_for_op,
    encipher_word, decode_op,
    NOP, CRAZY, OUT, HALT, MOVD, IN, JUMP, ROT,
)
from tools.hell_lite.score import execute_python

INPUTS = [0x02, 0x06, 0x09, 0x30, 0x82, 0x6f, 0xa7, 0xc0]
TGT = {x: x ^ 0x51 for x in INPUTS}
E = encipher_word

def nop_byte(addr):
    return source_byte_for_op(NOP, addr)

def enum_configs(max_jmax=1300):
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
                if len(set(vs)) != len(INPUTS) or vs[0] < 55 or vs[-1] > max_jmax:
                    continue
                out.append((tuple(cps), ts, J))
    return out

def intermediates(cps, ts, x):
    vals = {}
    a = x
    for cp, t in zip(cps, ts):
        a = crazy_word(a, t)
        vals[40 + cp] = a
    return vals

class Geo:
    def __init__(self, cps, ts, J):
        self.cps, self.ts, self.J = cps, ts, J
        self.reserved = {40 + cp: t for cp, t in zip(cps, ts)}
        self.reserved[50] = 48
        base = {0: 40, 1: source_byte_for_op(IN, 1)}
        for i in range(2, 10):
            base[i] = source_byte_for_op(CRAZY if i in cps else NOP, i)
        base[10] = source_byte_for_op(MOVD, 10)
        base[11] = source_byte_for_op(JUMP, 11)
        for cell, b in self.reserved.items():
            base[cell] = b
        # clusters over sorted J values
        vs = sorted(J.values())
        clusters = [[vs[0]]]
        for j in vs[1:]:
            # station needs maxJ+2, next landing at J_next+1 must be > m+1
            if j - clusters[-1][-1] >= 3 + 0:  # provisional; stagger may merge
                clusters.append([j])
            else:
                clusters[-1].append(j)
        self.station_of = {}
        next_free_ptr = 51
        self.ok = True
        for ci, cl in enumerate(clusters):
            lo, hi = cl[0], cl[-1]
            budget = (clusters[ci + 1][0] - 1 - (hi + 2)) if ci + 1 < len(clusters) else 40
            want = next_free_ptr - 51
            o = min(max(want, 0), budget)
            m = hi + 2 + o
            for j in cl:
                self.station_of[j] = m
            # walk NOPs and station
            for cell in range(lo + 1, m):
                base[cell] = nop_byte(cell)
            base[m] = source_byte_for_op(MOVD, m)
            base[m + 1] = source_byte_for_op(JUMP, m + 1)
            next_free_ptr = m + 49 - lo + 1
        last_station = max(self.station_of.values())
        self.proglen = max(last_station + 2, 150)
        self.base = base

    def lane_env(self, x):
        Jx = self.J[x]
        m = self.station_of[Jx]
        return Jx, m

    def zone(self, cell):
        if cell in self.base:
            return "fixed"
        if 12 <= cell < self.proglen:
            return "free"
        return "out"

    def cell_value(self, cell, x, assign, extra_enc=()):
        """(value, choices) as seen by lane x during its tail."""
        Jx, m = self.lane_env(x)
        z = self.zone(cell)
        if z == "out":
            return None, None
        if z == "fixed":
            if cell == 49:
                return Jx, None
            iv = intermediates(self.cps, self.ts, x)
            if cell in iv:
                return iv[cell], None
            b = self.base[cell]
            if (Jx + 1 <= cell <= m + 1) or cell == Jx or cell in extra_enc:
                return E(b), None
            return b, None
        if cell in assign:
            b = assign[cell]
            if cell in extra_enc:
                b = E(b)
            return b, None
        if cell in extra_enc:
            return None, [(b, E(b)) for b in source_valid_bytes(cell)]
        return None, [(b, b) for b in source_valid_bytes(cell)]

def place_code(geo, cells_ops, assign):
    delta = {}
    for cell, op in cells_ops:
        z = geo.zone(cell)
        if z == "out":
            return None
        if z == "fixed":
            if decode_op(geo.base[cell], cell) != op:
                return None
            continue
        cur = assign.get(cell, delta.get(cell))
        b = source_byte_for_op(op, cell)
        if cur is not None:
            if cur != b:
                return None
        else:
            delta[cell] = b
    return delta

# Attempt-budget guard: solve_operands' rec() has no native bound on total
# nodes visited when a lane has zero valid tails in a geometry -- it must
# otherwise exhaust the full combinatorial tree to prove that. map12-hi's
# larger landing spread (vs map8) inflates that tree enough to hang for a
# very long time. _ATTEMPTS/_ATTEMPT_BUDGET give tail_plans() an optional
# total-node cap; exceeding it is treated the same as genuine exhaustion
# (stop yielding) rather than raising, since callers already treat a
# zero-yield result as "skip this geometry."
_ATTEMPTS = [0]
_ATTEMPT_BUDGET = [None]

def tail_plans(geo, x, assign, max_k=8, max_n=3, cap=None, attempt_budget=None):
    _ATTEMPTS[0] = 0
    _ATTEMPT_BUDGET[0] = attempt_budget
    Jx, m = geo.lane_env(x)
    q = m + 49 - Jx
    emitted = [0]
    v, choices = geo.cell_value(q, x, assign)
    p_opts = ([(v, {})] if choices is None and v is not None else
              [(vv, {q: b}) for b, vv in (choices or [])])
    for p, asg_p in p_opts:
        if not isinstance(p, int):
            continue
        r = p + 1
        if not (12 <= r < geo.proglen):
            continue
        a1 = dict(assign); a1.update(asg_p)
        v2, ch2 = geo.cell_value(r, x, a1)
        T_opts = ([(v2, {})] if ch2 is None and v2 is not None else
                  [(vv, {r: b}) for b, vv in (ch2 or [])])
        for T, asg_t in T_opts:
            L = T + 1
            if not (12 <= L < geo.proglen - 2):
                continue
            a2 = dict(a1); a2.update(asg_t)
            for delta in tails_from(geo, x, Jx, L, p + 2, a2,
                                    {**asg_p, **asg_t}, max_k, max_n):
                yield delta
                emitted[0] += 1
                if cap and emitted[0] >= cap:
                    return
                if _ATTEMPT_BUDGET[0] is not None and _ATTEMPTS[0] >= _ATTEMPT_BUDGET[0]:
                    return
            if _ATTEMPT_BUDGET[0] is not None and _ATTEMPTS[0] >= _ATTEMPT_BUDGET[0]:
                return
        if _ATTEMPT_BUDGET[0] is not None and _ATTEMPTS[0] >= _ATTEMPT_BUDGET[0]:
            return

def tails_from(geo, x, Jx, L, d0, assign, acc_delta, max_k, max_n):
    tgt = TGT[x]
    Tcell = L - 1  # enciphered by the stage-2 jump before the tail runs
    for k in range(0, max_k + 1):
        for use_movd in (False, True):
            for use_rot in (False, True):
                for n in range(0, max_n + 1):
                    if not use_rot and n == 0:
                        continue  # need something feeding OUT deterministically? plain a=Jx allowed if n==0? out=Jx%256 rarely target; skip
                    ops = [NOP] * k + ([MOVD] if use_movd else []) + \
                          ([ROT] if use_rot else []) + [CRAZY] * n + [OUT, HALT]
                    cells = list(range(L, L + len(ops)))
                    code_delta = place_code(geo, list(zip(cells, ops)), assign)
                    if code_delta is None:
                        continue
                    a3 = dict(assign); a3.update(code_delta)
                    yield from solve_operands(
                        geo, x, Jx, tgt, ops, d0, a3,
                        {**acc_delta, **code_delta}, Tcell)

def solve_operands(geo, x, Jx, tgt, ops, d0, assign, acc_delta, Tcell):
    results = []
    extra_enc = (Tcell,)
    def rec(i, a_val, d_cur, cur_assign, cur_delta):
        if len(results) >= 24:
            return
        _ATTEMPTS[0] += 1
        if _ATTEMPT_BUDGET[0] is not None and _ATTEMPTS[0] >= _ATTEMPT_BUDGET[0]:
            return
        if i == len(ops):
            return
        op = ops[i]
        if op == NOP:
            rec(i + 1, a_val, d_cur + 1, cur_assign, cur_delta); return
        if op == OUT:
            if a_val is not None and a_val % 256 == tgt:
                results.append(cur_delta)
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
                na = dict(cur_assign); na.update(dd)
                rec(i + 1, a_val, vv + 1, na, {**cur_delta, **dd})
            return
        if op == ROT:
            for vv, dd in opts:
                na = dict(cur_assign); na.update(dd)
                rec(i + 1, rotate_right_word(vv), d_cur + 1, na, {**cur_delta, **dd})
            return
        if op == CRAZY:
            if a_val is None:
                return
            for vv, dd in opts:
                na = dict(cur_assign); na.update(dd)
                rec(i + 1, crazy_word(a_val, vv), d_cur + 1, na, {**cur_delta, **dd})
            return
    rec(0, Jx, d0, assign, acc_delta)
    yield from results

def assemble(geo, assign):
    prog = bytearray()
    for cell in range(geo.proglen):
        if cell in geo.base:
            prog.append(geo.base[cell])
        elif cell in assign:
            prog.append(assign[cell])
        else:
            prog.append(nop_byte(cell))
    return bytes(prog)

def simulate_all(prog):
    for x in INPUTS:
        r = execute_python(prog, bytes([x]), max_steps=2048, max_output_len=1)
        if not (r.status == "halt" and r.output == [TGT[x]]):
            return False, x, r.status, r.output
    return True, None, None, None
