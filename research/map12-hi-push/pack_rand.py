"""Randomized restart set-packing for the nine live map12-hi lanes.

pack9.py's depth-first branch and bound commits to the lane with the fewest
plans first and then exhausts that subtree; on this instance it plateaus at
five lanes.  The instance is a maximum-compatible-subset problem over ~10k
partial cell assignments, which randomized greedy with restarts handles much
better than DFS: each restart shuffles both the lane order and each lane's
plan list, takes the first compatible plan per lane, and keeps the best.

Plan enumeration is the expensive part (~80s/geometry), so it is cached to
research/map12-hi-push/cache/.

Usage: python3 research/map12-hi-push/pack_rand.py CFG "offs" PLANS RESTARTS
"""
from __future__ import annotations
import json
import os
import pickle
import random
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
CACHE = REPO / "research" / "map12-hi-push" / "cache"
OUT = REPO / "research" / "map12-hi-push" / "out"
CACHE.mkdir(exist_ok=True, parents=True)
OUT.mkdir(exist_ok=True, parents=True)

_orig_place_code = base.place_code


def place_code(geo, cells_ops, assign):
    for cell, _op in cells_ops:
        if cell in geo.reserved:
            return None
    return _orig_place_code(geo, cells_ops, assign)


base.place_code = place_code
geometry.place_code = place_code


def get_geo(cfg_i, offs):
    cps, ts, J = base.enum_configs()[cfg_i]
    geo = geometry.GeoV2(cps, ts, J, frozenset(), tuple(offs))
    if not getattr(geo, "ok", False) or not hasattr(geo, "base"):
        return None
    return geo


def enum_plans(cfg_i, offs, per_lane):
    tag = f"c{cfg_i}-o{'_'.join(map(str, offs)) or 'd'}-n{per_lane}"
    f = CACHE / f"{tag}.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    geo = get_geo(cfg_i, offs)
    if geo is None:
        return None
    plans = {}
    for x in LIVE:
        seen, out = set(), []
        for delta in base.tail_plans(geo, x, {}, cap=per_lane,
                                     attempt_budget=60_000_000):
            key = tuple(sorted(delta.items()))
            if key in seen:
                continue
            seen.add(key)
            out.append(tuple(sorted(delta.items())))
        plans[x] = out
    f.write_bytes(pickle.dumps(plans))
    return plans


def compatible(items, assign):
    for cell, val in items:
        if assign.get(cell, val) != val:
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
        return -1, [(run.stdout or run.stderr).decode()[:200]]
    ep = report["results"][0]["outcome"]["epochs"][0]
    return ep["correct_cases"], [
        f"{c['input_hex']}:{'ok' if c['correct'] else (c['observed_hex'] or '-')}"
        for c in ep["cases"]]


def main():
    cfg = int(sys.argv[1])
    offs = tuple(int(v) for v in sys.argv[2].split(",") if v != "")
    per_lane = int(sys.argv[3]) if len(sys.argv) > 3 else 6000
    restarts = int(sys.argv[4]) if len(sys.argv) > 4 else 20000
    t0 = time.monotonic()
    plans = enum_plans(cfg, offs, per_lane)
    if plans is None:
        print(f"cfg{cfg} offs={offs}: geometry invalid"); return
    lanes = [x for x in LIVE if plans[x]]
    print(f"cfg{cfg} offs={offs} plans={ {hex(x): len(plans[x]) for x in LIVE} } "
          f"enum={time.monotonic()-t0:.1f}s", flush=True)
    rng = random.Random(12345 + cfg)
    best = (0, None, None)
    for it in range(restarts):
        order = lanes[:]
        rng.shuffle(order)
        assign, got, chosen = {}, 0, []
        for x in order:
            pl = plans[x]
            # size-biased: a packing heuristic, prefer plans that pin fewer
            # cells so later lanes keep more of the 47-60 cell free window.
            idxs = rng.sample(range(len(pl)), min(len(pl), 2500))
            idxs.sort(key=lambda i: (len(pl[i]), rng.random()))
            for i in idxs:
                items = pl[i]
                if compatible(items, assign):
                    assign.update(items)
                    got += 1
                    chosen.append(x)
                    break
        if got > best[0]:
            best = (got, dict(assign), sorted(chosen))
            print(f"  restart {it}: satisfied={got}/9 lanes={[hex(c) for c in best[2]]}",
                  flush=True)
            if got == len(lanes):
                break
    geo = get_geo(cfg, offs)
    prog = base.assemble(geo, best[1])
    path = OUT / f"rand-c{cfg}-o{'_'.join(map(str, offs)) or 'd'}.mal"
    n, detail = native(prog, path)
    print(f"cfg{cfg} offs={offs} claimed={best[0]}/9 NATIVE={n}/12 len={len(prog)} "
          f"wall={time.monotonic()-t0:.1f}s\n  {'  '.join(detail)}\n  -> {path}", flush=True)


if __name__ == "__main__":
    main()
