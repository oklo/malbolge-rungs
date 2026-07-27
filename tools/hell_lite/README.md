# HeLL-Lite

HeLL-Lite is a small construction aid for classic Malbolge programs used in
MAL-51 research. It is inspired by HeLL/LMAO and related Malbolge programming
work, but it is not a full assembler or compiler.

HeLL-Lite is an authoring/diagnostic aid, not an official evaluator. Its Python
VM is diagnostic-only: the sole ground truth is the native Classic-Malbolge-51
evaluator in the `classic_malbolge` crate, reached through the `malbolge-rungs`
harness CLI. Always confirm a candidate by verifying it natively
(`malbolge-rungs verify --rung <id> --program <file>`); never trust a rung as
solved from a Python/hell_lite result alone.

## What It Does

- Compile simple first-use operation sequences into source-valid classic
  Malbolge bytes.
- Inspect instruction cycles at fixed addresses.
- Load and validate deterministic labeled layout sketches.
- Compile simple linear labeled layouts, including `IN,OUT,HALT -> ubO`.
- Parse and report finite-map targets such as `09:58,30:61`.
- Produce bounded routing-search reports for small diagnostic maps.
- Emit non-executable JUMP/loop planning reports that list the missing layout
  constraints.
- Describe small Phase 3 operation units and search for cycle-compatible unit
  cells.
- Emit D-as-PC planning sketches for input/output/branch layouts.
- Attempt tiny finite-map compiles and report an explicit `compile_status`.
- Compare candidate behavior against explicit byte pairs.
- Extract file-backed finite-map targets from raw MAL-51 match artifacts.
- Produce bounded branch-allocation planning reports that preserve known
  successes while targeting one specified failing lane.
- Emit compact diagnostic traces for explicit full-input or one-byte pairs.
- Run trace-guided route surgery to compare pass/fail traces and identify
  divergence, collisions, JUMP/MOVD targets, patchable cells, and dangerous
  shared cells.
- Search bounded source-valid local edits from a route-surgeon report while
  preserving extracted successes as hard constraints.
- Orchestrate route diagnosis plus patch enumeration into a branch repair
  report.
- List known internal construction specimens separately from search rankings.
- Represent small JSON sketches for straight-line and source-tail CRAZY
  templates.
- Explore source-tail CRAZY chains where legal source bytes after `HALT` are
  used as operands.
- Score finite byte mappings with a local Python VM for diagnostics. Score JSON
  uses `per_input_results` for per-input records.
- Optionally spot-check a candidate through the Rust CLI with `verify-rust`.

The Python VM is a heuristic construction tool. Cross-check important candidates
with:

```sh
cargo run -p harness -- execute --program candidate.mal --input-hex 61
```

or with the MAL-51 runner/sweep commands.

Spot-check one input through the Rust CLI:

```sh
python3 -m tools.hell_lite.cli verify-rust \
  --candidate fixtures/classic/echo_first_byte.mal \
  --input-hex 61 \
  --repo-root .
```

## Examples

Compile a straight-line echo-one-byte program:

```sh
python3 -m tools.hell_lite.cli compile-linear --ops IN,OUT,HALT
```

Expected source:

```text
ubO
```

Inspect an instruction cycle:

```sh
python3 -m tools.hell_lite.cli cycles --address 0 --visits 8
```

Score a candidate locally:

```sh
python3 -m tools.hell_lite.cli score \
  --candidate fixtures/classic/echo_first_byte.mal \
  --target echo1 \
  --inputs 61,ff
```

Search source-tail CRAZY chains for xor1 diagnostics:

```sh
python3 -m tools.hell_lite.cli search-tail-crazy \
  --target xor1 \
  --max-crazy 3 \
  --max-results 5 \
  --max-candidates 50000 \
  --out /tmp/hell-lite-tail-results
```

Validate and compile a Phase 2 layout sketch:

```sh
python3 -m tools.hell_lite.cli validate-layout \
  --sketch tools/hell_lite/examples/layout_echo1.json

python3 -m tools.hell_lite.cli compile-layout \
  --sketch tools/hell_lite/examples/layout_echo1.json
```

Find cells whose repeated visits match a requested cycle:

```sh
python3 -m tools.hell_lite.cli find-cycle \
  --cycle NOP,MOVD \
  --address-start 0 \
  --address-end 500
```

Find operation-unit cells for a requested cycle:

```sh
python3 -m tools.hell_lite.cli find-unit-cells \
  --cycle NOP,MOVD \
  --address-start 0 \
  --address-end 2000
```

Inspect a target relation:

```sh
python3 -m tools.hell_lite.cli target-info --target xor1 --inputs 09,30,82
```

Run a small routing-search scaffold:

```sh
python3 -m tools.hell_lite.cli search-routing \
  --target finite-map \
  --pairs 09:58,30:61 \
  --template source-tail-crazy \
  --max-results 5 \
  --max-candidates 1000
```

Emit a planning-only loop sketch:

```sh
python3 -m tools.hell_lite.cli loop-sketch \
  --kind input-output-loop \
  --out /tmp/hell-lite-loop-sketch.json
```

Emit a Phase 3 D-as-PC planning sketch:

```sh
python3 -m tools.hell_lite.cli d-as-pc-sketch \
  --kind two-value-branch \
  --out /tmp/hell-lite-d-as-pc-two-value.json
```

Attempt a tiny finite-map compile. Reports use `compile_status` values such as
`executable_candidate`, `diagnostic_candidate_only`, `planning_only`, and
`failed_constraints`; `planning_only` is an honest construction artifact, not a
match claim.

```sh
python3 -m tools.hell_lite.cli compile-finite-map \
  --pairs 02:53,06:57 \
  --out /tmp/hell-lite-map2

python3 -m tools.hell_lite.cli compile-finite-map \
  --pairs 02:53,06:57,82:d3 \
  --out /tmp/hell-lite-map3
```

Compare a candidate against explicit pairs with the Python diagnostic VM:

```sh
python3 -m tools.hell_lite.cli compare-map \
  --candidate /tmp/hell-lite-map2/candidate.mal \
  --pairs 02:53,06:57,82:d3
```

Extract the Codex 012 xor4096 finite-map frontier from raw match artifacts:

```sh
python3 -m tools.hell_lite.cli extract-match-map \
  --match-dir path/to/match-artifacts \
  --rung L2.R0d.xor-1-len4096 \
  --turn 012-codex \
  --out /tmp/hell-lite-codex012-map
```

This writes `extracted-map.json` and `extracted-map.md`. The extractor reports
the source path and status for each pair and records uncertainties when raw
input bytes are missing from an evaluator report.

Attempt a Phase 4 branch-allocation plan from a seed candidate:

```sh
python3 -m tools.hell_lite.cli allocate-branch \
  --map /tmp/hell-lite-codex012-map/extracted-map.json \
  --seed-candidate path/to/match-artifacts/rungs/L2.R0d.xor-1-len4096/turns/012-codex/candidate.mal \
  --add-target f0:a1 \
  --out /tmp/hell-lite-branch-alloc-f0 \
  --max-candidates 50000
```

The allocator treats extracted pass rows as hard preservation constraints. It
may emit `planning_only`; that is useful construction information, not a
solution claim. If a match target has a full official input vector, the map
keeps that full hex string even when the CLI target is supplied as a prefix
such as `f0:a1`.

Compare compact diagnostic traces:

```sh
python3 -m tools.hell_lite.cli compare-trace \
  --candidate fixtures/classic/echo_first_byte.mal \
  --pairs 61:61,ff:ff \
  --max-ops 20
```

`compare-trace` uses the Python diagnostic VM. It reports first-N operations,
steps, output, JUMP/MOVD targets when available, final `A/C/D`, and a compact
multi-input divergence summary, but it is not a Rust trace.

Run Phase 5 trace-guided branch repair on the Codex 012 frontier:

```sh
python3 -m tools.hell_lite.cli route-surgeon \
  --candidate path/to/match-artifacts/rungs/L2.R0d.xor-1-len4096/turns/012-codex/candidate.mal \
  --map /tmp/hell-lite-codex012-map/extracted-map.json \
  --target-index 0 \
  --max-ops 80 \
  --out /tmp/hell-lite-route-surgeon-f0

python3 -m tools.hell_lite.cli patch-enum \
  --candidate path/to/match-artifacts/rungs/L2.R0d.xor-1-len4096/turns/012-codex/candidate.mal \
  --map /tmp/hell-lite-codex012-map/extracted-map.json \
  --target-index 0 \
  --route-report /tmp/hell-lite-route-surgeon-f0/route-surgeon-report.json \
  --out /tmp/hell-lite-patch-enum-f0 \
  --max-sites 12 \
  --max-edits 2 \
  --max-candidates 50000

python3 -m tools.hell_lite.cli repair-branch \
  --map /tmp/hell-lite-codex012-map/extracted-map.json \
  --seed-candidate path/to/match-artifacts/rungs/L2.R0d.xor-1-len4096/turns/012-codex/candidate.mal \
  --target-index 0 \
  --out /tmp/hell-lite-repair-branch-f0 \
  --max-candidates 50000
```

For the Codex 012 map, `--target-index 0` is the file-backed
`f05d... -> a1` failure. These tools are diagnostic only. `patch-enum` may
return `planning_only` with a blocker report; this is useful construction
evidence, not a solution.

List internal specimens:

```sh
python3 -m tools.hell_lite.cli list-specimens
```

Known internal specimens can be reported separately from ranked search results:

```sh
python3 -m tools.hell_lite.cli search-tail-crazy \
  --target xor1 \
  --max-crazy 3 \
  --max-results 5 \
  --include-known-specimens \
  --out /tmp/hell-lite-tail-results
```

Summarize the current source-tail CRAZY search family:

```sh
python3 -m tools.hell_lite.cli analyze-tail-crazy \
  --target xor1 \
  --max-crazy 3 \
  --max-candidates 50000 \
  --include-known-specimens \
  --out /tmp/hell-lite-tail-analysis
```

`search-tail-crazy` and `analyze-tail-crazy` reject `--max-crazy` values above
4 unless `--allow-large-search` is supplied. The search grows
combinatorially. `analyze-tail-crazy` is bounded by default and reports
`candidates_tested` and `truncated`; truncated results are best found in the
bounded scan, not global maxima.

Exhaustive tail analysis is opt-in:

```sh
python3 -m tools.hell_lite.cli analyze-tail-crazy \
  --target xor1 \
  --max-crazy 3 \
  --exhaustive \
  --allow-large-search \
  --out /tmp/hell-lite-tail-analysis
```

Run the quick smoke check:

```sh
python3 -m tools.hell_lite.cli smoke
```

## Safe Commands During A MAL-51 Bout

These commands are intended to be safe for match-turn setup and diagnostics:

- `compile-linear`
- `validate-layout`
- `compile-layout`
- `target-info`
- `score` with a small input list
- `verify-rust` for spot-checking important candidates
- `cycles`
- `find-cycle` with small address ranges
- `find-unit-cells` with small address ranges
- `unit-catalog`
- `d-as-pc-sketch`
- `compile-finite-map` for two-, three-, and four-value drills
- `compare-map` on explicit small pair lists
- `extract-match-map` for read-only extraction from raw match artifacts
- `allocate-branch` with explicit bounds
- `compare-trace` with small pair lists
- `list-specimens`
- `search-tail-crazy` with small `--max-crazy`, `--max-results`, and
  `--max-candidates`
- `analyze-tail-crazy` only with explicit `--max-candidates`
- `search-routing` only with explicit `--max-candidates`
- `smoke`

Normal unit tests avoid exhaustive searches and should complete quickly. Heavy
search should never be part of a normal match-turn sanity check.

## Phase 4 Finite-Map Allocator

Phase 4 starts turning the Codex 008-012 routed/trampoline trail into explicit
finite-map tooling. It adds:

- `match_extract.py` for file-backed extraction of visible, holdout, blocks=3,
  passed, failed, and uncertain pairs.
- `branch_alloc.py` for a source-valid, cycle-aware planning report around a
  seed candidate and one target lane.
- `trace_compare.py` for compact diagnostic traces over explicit full-input or
  one-byte pairs.
- `examples/codex012_preserve_plus_f0.json` as the current focused target:
  preserve Codex 012's known successes and add `f05d... -> a1`.

The allocator is not a full branch-on-read compiler. It does not yet synthesize
restore/fixup cells, a general layout solver, or a real source-valid table
router. Its `compile_status` must be respected. `planning_only` means the tool
made constraints explicit but did not produce an executable improvement.

## Phase 5 Trace-Guided Branch Repair

Phase 5 adds `route_surgeon.py`, `patch_enum.py`, and a `repair-branch`
workflow. The surgeon compares preserved-success traces with the selected
failure and marks shared lanes, branch targets, patchable source-valid cells,
and dangerous cells. The patch enumerator searches bounded local edits using
only legal source bytes, with known successes enforced as hard constraints.

This is not a full branch-on-read compiler, restore/fixup compiler, or general
layout solver. There is no guarantee that a local patch exists, and no full
xor1 solution is known. Official evaluation still requires Rust CLI runner,
sweep, or classic-execute reports.

## Heavy Diagnostics

Large searches are allowed only deliberately. Use explicit bounds, checkpoint
best-so-far artifacts outside the repo or inside a match turn's scratch area,
and record the command that produced them. Exhaustive source-tail analysis
requires `--exhaustive --allow-large-search`. Do not confuse HeLL-Lite
diagnostics with official MAL-51 results. Candidate artifacts from HeLL-Lite
still require the Rust `classic execute`, MAL-51 runner, or MAL-51 sweep
reports before any match claim is made.

## Current Xor4096 Specimens

The known specimen report includes:

- Codex `005-codex`: 55-byte source-tail CRAZY diagnostic, `3/256` all-byte
  xor hits, visible failed.
- Claude `006-claude`: 81-byte source-tail CRAZY diagnostic, `11/256`
  all-byte xor hits, visible failed.
- Codex `007-codex`: executable two-input JUMP/routing branch,
  `0x02 -> 0x53` and `0x06 -> 0x57`, visible failed.
- Codex `008-codex`: visible plus `5/5` one-block holdout routed construction,
  blocks=3 failed, all-byte one-input score remained low.

The current diagnostic evidence suggests fixed source-tail CRAZY chains are
useful for finite-map islands, but this tested family has not produced a
visible or holdout-passing `xor1` program. The next promising direction is
JUMP/loop or HeLL/LMAO-style layout construction, not more constant-output or
fixed source-tail CRAZY polishing.

## Phase 2 Layout Layer

Phase 2 adds a tiny Nagoya/LAL/HeLL-inspired structure layer:

- `layout.py`: JSON-friendly sections, labels, code/data cells, cycle specs,
  constraints, validation, and a linear layout compiler.
- `targets.py`: `echo1`, `xor1`, and explicit finite-map target helpers.
- `routing.py`: deterministic routing-search report scaffolds for small maps.
- `loop_sketch.py`: planning reports for JUMP/loop work.
- `examples/layout_echo1.json`: labeled echo sketch that compiles to `ubO`.
- `examples/layout_two_value_map.json`: two-input diagnostic target.
- `examples/layout_xor1_toy.json`: xor1 diagnostic sketch, not a solution.

The useful near-term drill is: compile `echo1` from layout, score a two-value
finite map, expand to a four-value map, write a route sketch, then return to
full `xor1`.

## Phase 3 Operation Units

Phase 3 adds L-Ass-Lite operation-unit and D-as-PC planning tools. This is a
tiny internal construction layer inspired by Nagoya/LAL/L-Ass/HeLL practice:
describe an operation unit, find source-valid cells with useful instruction
cycles, plan where `D` must point, and record what restore/fixup work is still
missing.

New modules:

- `units.py`: JSON-friendly operation-unit catalog, unit cells, calls, and
  restore plans.
- `unit_search.py`: bounded cycle-to-unit-cell search.
- `d_as_pc.py`: planning sketches where `D` acts like a control path.
- `finite_map_compile.py`: tiny finite-map compiler attempts with explicit
  `compile_status`.
- `compare_map.py`: pairwise candidate comparison using the diagnostic Python
  VM.
- `specimens.py`: repo-owned metadata for Codex/Claude xor4096 specimens.

The first executable finite-map compile target reuses the Codex 007 two-input
JUMP/routing specimen for `02:53,06:57`. The three-value map
`02:53,06:57,82:d3` currently produces a planning report unless a seed
candidate is supplied. That is deliberate: the tool should make construction
constraints visible before future match turns try to extend Codex 008's sampled
finite router toward blocks=3.

Phase 3 is still not a full LMAO or Nagoya compiler. It has no general
restore-jump compiler, no complete branch-on-read generator, no real label
layout solver for reusable loops, and no full byte-wide `xor1` solution.

## HeLL-Lite Limitations

- No full label/layout solver yet.
- No restore-jump system yet.
- No true branch-on-read generator yet.
- No full JUMP loop compiler yet.
- No formal LAL/HeLL compatibility.
- No vendored external tooling.
- Current focus is source-valid op generation, cycle analysis, labeled layout
  sketches, tail CRAZY exploration, routing reports, loop sketches, and
  finite-map diagnostics.

## Next Milestones

- Generate an executable two-value finite map.
- Generate a four-value finite map.
- Generate a cat-like input/output loop skeleton.
- Add restore-cell planning that can become source-valid code.
- Try `xor1` diagnostic maps.
- Only then return to a full `xor1` holdout-passing solution.
