# HeLL-Lite Research Notes

Status: internal construction notes. This is not a consensus specification.

## Sources Inspected

- Esolang Malbolge programming:
  `https://esolangs.org/wiki/Malbolge_programming`
- Lou Scheffer Malbolge programming notes:
  `https://www.lscheffer.com/malbolge.shtml`
- Lou Scheffer Malbolge specification:
  `https://www.lscheffer.com/malbolge_spec.html`
- Lutter Malbolge assembler page:
  `https://lutter.cc/malbolge/assembler.html`
- Lutter cat tutorial:
  `https://lutter.cc/malbolge/tutorial/cat.html`
- zb3 malbolge-tools:
  `https://github.com/zb3/malbolge-tools`
- zb3 malbolge-tools README:
  `https://raw.githubusercontent.com/zb3/malbolge-tools/master/README.md`
- Hacker News discussion of MalbolgeLisp:
  `https://news.ycombinator.com/item?id=38850961`

No external source code is vendored into this repository.

## Takeaways

Raw Malbolge byte-string search is the wrong abstraction for loops and real
input-dependent transforms. It can find fixed-output coincidences, but it does
not naturally build data-pointer discipline, restore jumps, or reusable
instruction cells.

Nagoya/LAL/HeLL/LMAO-style work treats Malbolge as a memory-layout and
instruction-cycle problem. Useful programs need:

- code/data placement
- instruction cycles
- restore jumps
- `D` pointer management
- source-valid initialization
- explicit awareness of what gets enciphered after JUMP

Lutter's cat tutorial is especially relevant because it shows the conceptual
workflow:

1. Write as if memory can be laid out deliberately.
2. Use labels and instruction cycles.
3. Handle references as target-minus-one because C and D increment after the
   instruction.
4. Restore self-modified instruction cells when reuse is needed.
5. Only then translate into raw Malbolge source.

zb3-style branch-on-read and fixed-length generators are relevant for MAL-51
finite byte-function targets. The fixed-length idea matters because default
memory after the source depends on source suffixes. The branch-on-read idea
matters because a finite byte relation such as `input ^ 0x51` can be attacked
as a small input-conditioned output problem.

MalbolgeLisp is important prior art, but it targets Malbolge Unshackled and is
not directly admissible for classic MAL-51 rungs.

## HeLL-Lite Scope

HeLL-Lite should not be a full HeLL/LMAO clone. It should provide practical
construction and diagnostic tools for MAL-51 agents:

- first-use source-valid op generation
- instruction-cycle inspection
- simple JSON sketches
- deterministic labeled layout sketches
- finite-map target definitions
- routing-search report scaffolds
- planning-only loop/JUMP sketches
- source-tail CRAZY exploration
- finite-map diagnostic scoring

Official success still requires MAL-51 runner or sweep reports from the Rust
CLI.

Normal HeLL-Lite diagnostics are bounded by default. `analyze-tail-crazy`
reports `candidates_tested` and `truncated`; when a run is truncated, its best
candidate is only the best found in that bounded scan. Exhaustive tail analysis
is deliberate heavy work and requires explicit large-search flags.

## Phase 2 Direction

Phase 2 starts the move from raw strings toward small layout descriptions. It
adds labels, sections, code/data cells, finite-map targets, bounded routing
reports, and loop-planning reports. The compiler remains intentionally narrow:
it can compile only a single linear CODE section such as `IN,OUT,HALT -> ubO`.

This is still internal lab tooling. It is not a consensus component, not an
official evaluator, and not a public protocol requirement. It may eventually be
split away from a public protocol/verifier repository. Trust for public MAL-51
results should come from the verifier, VM, registry, task hashes, report
hashes, candidate artifacts, and transcript checks.

## Nagoya/L-Ass Construction Target

Nagoya-style Malbolge programming works with operation units rather than raw
byte strings. A useful unit is a placed piece of code/data whose first-use
instruction and later self-encrypted visits are predictable enough to compose
with neighboring units. Many practical units rely on simple cycle behavior,
including period-two patterns where a useful instruction alternates with a NOP
or with another harmless/useful operation.

`D` can be treated as a program-counter-like control path. A higher-level
construction can say "after INPUT, make D select the route cell; after the
route, make C jump to the selected output arm." The Malbolge work is then to
place target-minus-one data cells, source-valid operands, and restore/fixup
cells so those abstract transitions survive self-encryption.

Nagoya/LAL/L-Ass/HeLL-style assemblers compile higher-level operations such as
`INPUT`, `OUTPUT`, `MOV`, `BRANCH`, `INC`, `DEC`, and `STOP` into carefully
placed classic Malbolge units. HeLL/LMAO follows the same broad lineage with
labels, `.CODE`/`.DATA` sections, references, instruction cycles, and restore
jumps.

HeLL-Lite Phase 3 is only a tiny internal version of that idea. It adds
operation-unit metadata, cycle-to-unit-cell search, D-as-PC sketches, specimen
metadata, and finite-map compiler attempts that explicitly report
`compile_status`. It does not reproduce Nagoya's full compiler, LMAO, or a
general restore-jump system. The immediate MAL-51-specific target is to turn
the Codex 008 finite trampoline/collision-splitter progress into deliberate
layout construction for larger sampled maps.

## Phase 4 Finite-Map Allocator Target

Phase 4 adds the first read-only bridge from raw match artifacts into
construction tooling:

- `match_extract.py` extracts file-backed finite-map pairs from Codex 012
  notes, diagnostics, and reports, preserving full input hex when available.
- `branch_alloc.py` scores a seed candidate against extracted preservation
  pairs and one requested add-target, then emits a bounded planning report with
  collision, poisoned-lane, cycle-cell, and D-as-PC metadata.
- `trace_compare.py` gives compact Python-VM diagnostic traces for explicit
  inputs.

The current focused target is the Codex 012 routed candidate. It preserves the
visible byte, the five Codex 008 one-block holdout cases, several blocks=3
first-block lanes, and the fresh Codex 012 `02 bc ... -> 53` lane. The next
file-backed target is:

```text
f0 5d ... -> expected a1, got dd
```

The derived follow-up target is:

```text
2d ca ... -> 7c
```

This is still not a compiler. The allocator may honestly return
`planning_only`; that result should be read as a constraint report, not as a
match claim. A useful next compiler step would synthesize source-valid landing
pads while preserving known successes under full official input vectors.

## Phase 5 Trace-Guided Branch Repair

Phase 5 makes the next surgical step explicit:

- `route_surgeon.py` runs bounded Python diagnostic traces for selected
  preserve and failure pairs, then reports common prefixes, first divergence,
  shared C/D lanes, JUMP/MOVD targets, suspected collision cells, patchable
  source-valid cells, and dangerous shared cells.
- `patch_enum.py` consumes the route report and searches bounded one-byte and
  two-byte local edits. It uses only source-valid bytes at each address and
  treats extracted successes as hard constraints unless explicitly told
  otherwise.
- `repair-branch` orchestrates route surgery and patch enumeration into a
  single branch repair report.

This remains local repair tooling, not a compiler. The patch enumerator has a
small diagnostic scoring budget inside the user-supplied candidate cap so demo
runs stay fast. It may preserve the seed baseline and still report
`planning_only` if no local edit adds the target. That is a precise blocker:
the next step is then a restore/fixup-aware landing-pad split or broader
D-as-PC layout allocation, not another blind local byte sweep.

For the current Codex 012 frontier, `extract-match-map` puts the file-backed
`f05d... -> a1` failure first so `--target-index 0` selects the intended next
blocks=3 lane. The follow-up lane remains `2dca... -> 7c`.

## Why Source-Tail CRAZY Matters

Codex turn 005 on `L2.R0d.xor-1-len4096` showed that the relaxed program length
can matter as legal source-tail data after `HALT`.

The useful template is:

```text
MOVD, IN, NOP..., CRAZY^k, OUT, HALT
```

After `MOVD` at address 0, a `CRAZY` at source address `p` reads from
`D = p + 40`. If the source is long enough, cells `p + 40`, `p + 41`, and so on
can be valid but unexecuted source bytes after `HALT`. They are not arbitrary
words, but they can serve as planted CRAZY operands.

The Codex 005 diagnostic candidate is:

```text
(tBA@?>=<;:9210TA3210/.-,+*)('&%$#"!~}|{zyxwvutsrqpo{PO
```

Its planted operands are:

```text
[123, 80, 79]
```

This is not a rung solution. It is a useful construction specimen.

Claude turn 006 pushed the same family further:

```text
(tBA@?>=<;:9876543210/.-,+*)('&%$#"!~}vut:'wvutsrqponmlkjihgfedcba`_^]\[ZYXWVUsrp
```

Its planted operands are:

```text
[115, 114, 112]
```

Claude reported and HeLL-Lite reproduced an `11/256` all-byte xor diagnostic
score for this 81-byte candidate. It still fails the visible task:
`0x82 -> 0xdb`, expected `0xd3`. Holdout was not run because visible failed.

For the currently tested fixed source-tail CRAZY family over valid source-tail
bytes, the observed best scores are:

- `k = 1`: `10/256`
- `k = 2`: `9/256`
- `k = 3`: `11/256`

No candidate in that analyzed `k <= 3` family hits the visible input. Claude
also reported negative searches for deeper fixed CRAZY chains and
MOVD-redirect recurrence operands. This is evidence that this source-tail
family is bounded in current diagnostics, not evidence that classic Malbolge
cannot solve xor1.

## Next Work

- Use the Phase 2 layout layer to generate and score `echo1`.
- Generate a two-value finite-map diagnostic router.
- Expand that into a four-value finite-map diagnostic router.
- Add cycle-aware code placement.
- Add restore-jump sketches.
- Add small branch-on-read finite-map generation.
- Use Phase 3 operation units and D-as-PC sketches to make the Codex 008
  trampoline allocator deliberate instead of greedy.
- Use Phase 4 extraction and branch-allocation reports to protect Codex 012's
  known finite map while targeting `f05d... -> a1`.
- Use HeLL/LMAO-style JUMP and restore-cell construction instead of further
  polishing fixed source-tail CRAZY chains.
- Build two-value and four-value diagnostic rungs before retrying full xor1.
