# Claude attempt: `L5.R1.future-hash-prefix`

Date: 2026-08-11

Outcome: **unsolved** — 0/4 cases. One candidate authored and natively verified
(a 4-byte echo, 0/4, present only so the record ships a real program). The
construction that solved L4.R0/R1/R2 was ported to this rung's shape and the
run ended inside its search, not against a proof.

Solver: Claude (Opus 5) via Claude Code, autonomous single session under a hard
cap of 100k tokens / 20 minutes. The cap is the point: this run was asked
whether rank 35 is a wall or a budget problem.

Candidate: [`research/future-hash-prefix/cand-echo2.mal`](../../research/future-hash-prefix/cand-echo2.mal) (4 bytes, `ubaN`).
Search: [`research/future-hash-prefix/search_fhp.py`](../../research/future-hash-prefix/search_fhp.py).
Diagnostics: [`research/future-hash-prefix/diag_lanes.py`](../../research/future-hash-prefix/diag_lanes.py),
[`research/future-hash-prefix/diag_deep.py`](../../research/future-hash-prefix/diag_deep.py).

Builds on [`docs/attempts/2026-08-11-claude-hash-prefix-length-pressure.json`](2026-08-11-claude-hash-prefix-length-pressure.json)
(and through it the map8 two-stage dispatch, `research/map8/{base,geometry}.py`).

## What the rung actually asks

The registry entry is a placeholder ("Reserved for a future frontier hash-prefix
rung after empirical calibration"), so the shape has to be read out of
`crates/harness/src/challenge.rs`:

- family `HashPrefix`, so each case's input is the 32-byte hash
  `H("malbolge-coin:mal51:v0:input", (seed, index))` and the expected output is
  `H("malbolge-coin:mal51:v0:hash-prefix", (seed, input, index))[:2]`. The
  `transform: Identity` field is inert on this family.
- `output_bytes = 2`, `cases = 4`, `max_program_len = 2048`,
  `max_steps_per_case = 2_000_000`, `max_output_len = 2`.

The seed never reaches the program, so as on L4.R0/R1/R2 no function of the
input computes the output. The only correct program is a lookup table, and at
the default single epoch (epoch 0) it is this one:

| key (first input byte) | output |
|---|---|
| `ce` | `c9 31` |
| `46` | `86 91` |
| `a2` | `5f 84` |
| `f5` | `96 1d` |

Four distinct first bytes, so one `IN` is the whole key. Relative to the solved
L4 rungs this is **4 lanes instead of 1–2, and two output bytes instead of one**,
with a 2048-byte length limit that is not binding.

## What was built

`search_fhp.py` reuses the map8 two-stage dispatch unchanged — stage-1 crz
dispatch lands lane *x* at `J(x)+1`, a per-cluster `[MOVD,JUMP]` station
redirects it to a private tail — and replaces only the tail solver. An L4 tail is

    NOP*k SHAPE OUT HALT

and this rung needs

    NOP*k SHAPE1 OUT SHAPE2 OUT HALT

`OUT` prints `a % 256` without touching `a`, and `c`/`d` advance like any other
instruction, so the second stage continues on the same accumulator over the next
operand cells. Both stages therefore share one d-trail and compete for the same
free cells.

The first implementation enumerated `SHAPE1 × SHAPE2` (28 × 28 shapes × 9 NOP
prefixes ≈ 7000 op sequences per landing, each re-solving its operands): **18 s
per dispatch config**, hopeless against 17302 configs. It was replaced by a
unified DFS that walks the tail cell by cell, choosing op and operand together
and sharing every prefix — strictly more shapes, one traversal. That is the one
new construction primitive this attempt contributes.

## Where it stopped, and the two numbers that matter

**1. The landing floor is 80, so landings and tails fight for the same
addresses.** L4.R2 established that a tail entry `L = T + 1` is pinned to
`[34,127]`, because the stage-2 pointer `p` and the jump target `T` are both
source-valid bytes. Over all 90735 crz configs that give four *distinct*
landings for these four keys, the **maximum landing floor is 80** (histogram
peak at 16). So the dispatch band always starts inside the tail band: cells
81…station+1 are fixed NOP/station cells, and the four private tails must fit in
roughly `34…41` plus `51…80` — about 38 free cells for four tails that are now
twice as long as an L4 tail. Sweeping `jmin = 130` returns **zero configs**.

**2. The second `OUT` is expensive, but it is not impossible.**
`diag_lanes.py` counts tail plans per lane with the first byte only (the L4
shape) versus both bytes, on the first geometries in the sweep:

    cfg0 J=[80,101,134,263] m=[107,162,292]  1byte=[1,1,0,50]   2byte=[0,0,0,0]
    cfg1 J=[80,128,134,290] m=[82,137,300]   1byte=[0,24,0,50]  2byte=[0,0,0,0]
    cfg2 J=[80,101,134,263] m=[107,162,292]  1byte=[24,1,0,50]  2byte=[0,0,0,0]

Every lane, every geometry: zero two-byte tails under a 60k-node budget, while
one-byte tails show up immediately. That looked like a wall. `diag_deep.py`
re-ran one geometry with a 4M-node budget and depth 18 and it is not:

    lane 0xa2 -> (95,132)   2byte plans=5   nodes=349704   1.4s
    lane 0x46 -> (134,145)  2byte plans=0   nodes=4000131  80.7s  (budget, not exhaustion)
    lane 0xce -> (201,49)   2byte plans=0   nodes=4000302  64.6s  (budget, not exhaustion)
    lane 0xf5 -> (150,29)   2byte plans=0   nodes=4000319  49.3s  (budget, not exhaustion)

So two-byte tails exist — one lane produced five of them — at a cost of ~3×10^5
to >4×10^6 DFS nodes each, against ~10^3 for an L4 one-byte tail. Three of the
four lanes were budget-truncated, not proved empty. A solve needs all four lanes
feasible *in the same geometry* and then a joint assignment that survives the
shared operand cells: three or four orders of magnitude more Python DFS than the
L4 solves needed, on top of a 17302-config sweep.

## Verdict: a compute wall, not a structural one

Nothing found here says the rung is unsolvable, and the honest reading is that
it is a budget problem — but a large one, and of a different kind than the
earlier hash-prefix rungs. L4.R2 solved on the *first* geometry enumerated. Here
the per-lane tail search is ~10^3× more expensive, the landing floor caps at 80
so the tail band is contended, and the joint constraint over four lanes is
untested because no geometry cleared the per-lane gate inside the cap.

The candidate shipped is a 4-byte `IN OUT OUT HALT` that echoes the first input
byte twice (`ce → cece`, 0/4). It is not a partial solution; it is there so the
record carries a program that loads and halts on the native VM.

## Notes for the next agent

The rung is `Draft` status. If it is minted as-is, the L4 family carries over,
but the tail solver needs to be an order of magnitude faster than a Python DFS —
the natural move is to precompute, per lane, the set of accumulator words
reachable from `J(x)` whose residue is the first target byte, and *from those*
the words whose residue is the second, rather than searching op sequences. That
is a meet-in-the-middle over ~59049 words, not a tree walk, and it turns the
per-lane question into a table lookup. Also: multi-epoch verification remains
the real difficulty knob for this whole family, and this rung as written does not
touch it.
