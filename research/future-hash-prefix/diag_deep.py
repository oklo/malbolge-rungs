"""Is the missing second OUT a depth/budget artefact or structural?

Takes one geometry and one lane and re-runs the 2-byte tail DFS with a very
large node budget and a deeper cell window, so a zero here is not a budget zero.
"""
import sys, time, importlib.util
sys.path.insert(0, '.')
sys.argv = ['deep', '0', '20000', '512', '0', '55']
spec = importlib.util.spec_from_file_location("fhp", "research/future-hash-prefix/search_fhp.py")
fhp = importlib.util.module_from_spec(spec); spec.loader.exec_module(fhp)
base = fhp.base
fhp.MAXDEPTH = 18

configs = fhp.enum_configs_n(max_jmax=506, jmin=55)
configs.sort(key=lambda c: -min(c[2].values()))
cps, ts, J = configs[0]
geo = fhp.GeoLen(cps, ts, J, frozenset(), (4,))
print("geometry", sorted(J.values()), sorted(set(geo.station_of.values())), "ok", geo.ok)
for v in fhp.INPUTS:
    t0 = time.time()
    n = 0
    for _ in base.tail_plans(geo, v, {}, max_k=fhp.MAX_K, cap=5,
                             attempt_budget=4_000_000):
        n += 1
    print(f"lane {v:#04x} -> {fhp.TARGETS[v]}  2byte plans={n} "
          f"nodes={base._ATTEMPTS[0]} {time.time()-t0:.1f}s", flush=True)
