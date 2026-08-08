# map6 / map7a / map7b construction searches

The builders behind the Fable 5 solves of `L2.FM1b.xor51-map6`,
`L2.FM1c.xor51-map7a`, and `L2.FM1d.xor51-map7b`, published as run (paths
generalized so they execute from this directory; algorithms unchanged).

| File | Solve | Run |
|------|-------|-----|
| `build_map7a.py` | map7a, 2026-08-06 | `python3 build_map7a.py` — second config solved in ~2 min |
| `build_map7b.py` | (base for v2/v3) | the same builder with `0xc0` as the seventh input; fails all 50 configs standalone |
| `v2.py` | map7b geometry variants | cluster-boundary masks + station offsets + richer tails over `build_map7b.py` |
| `v3.py` | map7b, 2026-08-07 | breadth-first parallel sweep: `python3 v3.py <worker> <nworkers> <maxsplits> <budget>`; six workers solved three configs in minutes |

`build_map7a.py` with `INPUTS` edited to the six map6 bytes reproduces the
map6 solve (first feasible config). Build the native evaluator first
(`cargo build`); the scripts confirm every simulated hit with it and write
`SOLUTION.mal` to the working directory only on a native pass.

The architecture the code implements — even-CRAZY dispatch prelude, per-cluster
MOVD+JUMP stations, walk-distance pointer cells at `m+49−J`, per-lane tail
plans joined by byte-consistency backtracking — is described in the solved
rungs' board notes. The map8 continuation (one-split station geometry, by
Codex) is in `../map8_search.py` and `../map8/`.
