"""Bounded five-epoch hash lookup synthesis, extending the map8 geometry builder.

Run from repository root: python3 research/astra-2026-09-05/search.py
The native verifier, not this diagnostic search, decides correctness.
"""
import itertools
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.map8 import base, geometry

HERE = Path(__file__).resolve().parent
RUNG = sys.argv[1] if len(sys.argv) > 1 else 'L4.R0.hash-prefix-1'
KEY = int(sys.argv[2]) if len(sys.argv) > 2 else 0
rows = [r for r in json.loads((HERE / 'cases.json').read_text()) if r['rung'] == RUNG]
targets = {bytes.fromhex(r['input_hex'])[KEY]: int(r['expected_hex'], 16) for r in rows}
inputs = {bytes.fromhex(r['input_hex'])[KEY]: bytes.fromhex(r['input_hex']) for r in rows}
assert len(targets) == len(rows), 'first-byte collision requires a different key'
base.INPUTS = sorted(targets)
base.TGT = geometry.TGT = targets
start = time.monotonic()
log = (HERE / ('search-' + RUNG + '-key' + str(KEY) + '.jsonl')).open('a', buffering=1)

def diagnostic(program):
    return all((r := base.execute_python(program, inputs[x], max_steps=2048, max_output_len=1)).status == 'halt'
               and r.output == [targets[x]] for x in targets)

def event(**kw):
    kw['elapsed_seconds'] = round(time.monotonic() - start, 3)
    log.write(json.dumps(kw) + '\n')
    print(json.dumps(kw), flush=True)

event(kind='start', rung=RUNG, key=KEY, targets=targets, tail_node_cap=10000, plan_cap=60)
configs = [c for c in base.enum_configs(max_jmax=940) if min(c[0]) > KEY + 1]
configs.sort(key=lambda c: (-min(b-a for a,b in zip(sorted(c[2].values()), sorted(c[2].values())[1:])), -min(c[2].values())))
event(kind='configs', count=len(configs))
for ci, (cps, ts, landings) in enumerate(configs):
    if time.monotonic() - start > 900:
        break
    for mask, offsets in geometry.geometries_for(sorted(landings.values())):
        geo = geometry.GeoV2(cps, ts, landings, mask, offsets)
        if not geo.ok or geo.proglen > 1024:
            continue
        for address in range(2, KEY + 2):
            geo.base[address] = base.source_byte_for_op(base.IN, address)
        plans = {x: list(base.tail_plans(geo, x, {}, cap=60, attempt_budget=10000)) for x in targets}
        if not all(plans.values()):
            continue
        order = sorted(targets, key=lambda x: len(plans[x]))
        nodes = [0]
        def rec(i, assignment):
            nodes[0] += 1
            if nodes[0] > 10000:
                return None
            if i == len(order):
                p = base.assemble(geo, assignment)
                return p if diagnostic(p) else None
            x = order[i]
            for delta in base.tail_plans(geo, x, assignment, cap=100, attempt_budget=15000):
                result = rec(i + 1, {**assignment, **delta})
                if result is not None:
                    return result
            return None
        program = rec(0, {})
        event(kind='geometry', config=ci, cps=cps, operands=ts, landings=landings,
              mask=sorted(mask), offsets=offsets, plans={x:len(p) for x,p in plans.items()},
              nodes=nodes[0], diagnostic_pass=program is not None)
        if program is not None:
            dest = HERE / (RUNG + '-key' + str(KEY) + '.mal')
            dest.write_bytes(program)
            event(kind='candidate', path=str(dest.relative_to(ROOT)), length=len(program))
            raise SystemExit(0)
    if ci % 10 == 0:
        event(kind='progress', config=ci)
event(kind='stopped', config=ci)
