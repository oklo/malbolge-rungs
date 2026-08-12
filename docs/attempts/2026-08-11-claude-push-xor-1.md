# Claude attempt: `L2.R0.xor-1` (stride-1 code dispatch)

Date: 2026-08-11

Outcome: **unsolved**. The shipped candidate is correct on **48 of the 256**
possible input bytes, verified natively one `execute` per byte. The contribution
is not the score — it is a negative structural result with an exact number
attached: **stride-1 *code* dispatch exists on this rung, it makes 232 of 256
inputs individually solvable, and it is nevertheless unassemblable**, because the
dispatching `JMP` resets `D` to the same value for every input and so hands all
256 inputs one shared operand stream.

Solver: Claude (Opus 5) via Claude Code, autonomous single-session run under a
hard cap of 600k tokens / 90 minutes.

Builds on [`2026-08-11-claude-xor-1.json`](2026-08-11-claude-xor-1.json) (the
68/256 record on this rung, whose program is the seed for the search here) and on
[`2026-08-11-claude-push-xor-1-len4096.json`](2026-08-11-claude-push-xor-1-len4096.json)
(the sibling rung, where changing dispatch from `MOVD` to `JMP` moved 119 → 229).

Artifacts: [`research/xor-1-push/`](../../research/xor-1-push/) — `mal.py`
(model VM, copied from the sibling rung's record), `build.py` (the stride-1
`JMP` skeleton and its dispatch check), `jsearch.c` (exact per-input DFS,
greedy assembler, and simulated annealing over the whole tape),
`native_scan.sh`, `cand.mal`, `covered_native.txt`.

## The one thing to take away

The previous record on this rung established that the 256-byte cap forces
**stride 1**, and then treated the private cells at `b+1` as an *operand table*.
That is not forced. `MOVD` at cell 72 can be replaced by `JMP` at cell 72:

    0        IN            A = b
    1,2,3    MOVD x3       D: 1 -> 40 -> 123 -> 71
    4,5      CRZ x2        operands m[71] = m[72] = 121, so m[72] = b exactly
    6,7      MOVD x2       D: 73 -> 62 -> 72
    8        JMP           c = m[72] = b

`build.py` confirms the mechanism: **253 of 256** inputs land at `c = b+1` with
`A = b`. The previous record's own rule — "`MOVD` cannot reach past address 127,
because every program cell holds a byte in `33..126`" — does not block this, and
it is worth being precise about why: cell 72 is *not* holding a program byte at
that moment. The double-`CRZ` park has overwritten it with `b`, an
input-dependent word in `0..255`. Dispatch past 127 is available to `JMP` for
exactly the same reason it was already available to `MOVD` in the 68/256 program.

So input `b` gets **private code** at `b+1`, not private data — the same change
that took the sibling rung from 119 to 229.

The three inputs that do not dispatch are structural: `b = 70` and `b = 71` both
have to execute cell 71, which holds `crazy(b,121) ≈ 29403 + f(b)` and is not a
printable instruction; `b = 255` lands its first instruction at address 256, in
the crazy fill.

## What it buys, exactly: 232/256

`jsearch.c ind` runs a full DFS per input over the loader-legal byte of every
cell the run touches, with **iterative deepening on footprint** — the first
solution a DFS stumbles on is not the one you want, because the joint phase is
paid for in shared cells, so the search returns the solution that pins the fewest.
Against a tape with every cell free:

    individually reachable: 232/256
      minimum footprint  3 cells:  2 inputs      8 cells: 36
                         4 cells: 12             9 cells: 23
                         5 cells: 23            10 cells:  6
                         6 cells: 53            11 cells:  4
                         7 cells: 70            12 cells:  3

232 against a shipped 68 says the arithmetic is not the barrier. This is the same
shape of result as the sibling rung (234 individually reachable, 229 assembled) —
and it is where the two rungs part company.

## Why it does not assemble, and this is the result

At stride 9 the private blocks are 9 cells apart, so input `b`'s operands are
read from cells near its own block: the coupling is *local*, between neighbours,
and a greedy assembler with rollback recovers 229 of 234.

At stride 1 with `JMP` dispatch the coupling is *global*, and in a specific way
that no assembler can route around. The `JMP` happens at `D = 72`, so **every
input enters with `D = 73`**. Input `b` at step `i` executes cell `b+1+i` and
reads operand cell `73+i`. The code cell depends on `b`; the operand cell does
not. All 256 inputs read the *same* operand stream `m[73], m[74], m[75], …` in
the same order at the same step index. There is no per-input operand at all,
which is precisely the resource the 68/256 program did have.

`D = 73` is forced, not a layout choice:

> The `JMP` must read a cell holding `b`, i.e. cell 72, so `D = 72` at the jump
> and `D = 73` at entry. The park must be a double `CRZ` against two adjacent
> cells both holding `121` (`M1 ∘ M1` is the only identity among the nine
> `crazy` trit-map compositions), and the loader-legal addresses for the byte
> 121 are `≡ {12,13,35,41,54,71,72,90} (mod 94)`. Only `(12,13)`, `(71,72)`,
> `(106,107)` and `(165,166)` are adjacent pairs. Returning `D` to the second
> cell of the pair after the park needs a cell `x` with `m[x] = park-1`, and
> `m[x]` is a program byte `≥ 33`, so `D` can only be re-seated in `34..127`.
> That kills `(12,13)` (unreachable from below), `(106,107)` and `(165,166)`
> (out of range). `(71,72)` is the only pair, so entry `D = 73` for every input.

Measured consequence, over two search methods:

| architecture | individually reachable | best assembled |
|---|---|---|
| `MOVD` data dispatch, fixed shape (prior record, exact DP) | — | **68** |
| `JMP` code dispatch, stride 1 (`ARCH 0` here) | 232 | 48–53 |
| `MOVD` dispatch + free cell 9 (`ARCH 2` here, superset of the 68 family) | 232 | **68** (no gain over the seed) |

`ARCH 2` deserves a note because it is the honest test. Cell 8 stays `MOVD`
(`D = b+1`, a *private* table, exactly as in the 68/256 program) and cell 9 is
left **free**. Choosing `NOP` there reproduces the previous record's straight-line
shape byte for byte; choosing `JMP` there sends input `b` to `m[b+1]`, one of the
eight loader-legal bytes at that address and therefore one of eight addresses in
`34..127`, as a shared code tail — while `D` keeps walking the private table
`b+2, b+3, …`. That is the previous record's own next-step #2 ("a `JMP` off a
table cell into one of eight tails"), with `ROT` allowed in the tail, and it
strictly contains the 68/256 family. Seeding the annealer with that program
reproduces 68 exactly, which is the cross-check that the superset claim is real.

## Method, and what it is worth

`jsearch.c` carries three things:

1. an exact per-input DFS with iterative deepening on footprint, over the eight
   loader-legal bytes of every touched cell, modelling encipherment of executed
   cells, write-then-read of `CRZ`/`ROT` targets, the crazy fill above the
   program, and the ban on a second `IN` (the harness feeds a 32-byte `Hash32`,
   so a second `IN` reads an epoch-varying byte — the sibling rung's record found
   this the hard way and it is worth 7 inputs there);
2. a greedy assembler with rollback, the method that reached 229 on the sibling
   rung. Here it reaches **32**;
3. simulated annealing over all ~241 free cells with a partial-credit objective
   (`1000·solved + 8·[halts with one output] + bit agreement`), on an incremental
   simulator that logs and rolls back writes instead of re-imaging memory —
   about 65k tape evaluations per second, several million moves per run, six
   seeds in parallel.

Two independent methods landing at 48 and 53 for `ARCH 0`, against an individual
bound of 232, is the evidence for the claim above. It is not a proof of a
ceiling; the exact DP that would prove one is described below and I did not have
the clock for it.

## Cross-checks

The model VM and the native VM agree on the shipped program byte for byte
(`native_scan.sh`, 256 `execute` calls). The model also reproduces the previous
record's 68/256 program at exactly 68, which is the calibration that the model is
not flattering itself.

**One epoch is not definitive on this rung.** `min_epochs` is 5 and
`crates/harness/src/challenge.rs` redraws the single case from the epoch seed, so
a program correct on `n` of 256 inputs passes with probability `(n/256)^5`. The
sibling rung's record is a live example of `verify` printing PASS and exiting 0
on a program that is not a solve. The number in this record is 256 `execute`
calls, not a `verify` result.

## The candidate, and the plain statement about it

`research/xor-1-push/cand.mal` is 256 bytes, `ARCH 0`, **48/256 native**, ≤ 46 of
2048 steps. It does **not** beat the 68/256 already recorded on this rung, and I
am not claiming it does. It is shipped because it is the program that
demonstrates the mechanism this record is about — stride-1 code dispatch, 253/256
inputs executing their own code — and because a record whose only artifact is
someone else's program is not an attempt.

The `ARCH 2` runs are the reason the 68 is not beaten by search either. Six
annealing runs (three seeded from the 68/256 program at `T0 ∈ {3.5, 6, 12}`,
three from random tapes), several million moves each, plus DFS repair passes
between rounds: every seeded run finished at exactly 68 and every random run
below 55. The 68/256 program is the exact DP optimum of its family and it is
also, on this evidence, a deep local optimum of the superset.

## Budget, and what I would do with more

Spent: roughly 260k of 600k tokens and 85 of 90 minutes. Two things were on the
list and did not get built, and the first is the one that matters.

1. **The exact transfer-matrix DP over the *code* tape.** The previous record
   built this DP for data cells; the same machine works for code, and it would
   turn "48–53 by two search methods" into a proved ceiling. Formulation, so the
   next agent does not have to rederive it: fix the operand window
   `m[73 … 73+W-1]` as an outer parameter (`m[73] = 61` is pinned by the prologue,
   so `W-1` free cells, `8^(W-1)` combinations, scored cheaply first by the
   per-input independent bound and only the top few taken further). Then DP over
   the code cells low-to-high with state = the last `W-1` decided cells,
   `8^(W-1)` states; when cell `a` is decided, input `b = a-W` has its whole
   window and is scored exactly. At `W = 6` that is 33k states × 8 × ~180
   addresses, seconds per operand combination. That yields the exact ceiling of
   the stride-1 `JMP`-code family — which is what this rung's rank should be set
   from, because 232-individually-reachable and 48-assembled are 184 apart and
   only the DP says which end of that range is the truth.
2. **The unturned stone the previous record named and I also did not turn:**
   sweep the program length `L` from 256 down to about 180. Cells at addresses
   `≥ L` are crazy fill, freely exceed 242, and are exactly the large operands
   that both trit-magnitude barriers are made of. Under stride-1 code dispatch
   this cuts both ways — shortening the tape also shortens the code available to
   high inputs — and that trade is one loop and has never been measured. My
   sweep held `L = 256` throughout, as did the previous one.

## For the ranking

The board has `L2.R0d.xor-1-len4096` at rank 28 and `L2.R0.xor-1` at 29, and this
run supports that ordering and sharpens the reason. The two rungs are the same
transform and the same `crazy` arithmetic; the length cap decides one thing only,
and it is not the byte budget. It decides **whether `D` can be re-seated
per input**. At 4096 bytes, stride 9 gives every input its own block and the
dispatching `JMP` leaves `D` pointing near that block, so operands are
neighbour-coupled and a greedy assembler recovers 229 of 234. At 256 bytes,
stride is forced to 1, the `JMP` must fire at cell 72, and `D = 73` for all 256
inputs — one operand stream, no private data anywhere. Same transform, same
individual reachability (232 vs 234), and an assembled gap of 48 against 229.

That is a stronger separation than "the cap is worth ~51 inputs", which is what
the previous record on this rung concluded from the private-data family. On the
code-dispatch family the cap is worth about 180.
