# Claude attempt: `L2.FM2h.xor51-map12-hi`

Date: 2026-08-09

Outcome: unsolved

Solver: Claude (Sonnet 5) via Claude Code, working interactively in an agentic
coding session (cloned the repository fresh, no prior local state).

## Summary

`L2.FM2h.xor51-map12-hi` was the lowest-ranked open rung on the board at the
time of this attempt. `feasibility --rung L2.FM2h.xor51-map12-hi` reports
115 separating dispatch configurations and a best minimum landing gap of 1
("hard (separation available, realization is the work)"), as opposed to
`map12-low`'s "wall (dispatch family cannot separate this input set)" — so
`map12-hi` was the intended next target.

The construction used is the map8/map7b two-stage CRAZY-dispatch family,
unmodified in its core logic:

1. A short CRAZY prelude at fixed source positions maps each input byte to a
   distinct "landing" address (the dispatch stage).
2. Landings are grouped into clusters; each cluster gets a `[MOVD, JUMP]`
   station. A lane's walk distance from its landing to its cluster's station
   gives it a lane-specific data pointer.
3. That pointer selects a private second jump into a short lane-specific
   output tail (`NOP*/MOVD?/ROT?/CRAZY* OUT HALT`).
4. Joint byte-assignment backtracking searches for a full program where every
   lane's tail is simultaneously satisfiable without source-cell collisions;
   the diagnostic Python VM checks every complete candidate before native
   checking.

`research/map12hi/base.py` and `research/map12hi/geometry.py` are copies of
`research/map8/{base,geometry}.py`. The INPUTS/TGT module globals are
input-count-agnostic (patched at import time by the search driver), so no
architectural change was needed to point the same construction at twelve
inputs instead of eight. Enumerating configs with `INPUTS` set to map12-hi's
twelve values reproduced the Rust feasibility tool's reported numbers
exactly — 115 separating configs, minimum landing gap 1 — which is good
evidence this is the correct dispatch family for the rung, not just a
plausible one.

## The blocker: an unbounded exhaustive-failure proof

The first real run hung indefinitely on configuration 0. The root cause:
`solve_operands`'s per-lane backtracking (`rec()` in `base.py`) has no bound
on total nodes visited — it only stops early on **success** (24 results
collected). When a lane has **zero** valid tails in a given geometry, proving
that requires exhausting the entire combinatorial tree of tail shapes,
addresses, and legal source-valid bytes at each free cell. For `map8`
(landings roughly in the 55–150 address range) that tree stayed small enough
to be fast in practice. `map12-hi`'s twelve inputs need a longer CRAZY
prelude to separate, pushing landings out to address ~250; the free-cell
address range — and therefore the branching factor at each op position
(`source_valid_bytes` grows with address) and the number of geometrically
valid tail placements that reach `solve_operands` at all — grows enough to
make an exhaustive zero-proof impractically slow.

Fix: added an optional `attempt_budget` to `tail_plans()` (threaded through
`tails_from_v2` and `solve_operands`'s `rec()`) that caps total backtracking
nodes visited per lane-check. Exceeding the budget is treated identically to
genuine exhaustion — both already mean "skip this geometry" to every caller
in `solve_config`, so this introduces no correctness change, only a bound on
worst-case time. This dropped per-config wall time from unbounded/hanging to
single-digit seconds in the common case.

## Search performed

Two full sweeps of all 115 separating configs, smallest-landing-first
(map12-hi's problem is address-range-driven, so — unlike map8's search order
— configs were sorted to try the smallest landing spread first):

| Pass | Splits enumerated per config | Precheck budget/lane | Backtrack budget/lane | Wall time | Result |
|---|---|---|---|---|---|
| 1 | 0–1 | 60,000 | 150,000 | ~400s | 0/115 configs had a fully-live geometry |
| 2 | 0–2 | 150,000 | 300,000 | ~2,448s | 0/115 configs had a fully-live geometry |

"Fully-live" means every one of the twelve lanes had at least one
individually routable tail plan in that geometry — the precondition checked
*before* the expensive joint-assignment backtracking even starts. In both
passes, **no configuration ever reached the backtracking stage**: some lane
always came back with zero individually-findable plans, at every tried
combination of station-split mask (0, 1, or 2 splits) and station-offset
variant (3 variants tried: `()`, `(4,)`, `(8,)`).

This is a real negative result within the tested budget, not a proof of
impossibility — a much larger per-lane attempt budget, more station-offset
variants, 3+ splits, or a materially different tail-shape family could still
find something. But two full sweeps across all 115 separating configs with
a meaningfully large budget (up to 300,000 backtracking nodes just to
individually place one lane's tail) coming back completely empty — not even
one live geometry, let alone a joint solution — is a stronger signal than
map8's own pre-fix search, which found individually-live lanes in every
zero-split config and only failed at the *joint* assignment stage.

## What's reusable for a future attempt

- `research/map12hi/base.py` / `geometry.py`: the attempt-budget patch is a
  strict improvement over the map8 originals and should be safe to port back
  or reuse for `map12-low`, `map16`, or any rung whose landings run past
  `map8`'s address range.
- `research/map12hi_search.py`: reusable driver; smallest-landing-first
  config ordering is likely the right default for any high-range finite-map
  rung (`map12-hi`, `map16`) given this attempt's evidence that address
  range, not split count, was the practical bottleneck.
- The likely next lever isn't more splits — it's the tail-shape family
  itself. Every lane failing at the *individual-routability* check (not the
  joint one) suggests the fixed `SHAPES` catalog in `geometry.py` (bounded
  `NOP*`/`MOVD?`/`ROT?`/`CRAZY*` combinations) may not reach far enough
  addresses, or a fundamentally different station/tail geometry may be
  needed once landings run this far from the program prefix.

## Reproduce

```sh
cargo build -p harness   # debug binary used by native_check
python3 research/map12hi_search.py 0 1 2 20000 3 0 0
```

(The `20000` positional argument is the joint-backtracking node budget,
unused here since no config reached that stage; the per-lane attempt budgets
that actually gated this run are `PRECHECK_BUDGET`/`BACKTRACK_BUDGET`
constants at the top of `research/map12hi_search.py`.)
