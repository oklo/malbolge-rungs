"""Build a map12-hi program up to the proved 9/12 architecture ceiling.

ceiling.py proves that in the two-stage CRAZY-dispatch family with printable
tail operands, lanes 0x90, 0x9c and 0xf9 can never emit their targets -- their
inputs have trit4 in {1,0}, their targets need accumulator trit4 = 2, and every
printable operand acts on trit4 by g0 or g1, both of which are the swap 0<->1
on {0,1}.  No config, geometry, runway, shape or joint budget changes that.

So the joint search should stop spending cells on them.  This builder drops the
three provably dead lanes and packs only the nine live ones, which both frees
their tail cells for the survivors and removes them from the branching factor.

Usage: python3 research/map12-hi-push/push_build.py CFG NODE_BUDGET [OUT.mal]
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from research.map12hi import base, geometry  # noqa: E402

INPUTS = [0xA5, 0xE0, 0x90, 0x9C, 0x84, 0xA1, 0xBD, 0xC8, 0xBE, 0xF9, 0x86, 0xDD]
TGT = {x: x ^ 0x51 for x in INPUTS}
base.INPUTS = INPUTS
base.TGT = TGT
geometry.INPUTS = INPUTS
geometry.TGT = TGT

DEAD = {0x90, 0x9C, 0xF9}          # proved unreachable, see ceiling.py
LIVE = [x for x in INPUTS if x not in DEAD]

# --- correctness patch over the inherited map8 builder ---------------------
# base.place_code treats a dispatch operand cell (40+cp, i.e. 42..49) as an
# ordinary "fixed" cell and will happily place tail code there if the source
# byte happens to decode to the wanted op.  At runtime those cells have been
# OVERWRITTEN by the dispatch CRAZYs with the lane's intermediate accumulator,
# which is usually not a printable word -- so the program dies with
# "invalid runtime instruction at address 49".  Forbid code on them.
_orig_place_code = base.place_code


def place_code(geo, cells_ops, assign):
    for cell, _op in cells_ops:
        if cell in geo.reserved:
            return None
    return _orig_place_code(geo, cells_ops, assign)


base.place_code = place_code
geometry.place_code = place_code

PLAN_CAP = int(os.environ.get("PLAN_CAP", "600"))
PLAN_BUDGET = int(os.environ.get("PLAN_BUDGET", "600000"))
BINARY = REPO / "target" / "release" / "malbolge-rungs"


def native_score(program: bytes, path: Path):
    """Score with the native `verify` (one process, and it survives crashes)."""
    path.write_bytes(program)
    run = subprocess.run(
        [str(BINARY), "verify", "--rung", "L2.FM2h.xor51-map12-hi",
         "--program", str(path), "--json"],
        capture_output=True, check=False, timeout=120)
    try:
        report = json.loads(run.stdout)
    except Exception:
        return 0, [run.stdout.decode()[:160] or run.stderr.decode()[:160]]
    ep = report["results"][0]["outcome"]["epochs"][0]
    detail = [f"{c['input_hex']}:{'ok' if c['correct'] else (c['observed_hex'] or '-')}"
              for c in ep["cases"]]
    return ep["correct_cases"], detail


def pack(geo, node_budget):
    counts = {x: sum(1 for _ in base.tail_plans(geo, x, {}, cap=64,
                                                attempt_budget=PLAN_BUDGET))
              for x in LIVE}
    live = [x for x in LIVE if counts[x] > 0]
    if not live:
        return 0, None, counts
    order = sorted(live, key=lambda x: counts[x])
    best = [0, None]
    nodes = [0]

    def bt(index, assignment, satisfied):
        if nodes[0] > node_budget:
            return
        if satisfied > best[0]:
            best[0], best[1] = satisfied, dict(assignment)
            print(f"    satisfied={satisfied} nodes={nodes[0]}", flush=True)
        if index == len(order) or satisfied + (len(order) - index) <= best[0]:
            return
        x = order[index]
        for delta in base.tail_plans(geo, x, assignment, cap=PLAN_CAP,
                                     attempt_budget=PLAN_BUDGET):
            nodes[0] += 1
            if nodes[0] > node_budget:
                return
            nxt = dict(assignment); nxt.update(delta)
            bt(index + 1, nxt, satisfied + 1)
        bt(index + 1, assignment, satisfied)

    bt(0, {}, 0)
    return best[0], best[1], counts


def main() -> int:
    cfg_i = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    node_budget = int(sys.argv[2]) if len(sys.argv) > 2 else 40000
    outname = sys.argv[3] if len(sys.argv) > 3 else f"push-cfg{cfg_i}.mal"
    cps, ts, J = base.enum_configs()[cfg_i]
    started = time.monotonic()
    best_overall = (0, None, None)
    outdir = REPO / "research" / "map12-hi-push" / "out"
    outdir.mkdir(exist_ok=True)
    pinned = os.environ.get("PUSH_GEOMS")
    if pinned:
        geoms = [(frozenset(), tuple(int(v) for v in g.split(",") if v))
                 for g in pinned.split(";")]
    else:
        geoms = list(geometry.geometries_for(sorted(J.values())))
    for mask, offs in geoms:
        geo = geometry.GeoV2(cps, ts, J, mask, offs)
        if not getattr(geo, "ok", False) or not hasattr(geo, "base"):
            continue
        claimed, assign, counts = pack(geo, node_budget)
        print(f"cfg{cfg_i} mask={sorted(mask)} offs={offs} claimed={claimed}/9 "
              f"counts={ {hex(k): v for k, v in counts.items()} }", flush=True)
        if assign is None or claimed <= best_overall[0]:
            continue
        prog = base.assemble(geo, assign)
        n, detail = native_score(prog, outdir / outname)
        print(f"  -> native {n}/12  {'  '.join(detail)}", flush=True)
        if n > best_overall[0]:
            best_overall = (n, prog, (sorted(mask), offs))
            (outdir / f"best-{outname}").write_bytes(prog)
        if n >= 9:
            break
    print(f"cfg{cfg_i} BEST native={best_overall[0]}/12 geometry={best_overall[2]} "
          f"wall={time.monotonic()-started:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
