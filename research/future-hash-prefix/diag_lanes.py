"""Per-lane feasibility of 1-byte vs 2-byte tails, on the first few geometries.

Isolates which half of the tail is the wall: count how many tail plans each
lane has when only the FIRST target byte must be emitted (the L4 shape) versus
when both bytes must be emitted (this rung's shape).
"""
import sys, time
sys.path.insert(0, '.')
import importlib
fhp = importlib.import_module('research.future-hash-prefix.search_fhp'.replace('-', '_')) if False else None
sys.argv = ['diag', '0', '20000', '512', '0', '55']
import importlib.util
spec = importlib.util.spec_from_file_location(
    "fhp", "research/future-hash-prefix/search_fhp.py")
fhp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fhp)
base, geometry = fhp.base, fhp.geometry

configs = fhp.enum_configs_n(max_jmax=506, jmin=55)
configs.sort(key=lambda c: -min(c[2].values()))
print(len(configs), "configs")

start = time.time()
tried = 0
for idx, (cps, ts, J) in enumerate(configs):
    if time.time() - start > float(sys.argv[6]) if len(sys.argv) > 6 else False:
        break
    for mask, offs in fhp.geometries_for(sorted(J.values()), 0, [(), (4,), (8,)]):
        geo = fhp.GeoLen(cps, ts, J, mask, offs)
        if not geo.ok:
            continue
        tried += 1
        one, two = [], []
        for v in fhp.INPUTS:
            fhp.TARGETS_FULL = fhp.TARGETS
            # 1-byte mode: pretend the tail only owes the first byte
            fhp.TARGETS = {k: (t[0],) for k, t in fhp.TARGETS_FULL.items()}
            one.append(sum(1 for _ in base.tail_plans(geo, v, {}, max_k=fhp.MAX_K,
                                                      cap=50, attempt_budget=60000)))
            fhp.TARGETS = fhp.TARGETS_FULL
            two.append(sum(1 for _ in base.tail_plans(geo, v, {}, max_k=fhp.MAX_K,
                                                      cap=50, attempt_budget=60000)))
        print(f"cfg{idx} J={sorted(J.values())} m={sorted(set(geo.station_of.values()))} "
              f"1byte={one} 2byte={two}", flush=True)
        if tried >= int(sys.argv[7] if len(sys.argv) > 7 else 8):
            raise SystemExit(0)
