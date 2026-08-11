"""Set-packing build for map12-hi's nine live lanes.

ceiling.py proves 0x90 / 0x9c / 0xf9 can never emit their targets in this
architecture, so 9/12 is the exact ceiling.  This packs the nine survivors.

The inherited joint search re-derives every lane's tail plans at every node of
the backtrack, which makes each node cost a full bounded DFS.  A tail plan is
just a partial cell assignment (delta), and a plan derived under the EMPTY
assignment stays valid under any larger assignment it does not conflict with --
cell_value only ever branches on cells the plan itself then pins.  So the joint
problem is plain set packing: enumerate plans once per lane, then search for a
maximum pairwise-compatible selection.  Nodes become dictionary-merge checks
instead of nested DFS, which is what buys the extra lanes.

Usage: python3 research/map12-hi-push/pack9.py CFG "offs" [PLANS_PER_LANE]
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
base.INPUTS, base.TGT = INPUTS, TGT
geometry.INPUTS, geometry.TGT = INPUTS, TGT
DEAD = {0x90, 0x9C, 0xF9}
LIVE = [x for x in INPUTS if x not in DEAD]
BINARY = REPO / "target" / "release" / "malbolge-rungs"

# see push_build.py: tails must never be placed on a dispatch operand cell,
# whose runtime value is the overwritten intermediate accumulator.
_orig_place_code = base.place_code


def place_code(geo, cells_ops, assign):
    for cell, _op in cells_ops:
        if cell in geo.reserved:
            return None
    return _orig_place_code(geo, cells_ops, assign)


base.place_code = place_code
geometry.place_code = place_code


def compatible(a, b):
    if len(b) < len(a):
        a, b = b, a
    for cell, val in a.items():
        if b.get(cell, val) != val:
            return False
    return True


def native(program: bytes, path: Path):
    path.write_bytes(program)
    run = subprocess.run([str(BINARY), "verify", "--rung",
                          "L2.FM2h.xor51-map12-hi", "--program", str(path),
                          "--json"], capture_output=True, check=False, timeout=180)
    try:
        report = json.loads(run.stdout)
    except Exception:
        return -1, [run.stdout.decode()[:200] or run.stderr.decode()[:200]]
    ep = report["results"][0]["outcome"]["epochs"][0]
    return ep["correct_cases"], [
        f"{c['input_hex']}:{'ok' if c['correct'] else (c['observed_hex'] or '-')}"
        for c in ep["cases"]]


def run(cfg_i, offs, per_lane, node_cap):
    cps, ts, J = base.enum_configs()[cfg_i]
    geo = geometry.GeoV2(cps, ts, J, frozenset(), tuple(offs))
    if not getattr(geo, "ok", False) or not hasattr(geo, "base"):
        return None
    t0 = time.monotonic()
    plans = {}
    for x in LIVE:
        seen, out = set(), []
        for delta in base.tail_plans(geo, x, {}, cap=per_lane,
                                     attempt_budget=40_000_000):
            key = tuple(sorted(delta.items()))
            if key in seen:
                continue
            seen.add(key)
            out.append(delta)
        plans[x] = out
    print(f"cfg{cfg_i} offs={offs} plans/lane="
          f"{ {hex(x): len(plans[x]) for x in LIVE} } enum={time.monotonic()-t0:.1f}s",
          flush=True)
    if any(not plans[x] for x in LIVE):
        print(f"  lanes with no plan: {[hex(x) for x in LIVE if not plans[x]]}", flush=True)

    order = sorted([x for x in LIVE if plans[x]], key=lambda x: len(plans[x]))
    best = [0, None]
    nodes = [0]

    def bt(i, assign, sat, chosen):
        if nodes[0] > node_cap:
            return
        if sat > best[0]:
            best[0], best[1] = sat, dict(assign)
            print(f"    satisfied={sat} nodes={nodes[0]} "
                  f"lanes={[hex(c) for c in chosen]}", flush=True)
        if i == len(order) or sat + (len(order) - i) <= best[0]:
            return
        x = order[i]
        for delta in plans[x]:
            nodes[0] += 1
            if nodes[0] > node_cap:
                return
            if not compatible(delta, assign):
                continue
            nxt = dict(assign)
            nxt.update(delta)
            bt(i + 1, nxt, sat + 1, chosen + [x])
        bt(i + 1, assign, sat, chosen)

    bt(0, {}, 0, [])
    if best[1] is None:
        return None
    prog = base.assemble(geo, best[1])
    outdir = REPO / "research" / "map12-hi-push" / "out"
    outdir.mkdir(exist_ok=True)
    path = outdir / f"pack-cfg{cfg_i}-{'_'.join(map(str, offs)) or 'd'}.mal"
    n, detail = native(prog, path)
    print(f"cfg{cfg_i} offs={offs} claimed={best[0]}/9 native={n}/12 len={len(prog)} "
          f"wall={time.monotonic()-t0:.1f}s\n  {'  '.join(detail)}\n  -> {path}",
          flush=True)
    return n, path


if __name__ == "__main__":
    cfg = int(sys.argv[1])
    offs = tuple(int(v) for v in sys.argv[2].split(",") if v != "")
    per_lane = int(sys.argv[3]) if len(sys.argv) > 3 else 4000
    node_cap = int(sys.argv[4]) if len(sys.argv) > 4 else 4_000_000
    run(cfg, offs, per_lane, node_cap)
