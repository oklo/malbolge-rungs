# Survey of the open rungs: a proposed ranking

Date: 2026-08-11

Surveyor: Claude Opus 5 via Claude Code. No rung was attempted. Every load-bearing
number below was re-run on the native evaluator in this clone.

**Input.** Twenty sessions, one per open rung, plus the four records that predate
the survey — 24 attempt records in `docs/attempts/`, their reports, and their
search code under `research/`. Roughly 3.3M tokens of session cap in total.

**Headline.** Nine of the twenty open rungs are solved. The ladder's current
ordering is wrong in both directions and by large amounts: the three `L4`
hash-prefix rungs (31/32/33) are among the four *easiest* things on the board,
and `L2.FM2h.xor51-map12-hi` (15, nominally the easiest open rung) is the only
rung on the board whose wall no session could name.

---

## 0. What was re-verified, and one integrity finding

| claim | source record | re-run here | result |
|---|---|---|---|
| cov34 34/256 | `2026-08-10-claude-cov34` | `verify` | **34/256 PASS** |
| cov36 51/256 | `2026-08-11-claude-cov36` | `verify` | **51/256 PASS** |
| cov40 43/256 | `2026-08-10-claude-cov40` | `verify` | **43/256 PASS** |
| cov48 71/256, passes every coverage rung | `2026-08-10-claude-cov48` | `verify` × 6 rungs | **71/256, PASS on all six** |
| cov64 68/256 | `2026-08-11-claude-cov64` | `verify` | **68/256 PASS** |
| reverse-2 total over 65536 pairs | `2026-08-11-claude-reverse-2-multicase` | `verify --epochs 20` | **60/60 cases PASS** |
| L4.R0/R1/R2 solved at epoch 0, fail beyond | three L4 records | `verify`, `verify --epochs 3` | **PASS at 1 epoch, FAIL at 3** — exactly as claimed |
| xor-1 68/256 | `2026-08-11-claude-xor-1` | 256 × `execute` | **68/256** |
| xor-1-len4096 119/256 | `2026-08-11-claude-xor-1-len4096` | 256 × `execute` | **119/256** |
| xor-2 phase A 66/256 | `2026-08-11-claude-xor-2-multicase` | 256 × `execute` | **66/256** |
| xor-4 phase A 61/256 | `2026-08-11-claude-xor-4-length-cap` | 256 × `execute` | **61/256** |
| mixed-transform phase A 63/256 | `2026-08-11-claude-mixed-transform-small` | 256 × `execute` | **63/256** |
| branchless XOR ceiling = 34, 9 argmax configs | cov32 / cov34 | `research/cov34/argmax.c` | **max 34, exactly 9 configs** |
| straight-line NibbleMap ceiling = 16 | `2026-08-10-claude-future-transform` | `research/future-transform/straightline_ceiling.c` | **16/256 at N=0** |
| map16 table ceiling 15/16, dead lane 0xa7 | `2026-08-10-claude-map16` | `research/map16/trit4.py` | **15/16, dead=[167]** |
| the multi-hop D-funnel exists | `2026-08-11-claude-xor-4-length-cap` | `research/xor-4-length-cap/funnel.py` | **8 fixed points, 94/94 at depth 4** |
| dispatch separation counts | four FM records | `feasibility` × 4 | **map8 39, map12-hi 115, map12-low 0, map16 0** |

Not one claimed number was wrong.

**One integrity finding.** `attempts validate` failed on
`2026-08-10-claude-map12-hi.json`: *"claimed 7/12 but the native VM observes
5/12."* The record is not at fault. The candidate file
`docs/attempts/2026-08-10-claude-map12-hi.best.mal` was **overwritten twice by
later survey sessions** — commit `cf735aa` (the map12-low session) and commit
`b3191ce` (the cov36 session) each replaced it with a different map12-hi-builder
output, presumably a default output path collision. Restoring the file from its
own commit `551053f` reproduces the record's `--verbose` transcript case for
case, including the `invalid runtime instruction at address 109` on lane `0xe0`.

I restored it. `attempts validate` is now 24/24 clean. Any harness that lets a
session write into `docs/attempts/*.best.mal` without a per-rung path guard will
do this again.

---

## 1. Proposed ordering

Rank is a single ordering over the whole ladder, so placing nine newly-solved
rungs renumbers the solved block. Displacement is marked separately from
evidence-driven moves.

| # | rung | was | move |
|---|---|---|---|
| 1 | `L0.R0.hello-world` | 1 | — |
| 2 | `L0.R1.echo-1-demo` | 2 | — |
| 3 | `L1.R0.echo-1` | 3 | — |
| 4 | `L2.R1.reverse-1` | 4 | — |
| 5 | `L1.R1.echo-2` | 5 | — |
| 6 | `L1.R2.echo-4` | 6 | — |
| 7 | `L1.R3.echo-2-multicase` | 7 | — |
| **8** | **`L4.R0.hash-prefix-1`** | 31 | **−23** |
| **9** | **`L3.R0.reverse-2-multicase`** | 28 | **−19** |
| **10** | **`L4.R2.hash-prefix-length-pressure`** | 33 | **−23** |
| 11 | `L2.FM0.xor51-map2` | 8 | displaced |
| **12** | **`L4.R1.hash-prefix-1-multicase`** | 32 | **−20** |
| 13 | `L2.FM1.xor51-map4` | 9 | displaced |
| 14 | `L2.R0c.crazy-mask-1` | 10 | displaced |
| 15 | `L2.FM1b.xor51-map6` | 11 | displaced |
| 16 | `L2.FM1c.xor51-map7a` | 12 | displaced |
| 17 | `L2.FM1d.xor51-map7b` | 13 | displaced |
| 18 | `L2.FM2.xor51-map8` | 14 | displaced |
| 19 | `L2.C0.xor51-cov32` | 16 | displaced |
| 20 | `L2.C0a.xor51-cov34` | 17 | displaced |
| 21 | `L2.C0b.xor51-cov36` | 18 | displaced |
| 22 | `L2.C0c.xor51-cov40` | 19 | displaced |
| 23 | `L2.C0d.xor51-cov48` | 20 | displaced |
| 24 | `L2.C1.xor51-cov64` | 21 | displaced |
| 25 | `L2.FM2l.xor51-map12-low` | 22 | displaced |
| **26** | **`L5.R1.future-hash-prefix`** | 35 | **−9** |
| **27** | **`L2.R0d.xor-1-len4096`** | 25 | +2 (displaced +2, order held) |
| **28** | **`L2.R0.xor-1`** | 26 | +2 (order held) |
| **29** | **`L2.R2.rotate-1`** | 24 | **+5** |
| **30** | **`L2.FM3.xor51-map16`** | 23 | **+7** |
| **31** | **`L2.R3.xor-2-multicase`** | 27 | **+4** |
| **32** | **`L3.R2.mixed-transform-small`** | 30 | **+2** |
| **33** | **`L3.R1.xor-4-length-cap`** | 29 | **+4** |
| 34 | `L5.R0.future-transform` | 34 | — |
| **35** | **`L2.FM2h.xor51-map12-hi`** | 15 | **+20** |

### The evidence for each move

**`L4.R0.hash-prefix-1` 31 → 8.** `HashPrefix` derives the target as
`H(seed, input, index)[0]` and the seed never reaches the program, so — as three
independent records establish from `challenge.rs` — no function of the input
computes it and the only correct program is a table. At one case and one epoch
that table has **one row**: the rung is "emit a constant byte and halt". The
session found it by BFS at **depth 1** (`crazy(0, 47) mod 256 = 0x5e`), and
`coverage.py` shows the constant family covers all 256 possible targets at depth
≤ 11, so solvability is not seed luck. 253 bytes, of which 249 are the NOP
prefix. This is strictly easier than `L2.FM0.xor51-map2` (a two-row map keyed on
the input) and than `L2.R0c.crazy-mask-1` (a total 256-input transform), both of
which currently outrank it by 20+. It belongs immediately above the echo rungs.

**`L4.R2.hash-prefix-length-pressure` 33 → 10** and **`L4.R1.hash-prefix-1-multicase`
32 → 12.** These are the **two-row** and **three-row** instances of the same
table. Both fell on **the first geometry enumerated** (`cfg0`), using
`research/map8/{base,geometry}.py` — the already-solved eight-row rung's builder
— *unchanged*, at 60k and 70k tokens. L4.R2's nominal difficulty lever is inert:
its session shrank the program to **121 bytes against a 256-byte cap** and then
proved 121 is the architectural floor by enumerating all 143808 stage-1 chains,
so the cap has 2.12× slack. The binding resource is not bytes but the
`[34,127]` tail band — 94 addresses, *identical at every program length*. That
correction retracts L4.R1's own prediction that length pressure would bite,
and the code supports L4.R2.

I place R2 below R1 (two rows vs three), and both around `map2`/`map4`.

**`L3.R0.reverse-2-multicase` 28 → 9.** `transform_bytes` reverses the
`output_bytes`-length prefix, so at 2 bytes `Reverse` is a **byte swap** — a
permutation of the input, not a function of its value. No table, no dispatch, no
input-dependent control flow at all: `exhaustive.py` shows the `(C,D)` trace is
bit-identical for every input. The whole rung is one gadget — Malbolge has no
load, and `ROT` is the only instruction that loads `A` from memory without
mixing in the old `A`, so `b0` is parked with two `CRZ`s against a `121`-pair,
pre-rotated nine times, and reloaded with a tenth `ROT` after `OUT b1`. 122
bytes, 71 steps, solved in ~12 minutes. I re-verified 20 epochs: 60/60 cases.
This is the only solve in the survey that is *total* rather than epoch-0. Note
that `L2.R1.reverse-1` already sits at rank 4 because a one-byte reverse **is**
the identity; the step from rank 4 to this rung is exactly the store gadget and
nothing else.

**cov34/36/40/48/64, 17–21 → 20–24.** Pure displacement; the relative order is
kept and the thresholds are the only tiebreak left, because *the block is a
plateau* — see §4. All five are solved and all five are cleared by a single
program (`solutions/cov48/cov48-table-dispatch.mal`, 71/256, re-verified PASS on
all six coverage rungs including cov64).

**`L2.FM2l.xor51-map12-low` 22 → 25.** Displacement, order held. It is the
strongest open rung: 10/12 natively verified, and its own "first thing I would
run with real budget" — NOP-spaced walks, so lanes collide only when an input
difference lies in `O − O` — was **never run there but was implemented on
`map16` the same day**, where it eliminated window overlap exactly, for every
`K ≤ 8`. Window overlap is precisely what `research/map12-low/solve.c` proves
binds (UNSAT in all 83 all-lanes-live configurations). A named lever with
demonstrated effect against the named blocker is as good as evidence of
tractability gets short of a program.

**`L5.R1.future-hash-prefix` 35 → 26.** The largest move downward on an *open*
rung, and it rests on the only self-assessment of its kind in the corpus: *"a
compute wall, not a structural one."* The evidence behind that phrase is
concrete. A 60k-node budget reported zero two-byte tails on every lane in every
sampled geometry — which looked like a wall — and a 4M-node re-run found **five**
two-byte tails on lane `0xa2` at 350k nodes, with the other three lanes
budget-truncated rather than proved empty. Nothing here is an arithmetic ceiling;
it is 10³× more search per lane than an L4 tail, times a 17302-config sweep,
against a Python DFS. Every rung I rank above it has a *proven* bound below its
own threshold. It cannot sit at the bottom of the ladder.

**`L2.R0d.xor-1-len4096` 25 → 27, `L2.R0.xor-1` 26 → 28.** Order held, and the
`len4096`-before-`xor-1` ordering is now *measured* rather than assumed. The
len4096 record closed by asserting that separating the two rungs on length is
"measuring the wrong variable". The xor-1 session measured it: 119/256 with
stride-9 private blocks at 4096 bytes, **68/256** with the forced stride-1 shared
table at 256 bytes. I re-verified both natively, byte-sweeping all 256 inputs.
The cap is worth **51 inputs**, and the board is right to separate them. What
survives from the len4096 record is the part that matters more: neither reaches
256, and both fail for the same arithmetic reason.

**`L2.R2.rotate-1` 24 → 29.** Currently ranked *below* both xor-1 rungs; the
exact DPs say the opposite. `rotate-1`'s table-dispatch optimum is **63/256**
against xor-1's free-layout bound of **77/256**, and rotate-1's number is
computed under *more* freedom than xor-1 ever had — the 256-byte cap forces
`K0 = 0`, which puts the whole table inside the program where every cell is
choosable. `rotl(b,1) = 2b mod 255` is carry-propagating; `crazy` is trit-local.
Same architecture, harder target, and the counting bound is blunt: 255 free cells
× 3 bits = **765 bits of freedom against 2048 bits of constraint**. It belongs
above both xor rungs.

**`L2.FM3.xor51-map16` 23 → 30.** Two architectures, both closed. The dispatch
family: 0 separating configs of 143808 (`feasibility`, re-run). The table
architecture: the **trit-4 forcing law** caps it at **15/16** over all 80
realisable configurations, with `0xa7` the dead lane — I re-ran
`research/map16/trit4.py` and reproduced `best ceiling 15/16, dead=[167]`. A
`FiniteMap` rung needs 16/16. So map16 requires a third architecture nobody has,
where map12-low needs one implemented lever. The gap between them is much larger
than one rank.

**`L2.R3.xor-2-multicase` 27 → 31.** Two independent multipliers over `xor-1`.
The pass probability is the *fourth* power of the per-byte hit rate (two output
bytes × two cases, all four bytes seed-derived and random), so even at the
family's free-layout bound of 77/256 an epoch passes 0.8% of the time. And the
rung needs a second dispatch. Its own session thought that was impossible; the
`xor-4` session proved otherwise (see §5), but at a cost of ~28 pinned table
cells. The record's own ranking note asks for exactly this move.

**`L3.R2.mixed-transform-small` 30 → 32 and `L3.R1.xor-4-length-cap` 29 → 33 —
the one clean inversion.** These two were built within a day of each other with
the same exact DP (`research/xor-1/dpk.c`, one expression changed), the same
`121`-parking gadget and the same ride-chain architecture, which makes the
comparison unusually direct:

| | mixed-transform-small | xor-4-length-cap |
|---|---|---|
| real dispatches needed | 2 | 4 |
| fresh `121` parking pairs needed | 2 | 4 |
| pairs `MOVD`-addressable (≤127) | **2 — exactly enough** | 2 — **half short** |
| program cap | 512 | 256 |
| measured epoch pass probability | **1.7e-9** | 1.2e-14 |

`xor-4`'s recorded blocker is the parking-pair shortage: reaching `(165,166)` or
`(200,201)` costs ~38 and ~35 bytes of `NOP` walk that do not fit in 256
alongside a table spanning 256 consecutive addresses. `mixed-transform` needs
exactly two pairs and exactly two exist, and its transform is the *same function*
for both output bytes so one operand table serves both walks. On every axis the
two records share, `mixed-transform-small` is the easier rung. Swap them.

**`L5.R0.future-transform` 34 → 34.** No move. Four cases × four bytes = **16
exact bytes per epoch** of a value transform on random input, with the
straight-line family exhaustively dead at 16/256 (I re-ran the enumeration: the
optimum *is the identity*), needing four independent 256-entry lookups inside 94
`MOVD`-addressable cells and ~68 instructions of headroom. It is correctly the
hardest rung with a namable obstruction.

**`L2.FM2h.xor51-map12-hi` 15 → 35.** The largest move in the survey, and the
most important. Three sessions — Claude Sonnet 5, GPT-5.4 at xhigh, Claude
Opus 5 — roughly 1M tokens between them, produced no program above 7/12. The
third's screen covered **1611 geometries spanning all 115 separating dispatch
configurations** and lane `0x90 → 0xc1` was dead in every one, with maximum
operand freedom and no competing lanes. Three independent widenings of the tail
grammar (Codex's brute force over `{MOVD,ROT,CRAZY}` bodies to length 5, deeper
CRAZY chains, and a doubled-`ROT` 56-shape catalogue) left the identical dead
set. And unlike every other rung on this ladder, **nobody can say why**: the
reachable-output hole is empirical (`|R| = 209` for low-`J` lanes, 47 bytes
missing) and has no closed form, the screen's own "honest limits" section flags a
memoisation caveat that stops it being a proof, and the second architecture that
works on its sibling rungs was never pointed at it. See §2 and §3.

Why the board ranked it 15: `feasibility` reports 115 separating configs against
map8's 39 and labels it *"hard (separation available, realization is the work)"*
where map12-low and map16 get *"wall"*. That number is silent about whether a
separated lane can then **emit its byte**, and on this rung four cannot. The
label is not just wrong about the difficulty; it actively steered three sessions
into the family that cannot do it.

---

## 2. Classification of every open rung

### Solved this survey (9)

| rung | score | epochs | cost |
|---|---|---|---|
| `L2.C0a.xor51-cov34` | 34/256 (34 required — zero slack) | seed-independent | ~140k tok |
| `L2.C0b.xor51-cov36` | 51/256 | seed-independent | ~90k tok |
| `L2.C0c.xor51-cov40` | 43/256 | seed-independent | ~105k tok |
| `L2.C0d.xor51-cov48` | 71/256 | seed-independent | ~75k tok |
| `L2.C1.xor51-cov64` | 68/256 (132/256 also on disk) | seed-independent | ~95k tok |
| `L3.R0.reverse-2-multicase` | 3/3 | **20 epochs re-verified; 65536/65536 pairs** | ~78k tok |
| `L4.R0.hash-prefix-1` | 1/1 | epoch 0 only | ~80k tok |
| `L4.R1.hash-prefix-1-multicase` | 3/3 | epoch 0 only | ~70k tok |
| `L4.R2.hash-prefix-length-pressure` | 2/2 | epoch 0 only | ~60k tok |

Coverage rungs enumerate all 256 inputs, so one epoch is definitive there and
these five are unconditional. `reverse-2-multicase` is total.

**The three `L4` solves are epoch-0 lookup tables and I verified they fail
`--epochs 3`.** Every one of the three reports says so plainly and unprompted.
`llms.txt` defines correct as `verify` exiting 0, which runs one epoch, so they
are solves under the rules as written — but the rules as written are what makes
these rungs rank 8/10/12 rather than 31/32/33. If the board wants the L4 block to
mean what its rank implies, the fix is a rung-level epoch count, not a tighter
length cap: all three sessions independently identified multi-epoch (or the first
epoch-key collision, ~epoch 20–30 by birthday) as the family's only real knob.

Also on disk and uncredited by any record: `solutions/cov64/cov64-stride-dispatch.mal`,
which I verify at **132/256** — the best coverage figure on the board, from an
earlier survey run at the same rank (commit `7ea30c9`).

### Reachable with more budget (2)

**`L2.FM2l.xor51-map12-low` — one session, ~200k tokens.** Best 10/12 verified.
The exact joint DP is UNSAT in all 83 all-lanes-live configurations, but *only*
for `K ≤ 8` **consecutive** CRAZYs — and the blocker it identifies (four inputs
within a span of six sharing almost all operands) is exactly what NOP-spaced
walks remove. `research/map16/lanes.py` implements the spaced walk and shows it
decomposes the joint table problem into independent per-lane reachability. It has
never been run against map12-low's twelve inputs. Separately, the 11/12 offsets
`K0 = 405/567` are real and blocked only by ~700 cells of `MOVD` padding — a
scheduling problem with a stated target.
*Estimate:* one 200k-token session. The lever is already written; the work is
porting `lanes.py`'s offset construction and re-running an exact DP that runs in
seconds.

**`L5.R1.future-hash-prefix` — one session, 100k cap, ran ~85k and past its wall.**
No arithmetic ceiling was found and none is claimed; three of four lanes were
*budget-truncated* at 4M DFS nodes, and the fourth produced five valid two-byte
tails at 350k. What is needed is all four lanes feasible in one geometry plus a
joint assignment over shared operand cells, at 10³–10⁶ nodes per lane.
*Estimate:* 400–600k tokens **if** the tail solver stays a Python DFS; roughly
one 150k session if the record's own fix lands first — replace the tree walk with
a meet-in-the-middle closure over the 59049-word accumulator space (the same
trick `L4.R0`'s `coverage.py` already uses), which turns each lane's question
into a table lookup.

### Blocked on a structural obstruction I can name (8)

**Seven of these eight share one obstruction.** Naming it once:

> **The operand-magnitude barrier.** Every operand a CRAZY chain can read from a
> *designed* program cell is a loader-valid source byte in `33..126`. Two
> consequences follow, and everything in the transform block dies of them.
> (a) A byte is `< 243 = 3⁵`, so trits 5..9 of every operand are 0 and the
> accumulator's top five trits evolve under `M0 = (1,0,0)` with **no choice at
> all**; `M0` is 2-periodic, so the high word `H` is a function of the input and
> the *parity* of the chain length, nothing else. `OUT` emits `A mod 256`, so the
> required low value `L = (target − 243·H) mod 256` is uniquely determined and the
> input is dead outright when it lands in `243..255`.
> (b) A byte is `< 162 = 2·81`, so operand trit 4 ∈ {0,1}, `M2` is never
> selectable there, and nothing maps *into* trit-state 2 — it can be held, never
> entered.
> Together these cap the reachable accumulator set at ~110 of 59049 words per
> input, independent of chain depth, program length, or search budget.

The barrier's fingerprints, all exact and all measured by different sessions:
68/256 (xor, stride 1, 256-byte cap) · 77/256 (xor, free layout, zero-cost code)
· 119/256 (xor, stride 9, 4096 bytes) · 194/256 (xor, union over all depths with
per-input branching) · 148/256 (xor, fully decoupled coverage table, no sharing
at all) · 63/256 (rotl) · 63/256 (nibble swap) · 16/256 (nibble swap,
straight-line) · 15/16 (map16's trit-4 forcing law is barrier (b) restated for a
finite map).

| rung | additional obstruction | distance to threshold |
|---|---|---|
| `L2.R0d.xor-1-len4096` | — | 119 built, 194 exact union ceiling, needs 256 |
| `L2.R0.xor-1` | `MOVD` cannot reach past address 127, so stride > 1 is unaffordable at 256 bytes | 68 built, 77 free-layout bound, needs 256 |
| `L2.R2.rotate-1` | 765 bits of table freedom vs 2048 bits of constraint; the target is carry-propagating | 63 exact, needs 256; no program built |
| `L2.FM3.xor51-map16` | 0 separating dispatch configs; trit-4 forcing law | 15/16 exact ceiling, needs 16/16 |
| `L2.R3.xor-2-multicase` | pass probability is the 4th power; second dispatch costs ~28 pinned cells | (77/256)⁴ = 0.8% at the family bound |
| `L3.R2.mixed-transform-small` | needs the ceiling broken twice; `K0 ≤ 28 − k − m` is forced by the pointer cell at address 40, so the 512-byte cap is inert | (77/256)⁶ per epoch at the bound |
| `L3.R1.xor-4-length-cap` | 8th power; only 2 of 4 needed `121` parking pairs are `MOVD`-addressable | (77/256)⁸ ≈ 7e-5 at the bound |
| `L5.R0.future-transform` | four 256-entry tables in 94 addressable cells, ~68 instructions of headroom | 16/256 straight-line; needs 16 exact bytes/epoch |

**The barrier has exactly one named escape, and nobody ran it.** `ROT` at `D`
does `m[D] = rotr(m[D]); A = m[D]`, promoting a controllable low trit to trit 9
in one instruction — the only operator that moves information *between* trit
positions and therefore the only thing that can put a runtime-written word, which
can exceed 242, into the walk. **Nine of the twenty records name it as the next
measurement** (cov64, rotate-1, map16, xor-1-len4096, xor-1, xor-2-multicase,
xor-4-length-cap, mixed-transform-small, reverse-2-multicase), five of them call
it "the only thing" that can move their rung, every one of them describes it as a
59049-state BFS that is "trivial in C" — and **not one of the twenty ran it.**
That is the single highest-leverage fact in this survey: one cheap, well-specified
measurement gates eight rungs, and the survey's structure (one session per rung,
each ending inside its own build) is exactly what prevented anyone from doing it.

### Blocked on something no session could characterise (1)

**`L2.FM2h.xor51-map12-hi`.** Three sessions, ~1M tokens, best 7/12.

What *is* known is sharp and bounded: the tail-placement window `[34,127]` is
fixed by the byte encoding, not by search; the free tail width `W` varies by only
13 cells across all 115 configs (47–60); low-`J` lanes can emit 209 of 256 bytes
and four of this rung's targets sit in the missing 47; `0xe0` has an empty
reachable set in some geometries, a pure placement failure distinct from the
other three.

What is **not** known is the thing that decides the rung:

1. **Why 47 bytes are unreachable.** The hole is empirical. The record's own
   item 2 asks for it "in closed form as a function of `J(x)` and the trail
   alphabets", and says doing so "would upgrade this 1611-geometry negative into
   a proof or produce a counterexample." Nobody has it. Contrast every rung in
   the previous section, where the obstruction is five lines of trit arithmetic.
2. **The negative is not a proof.** `screen.py` memoises on
   `(op index, accumulator, data pointer)` and drops the partial cell assignment
   from the key, so a `MOVD` re-reading an assigned cell can in principle suppress
   a branch. The session says so itself.
3. **The second architecture was never tried.** Every map12-hi attempt lives in
   the two-stage CRAZY-dispatch family. The *data-dispatch table* architecture —
   the one that produced 10/12 on map12-low and an exact ceiling on map16 — has
   never been aimed at this input set, because `feasibility` says separation is
   available here and so every session stayed in the dispatch family. map12-low's
   record makes the converse point explicitly ("a rung that walls the dispatch
   family says nothing about this one"); the mirror-image check was never made.

That third point is the survey's largest coverage gap, and it is cheap to close.
`research/map16/trit4.py` computes the table architecture's exact ceiling for a
given input set in under a minute; map12-hi's twelve inputs are pairwise distinct
mod 243, so map16's `K0 ≡ 0 (mod 243)` result transfers directly. It does **not**
transfer by inspection, because map12-hi's lanes span all three trit-4 classes
(six at 2, five at 1, one at 0) where the forcing law's behaviour differs — which
is exactly why it has to be run rather than reasoned about. Until it is,
map12-hi's wall is unmapped, and that is why it ranks last.

### Ran out of ideas vs ran out of budget

Separating these, because the brief is right that they are different signals:

- **Out of ideas, family provably closed:** `cov34` ("Nothing on this rung — 34
  is exhaustive over the branchless family and this program attains it"). The
  only record in the corpus with nothing queued. It is also a *solve*.
- **Out of budget, with a named lever that later evidence supports:**
  `map12-low` (NOP-spaced walks — demonstrated on map16 the same day),
  `map16` (~20 lines of builder fix between 0 verified and ~12/16),
  `cov64` (the 148/256 table is emitted and unbuilt), `future-hash-prefix` (MITM
  tail solver), `xor-4` and `mixed-transform` (build the funnel dispatch).
  These six are the tractable ones.
- **Out of budget having hit a proven ceiling:** `xor-1`, `xor-1-len4096`,
  `xor-2`, `rotate-1`, `future-transform`. Their "next" items are all the same
  ROT measurement.
- **Neither:** `map12-hi`. It did not run out of budget (it spent its last
  tranche on its own best lever, the doubled-`ROT` catalogue, and reported the
  failure) and it did not run out of ideas (it names the three-hop pointer
  chain). It ran out of *characterisation*.

---

## 3. Smoothing rungs worth minting

The cov34 model: a rung whose threshold is a **measured ceiling of a family**,
minted so that the ceiling gets realised in the machine rather than jumped over.
Five candidates, in the order I would mint them.

### 3.1 `L2.FM2j.xor51-map8-hi` — 8 lanes, inputs `a5 84 a1 bd c8 be 86 dd`

**Threshold:** 8/8. `FiniteMap`/`XorMask`, cap 2048.
**Increment isolated:** *joint packing of eight high-range lanes inside a 47–60
cell free tail window*, with the uncharacterised reachability hole removed.

map12-hi's screen names four lanes (`0xe0, 0x90, 0x9c, 0xf9`) as structurally
dead across the family and concludes: *"Given four lanes are provably out in this
geometry, 8/12 is the ceiling for the two-stage family here, and 7/12 is one short
of it."* This rung is that ceiling, minted. It follows the map7a/map7b precedent
exactly (map8 minus `0xc0`, map8 minus `0xa7`) and it does the one thing the
current ladder cannot: it separates map12-hi's *packing* difficulty, which is
ordinary and measurable, from its *reachability* difficulty, which nobody can
name. If a session clears map8-hi and still cannot clear map12-hi, that is a
clean, attributable result; today the two failures are entangled.

### 3.2 `L2.C1a.xor51-cov148` — coverage threshold 148

**Threshold:** 148/256. `CoverageTransform`/`XorMask`, cap 4096.
**Increment isolated:** *realising the fully-decoupled strided table under the
2048-step budget.*

`research/cov64/gstride.c` measures the strided walk exactly. At stride 256 no
two inputs share a cell — decoupling is total — and the exact count at
`K0 = 1458, k = 5` is **148/256**. The table is emitted and checked in
(`research/cov64/table-1458-s256-k5.txt`) and was not built for one stated
reason: the chain is `(k−1)s + 1 = 1025` instructions, every one a step, against
a 2048-step limit that a ~900-step prefix has mostly spent. Best actually built:
132/256.

This is cov34's shape. The mathematics is settled and published; the rung asks
for the construction, and the increment it isolates — step-budget-constrained
layout, i.e. the `MOVD`-padding problem that cov40, cov36 and cov64 all name as
the binding constraint and none of them solved — is a genuine one that no current
rung charges for. Caveat worth stating in the `purpose` field: 148 is the maximum
over the swept `K0 × s × k` box, not a proven family optimum, so it is slightly
weaker evidence than cov34's exhaustive 34. Mint at **136** instead if the board
wants slack; 136 still beats the built 132 and still requires the `s = 256`
decoupling.

### 3.3 `L2.C1b.xor51-cov160` — coverage threshold 160

**Threshold:** 160/256. `CoverageTransform`/`XorMask`, cap 4096.
**Increment isolated:** *the operand-magnitude barrier itself.*

Past 148, decoupling is exhausted — at stride 256 there is no sharing left and
**108 inputs are still unreachable**, with more depth making it worse (110 at
k = 6). The cov64 record states the consequence: *"Decoupling is not the binding
constraint on this architecture. Reachability is."* So a threshold above 148
cannot be met by any chain of CRAZYs against loader-supplied bytes; it forces a
runtime-written operand, which means `ROT` inside the walk or an equivalent.

This is the highest-value rung on the list, because it converts the board's
single most important unanswered question — the one nine records name and none
answered — into a **graded, partial-credit rung** where progress is measurable in
single cases rather than all-or-nothing. It is the coverage family's whole reason
for existing, applied to the wall that actually matters.

### 3.4 `L4.R3.hash-prefix-6` — HashPrefix, 6 cases, 1024-byte cap

**Threshold:** 6/6. `HashPrefix`/`Identity`, cap 1024.
**Increment isolated:** *lane count against the 94-address tail band.*

L4.R2 established that the binding resource in this family is not program length
but the `[34,127]` tail band — 94 addresses, identical at 256 bytes and at 1024 —
divided by tail size. L4.R1 measured the other side: of the stage-1 configs
fitting a 1024-byte program, **20590 separate 3 lanes and 3937 separate 6**. So 6
is measurably harder than 3, still feasible, and sits where the band starts to
bite rather than where the dispatch funnel does. Both records predict the family
dies around 10–15 lanes; 6 is the honest midpoint and the first `L4` rung whose
difficulty comes from a measured resource instead of the family's flavour.

This is the fix for the L4 block. `hash-prefix-length-pressure` is a *bad*
smoothing rung by the brief's own test — its nominal lever (a 256-byte cap
against a 121-byte floor) isolates nothing, and its session proved so by
producing a fresh verified program at every cap down to 121.

### 3.5 `L3.R0b.reverse-4-multicase` — Reverse, 4 output bytes, 3 cases

**Threshold:** 3/3. `Transform`/`Reverse`, `output_bytes` 4, cap 512.
**Increment isolated:** *contention for the sub-128 `D`-navigation cells when
several bytes are parked at once.*

`reverse-2` is one gadget above echo and its rank should say so — but the gadget
has a stated cost bound that nothing on the board currently charges for: four
data cells per `D`-reset path, all forced below address 128 by the `MOVD` reach
bound, plus three instructions per rotation. Reversing four bytes needs three
bytes parked across two intervening outputs with three distinct rotation counts,
and the record identifies that as "where this family would become genuinely hard,
and it would be a better L3 than this rung is." One increment, one named binding
resource, no new architecture. Cheap to mint and cheap to attempt.

### What the survey says about the *existing* smoothing rungs

- **cov34 was a good mint** and is vindicated: the +2 over cov32 turned out to
  require an operand with a **zero trit**, which cov32's entire manufacturing
  family (`rot^k(crazy(0, byte))`, all ten trits in {1,2}) cannot express, plus a
  high constant of 81 — odd — which forces a trit-2 at a high position that no
  byte operand supplies. Two independent reasons the obvious extension fails. A
  rung that looked cosmetic was a real construction problem.
- **cov40 and cov48 are bad smoothing rungs**, by the brief's own definition.
  They are arithmetic steps: one program clears cov36, cov40, cov48 and cov64,
  and the cov48 session was the **cheapest of the five** (75k tokens) while
  producing the **highest score** (71/256). The increment between them is worth
  two instructions of table depth.
- **`xor-1-len4096` is a good calibration rung** and its own session was wrong to
  doubt it: the 256 → 4096 relaxation is worth 51 inputs, measured. But
  `mixed-transform-small`'s 512-byte cap is inert — `K0 ≤ 28 − k − m` is forced by
  a pointer cell at address 40, not by `max_program_len`. If the board wants
  length to be a lever, the step has to cross ~2302 cells, where stride-9 private
  blocks become affordable. Nothing between 256 and 2302 is a difficulty variable.

---

## 4. Cliffs — where the ladder lies about its own gradient

**Cliff 1 — `map8` (18) → `map12-hi` (35). Four ranks apart; ~1M tokens and three
models apart.** The board's own difficulty estimator points the wrong way here:
`feasibility` gives map12-hi **115** separating configs against map8's 39 and
labels it *"hard (separation available, realization is the work)"* against map8's
*"frontier"*. Separation feasibility measures whether inputs land on distinct
addresses; it is silent about whether a landed lane can then emit its byte. On
map12-hi four cannot. This is the ladder's largest single misstatement, and it is
worse than a bad rank because the label actively steered every session into the
family that provably cannot solve it.

**Cliff 2 — `cov34` (20) → `cov36` (21), and the plateau behind it.** The
branchless CRAZY/ROTATE family's ceiling is exactly 34 — exhaustive, re-verified.
Getting past it requires input-dependent branching, which the cov34 record
correctly called a wall and then over-generalised: *"ranks 18–21 are one problem,
not four."* The first half is right. The second half is falsified twice over.
cov40 found that the branch costs **four instructions** (`crazy(crazy(b,O1),O2) = b
+ K0` with all-`M1` low trits parks the input as a data pointer; one `MOVD` on the
written cell makes the input the table index), and cov48 then cleared **every**
coverage rung with one program by running the same DP two layers deeper. So:
cov34 → cov36 is a real cliff, but a *narrower* one than the ladder implies, and
cov36 → cov40 → cov48 → cov64 is a **flat** — four rungs charging for what is
worth two instructions. The ladder says four steps; the evidence says one step
and a plateau.

**Cliff 3 — the coverage plateau (24) → the transform block (27+). A pass/no-pass
discontinuity that the ladder renders as three ranks.** `cov48` scores 71/256 with
twelve instructions and passes. `xor-1` scores 68/256 — the same architecture,
essentially the same number — and is 188 cases short, because a coverage rung asks
for a *fraction of a table* and a transform rung asks for a *function*. rotate-1
states the counting reason: the table holds 765 bits of freedom against 2048 bits
of constraint, and no arrangement of program bytes changes that. Partial credit is
not a difficulty knob across this boundary; it is a different question.

**Cliff 4 — the `L4` block is a false cliff, top to bottom.** Ranks 31/32/33, above
every finite map and above the xor frontier, for the 1-row, 3-row and 2-row
instances of a table whose 8-row instance has been solved since 2026-08-07. All
three fell in one session each, at 60–80k tokens, with `research/map8/`'s builder
**unchanged**, two of them on the *first geometry enumerated*. The ladder is
pricing SHA-256's reputation. (The rungs are not worthless — they are just worth
what a 2-row map is worth, and the family's real knob, multi-epoch, is not
expressed in the registry at all.)

**Cliff 5 — `reverse-2-multicase` (28) is a false cliff in the same way, from the
opposite direction.** `Reverse` at one output byte **is** `Identity` — which is
why `reverse-1` sits at rank 4 — and at two bytes it is a byte swap needing no
table, no dispatch and no input-dependent control flow. The ladder reads "L3,
three cases, Reverse" as harder than "L2, one case, XorMask"; the machine reads it
as one gadget above echo. The rule the record extracts is worth putting in the
registry docs: read `challenge.rs::transform_bytes` and ask whether the transform
is a **permutation of the input bytes** (`Identity`, `Reverse` — cheap, no table,
straight-line at any case count) or a **function of their values** (`XorMask`,
`RotateLeft`, `NibbleMap`, `CrazyMask` — hits the 77/256 wall). Case count is
nearly irrelevant next to that distinction.

**Cliff 6 — `future-hash-prefix` (35) sits nine ranks below where its evidence puts
it.** It is the only open rung any session called a compute wall rather than a
structural one, and it currently ranks below eight rungs with proven arithmetic
ceilings under their own thresholds. The ladder's `L5` tier is a statement about
intent, not measured difficulty, and this is where the two diverge most.

---

## 5. Where two sessions disagree, and what the code says

1. **Is the coverage ladder one problem above 34?** `cov34` said ranks 18–21 "are
   one problem, not four". `cov40` and `cov48` falsified it. **The code supports
   cov40/cov48** — I re-verified 43/256 and 71/256 natively, and the cov48 program
   PASSes all six coverage rungs.

2. **Can `D` be reset after a dispatch?** `xor-2-multicase` proved the one-hop
   funnel impossible (each landing cell serves 8 of 94 source residues, so ≥ 12
   landings are needed, but a fixed value is legal at exactly 8 addresses in any
   94-address window: 8 < 12) and framed it as the wall for the whole multicase
   family. `xor-4-length-cap` showed the framing was one hop too shallow: every
   `MOVD` lands in `34..127`, exactly one residue system mod 94, so the hop map is
   a function on ℤ/94 and the question is whether it *iterates* to a constant. It
   does. **The code supports `xor-4`** — I re-ran `funnel.py`: 8 fixed points,
   each covering 94/94 of the window at depth 4, no source address without a legal
   hop in. Cost: ~28 pinned cells, about 12% of a 256-byte table.

3. **Does the multicase family inherit that wall?** `xor-2` predicted
   `reverse-2-multicase` and `hash-prefix-1-multicase` would. Both refuted it, for
   two different reasons: `Reverse` never pollutes `D` because it needs no table
   at all, and `HashPrefix` runs each case as a **separate execution**, so there
   is only ever one dispatch per run. **The code supports both refutations** —
   `reverse-2` passes 20 epochs and all 65536 pairs; `hash-prefix-1-multicase`
   passes 3/3 with a single dispatch.

4. **Is the 256 vs 4096 length split "measuring the wrong variable"?**
   `xor-1-len4096` said yes. `xor-1` measured 68 vs 119. **The code supports
   `xor-1`** — I re-swept all 256 inputs on both programs and reproduced both
   numbers exactly. But `mixed-transform-small` then showed 256 → 512 is worth
   nothing, because `K0` is capped by a pointer cell at address 40. Both are
   right, at different scales: length is inert until it crosses ~2302 cells.

5. **Would length pressure bite the HashPrefix construction?** `hash-prefix-1-multicase`
   predicted yes. `hash-prefix-length-pressure` measured a 121-byte architectural
   floor against a 256-byte cap by enumerating all 143808 stage-1 chains, and named
   the real resource (the 94-address tail band). **The code supports L4.R2.**

6. **Is `xor-4-length-cap` a budget problem?** Its own record says *"as of this
   record it is a cell-budget rung, not an impossibility rung… a well-funded agent
   should take it."* `mixed-transform-small`, one day later, says nothing solves it
   until the 77/256 ceiling breaks. **The code supports `mixed-transform`**: the
   rung needs 8 exact bytes of a value transform on seed-derived input, so even at
   the family's free-layout bound the epoch pass rate is (77/256)⁸ ≈ 7e-5. The
   funnel is real progress on the *architecture* and does not move the *rung*.
   `xor-4`'s claim is true of its score and false of its solvability.

7. **`map12-hi`, 7/12 or 5/12?** Neither session is wrong; the artifact was
   clobbered in-tree by two later sessions. Restored and re-verified at 7/12,
   reproducing the record's transcript case for case. See §0.

---

## 6. The one thing I would do next

Run the `ROT`-in-the-walk reachability BFS. Nine records name it, five call it the
only lever that can move their rung, all describe it as ~59049 states and trivial,
and none ran it. It gates `xor-1`, `xor-1-len4096`, `xor-2-multicase`,
`xor-4-length-cap`, `mixed-transform-small`, `rotate-1`, `map16` and
`future-transform` — eight of the twenty rungs surveyed — and it is a
measurement, not a build, so it is cheap to get wrong safely.

Second: run `research/map16/trit4.py` against map12-hi's twelve inputs. One
minute of compute decides whether the board's most-attempted rung is a mapped wall
or an unmapped one, which is the difference this report cares about most.

---

## Reproduce

```sh
cargo build --release
./target/release/malbolge-rungs attempts validate                    # 24/24 after the §0 restore

# coverage cross-matrix (six rungs × six programs)
for r in L2.C0.xor51-cov32 L2.C0a.xor51-cov34 L2.C0b.xor51-cov36 \
         L2.C0c.xor51-cov40 L2.C0d.xor51-cov48 L2.C1.xor51-cov64; do
  ./target/release/malbolge-rungs verify --rung $r \
      --program solutions/cov48/cov48-table-dispatch.mal
done

# the three L4 solves are epoch-0 tables
for r in L4.R0.hash-prefix-1 L4.R1.hash-prefix-1-multicase L4.R2.hash-prefix-length-pressure; do
  ./target/release/malbolge-rungs verify --rung $r --program <its candidate> --epochs 3   # FAIL
done
./target/release/malbolge-rungs verify --rung L3.R0.reverse-2-multicase \
    --program research/reverse-2-multicase/cand-rev2.mal --epochs 20      # PASS

# structural ceilings, independently re-derived
cc -O2 -o /tmp/argmax research/cov34/argmax.c && /tmp/argmax          # 34, 9 configs
cc -O2 -o /tmp/slc research/future-transform/straightline_ceiling.c && /tmp/slc   # 16/256
python3 research/map16/trit4.py                                      # 15/16, dead=[167]
python3 research/xor-4-length-cap/funnel.py                          # 8 fixed points, 94/94

# the restore
git show 551053f:docs/attempts/2026-08-10-claude-map12-hi.best.mal \
  > docs/attempts/2026-08-10-claude-map12-hi.best.mal
```

## Honest limits of this survey

- I attempted no rung and built no program. Every construction claim here is a
  session's, re-verified where it was verifiable and labelled as a model result
  where it was not (`map16`'s 12/16 and `rotate-1`'s 63/256 have no native
  program behind them; both sessions say so).
- Rank is an ordering, not a metric. The gaps between adjacent proposed ranks are
  wildly unequal — §4 is the part of this report that carries that information,
  and it should be read as more load-bearing than the table in §1.
- The map12-hi classification is the one I am least sure of and the one I most
  want overturned. It is "unmapped" because of a gap in coverage, not because the
  rung resisted characterisation on its merits; one script settles it.
- Budget estimates in §2 are extrapolations from what the sessions spent and what
  their named next levers cost, not measurements.
