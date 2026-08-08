"""map7b v3: breadth-first geometry sweep, parallel workers.

usage: v3.py WORKER NWORKERS MAXSPLITS NODE_BUDGET [NOFFS]
Configs are dealt worker_id::nworkers. Per config, geometries are limited to
masks with <= MAXSPLITS splits and the first NOFFS offset choices, so the
sweep visits every config before deepening anywhere. Pre-counts use cap=300
so the most-constrained lane (0x82 in practice) is placed first.
"""
# As run on 2026-08-07 (lightly edited: /tmp paths generalized to run
# from research/map7/ in the repo; algorithm unchanged).
import os as _os, sys as _sys
_REPO = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import sys, itertools, random
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import build_map7b as B
import v2 as V
from build_map7b import INPUTS, enum_configs, assemble, simulate_all, native_check

WORKER = int(sys.argv[1]); NW = int(sys.argv[2])
MAXSPLITS = int(sys.argv[3]); BUDGET = int(sys.argv[4])
NOFFS = int(sys.argv[5]) if len(sys.argv) > 5 else 3
OFFSETS = [(), (4,), (8,), (12,), (2,), (6,)][:NOFFS]


def geometries(vs):
    bnds = V.splittable_boundaries(vs)
    masks = sorted((frozenset(c) for r in range(0, MAXSPLITS + 1)
                    for c in itertools.combinations(bnds, r)), key=len)
    for mask in masks:
        for offs in OFFSETS:
            yield mask, offs


def solve_config(idx, cps, ts, J):
    vs = sorted(J.values())
    rng = random.Random(idx)
    for mask, offs in geometries(vs):
        geo = V.GeoV2(cps, ts, J, mask, offs)
        if not geo.ok:
            continue
        counts = {}
        bad = False
        for x in INPUTS:
            cnt = sum(1 for _ in B.tail_plans(geo, x, {}, cap=300))
            counts[x] = cnt
            if cnt == 0:
                bad = True
                break
        if bad:
            continue
        order = sorted(INPUTS, key=lambda x: counts[x])
        print(f"[w{WORKER}] cfg{idx} mask={sorted(mask)} offs={offs} "
              f"minplans={counts[order[0]]:#x}:{counts[order[0]]}", flush=True)
        sol = [None]; nodes = [0]

        def bt(i, assign):
            if sol[0] is not None or nodes[0] > BUDGET:
                return
            if i == len(order):
                sol[0] = dict(assign)
                return
            x = order[i]
            plans = list(B.tail_plans(geo, x, assign, cap=400))
            if 1 <= i <= 2:
                rng.shuffle(plans)
            for delta in plans:
                nodes[0] += 1
                na = dict(assign); na.update(delta)
                bt(i + 1, na)
                if sol[0] is not None:
                    return

        bt(0, {})
        if sol[0] is None:
            continue
        prog = assemble(geo, sol[0])
        ok, badx, st, out = simulate_all(prog)
        if ok:
            return prog
        print(f"[w{WORKER}] cfg{idx} simfail {badx:#x} {st} {out}", flush=True)
    return None


if __name__ == "__main__":
    configs = enum_configs()
    def lowgap(J):
        vs = sorted(J.values())
        gaps = [b - a for a, b in zip(vs, vs[1:]) if b - a < V.FORCE_GAP]
        return min(gaps) if gaps else 99
    configs.sort(key=lambda c: (-lowgap(c[2]), -min(c[2].values())))
    mine = list(enumerate(configs))[WORKER::NW]
    print(f"[w{WORKER}] {len(mine)} configs", flush=True)
    for idx, (cps, ts, J) in mine:
        prog = solve_config(idx, cps, ts, J)
        if prog is not None:
            okc, info = native_check(prog)
            print(f"[w{WORKER}] cfg{idx} SOLVED(sim) native {okc}/{len(INPUTS)} {info or ''}",
                  flush=True)
            if okc == len(INPUTS):
                open(f"SOLUTION.mal", "wb").write(prog)
                print(f"[w{WORKER}] *** NATIVE ALL pos={cps} t={ts} -> SOLUTION.mal ***",
                      flush=True)
                sys.exit(0)
    print(f"[w{WORKER}] worker complete, no solution", flush=True)
