# Claude attempt: `L2.R0d.xor-1-len4096` (joint tape optimisation)

Date: 2026-08-11

Outcome: **unsolved**. Best candidate is correct on **249 of the 256**
possible input bytes, verified natively on all 256. Prior art on this rung ran
119 → 229; this run takes it to 249 and, more usefully, **retracts the
structural claim that has framed this rung twice**.

Solver: Claude (Opus 5) via Claude Code, autonomous single-session run under a
hard cap of 900k tokens / 150 minutes.

Builds on [`2026-08-11-claude-push-xor-1-len4096.json`](2026-08-11-claude-push-xor-1-len4096.json)
(the 229/256 private-code-block architecture, which this run reuses unchanged)
and [`2026-08-11-claude-xor-1-len4096.json`](2026-08-11-claude-xor-1-len4096.json)
(the 119/256 private-data-block ceiling proof, whose `would_try_next` set the
direction both runs took).

Artifacts: [`research/xor-1-len4096-hero1/`](../../research/xor-1-len4096-hero1/) —
`hero.c` (simulator + exact per-input DFS + optimiser), `structure.py` (the
finite checks below), `prologue2.py` (the prologue-phase search),
`native_check.sh` (all-256 native measurement), `cand.mal` (the candidate),
`uncovered.txt`, run logs.

## The headline: b = 0, 1, 2, 3 are not walls

Both prior records on this rung treat the four lowest inputs as structurally
impossible, because the dispatch JMP sends input `b` to `c = 9b` and resumes at
`9b+1`, which for `b ≤ 3` is address 1, 10, 19 or 28 — inside the prologue,
already executed and therefore enciphered. The 229 record puts it plainly:
"**`b = 0,1,2,3` — provably unreachable in this architecture.**"

That is wrong, and the reason is one line of the VM:

```rust
// crates/classic_malbolge/src/lib.rs, step()
let fetched = self.memory[self.c];
if !is_printable_word(fetched) { return Err(InvalidRuntimeInstruction { .. }); }
let code = instruction_code(fetched, self.c);
match code { 4 => .., 5 => .., .., 81 => return Ok(Halt), _ => {} }   // <-- _ => {}
```

The runtime error is on a **non-printable word**, not on a non-instruction code.
`XLAT2` maps `33..126` onto `33..126`, so an enciphered cell is always still
printable and always still executes — and 92.5% of the time it decodes outside
the eight codes and is a **runtime NOP**. `structure.py` measures it: of the
2400 (address, first-pass code) pairs over addresses 0..299, only 179 re-decode
to one of the eight codes.

So an executed prologue is a **NOP sled**. And the dispatch JMP is never
enciphered — the canonical cycle sets `c = m[d]` *first* and then enciphers
`m[c]`, so the jump **target** (cell `9b`) is enciphered and the JMP's own cell
keeps its byte. An input that lands in the prologue therefore slides forward to
that JMP and executes it a second time, now with `d = 73 + (32 − entry)`, and
lands on `m[d] + 1`. That is a **second, per-input dispatch through a cell we
choose**:

| input | resumes at | real instructions in the sled | re-dispatches through |
|---|---|---|---|
| b=0 | 1  | `1: IN`  (fatal) | m[104] |
| b=1 | 10 | none — clean sled | m[95] |
| b=2 | 19 | none — clean sled | m[86] |
| b=3 | 28 | none — clean sled | m[77] |

**The shipped candidate solves b = 2 by exactly this route.** It is not a
special case and it is not luck; it is a live dispatch path that the previous
search never modelled, and it is why the ceiling on this architecture is not
252/256.

Only `b = 0` is blocked by the prologue itself, and only because address 1 must
hold the first MOVD, whose enciphered form at address 1 is `IN` — and `IN` reads
the **second** byte of the 32-byte case input, which is seed-derived.
`prologue2.py` searches the fix: a MOVD executes with `d == c` before any other
MOVD has run, so it reads its own byte and lands on `byte_for(MOVD, a) + 1`;
putting a NOP at address 1 starts the d-chain at 39 instead of 40, and the
shortest route from 39 to the forced CRAZY pair `(71,72)` is `39 → 43 → 92 → 71`,
one hop longer. That layout does give b = 0 a clean sled — but shifting every
later instruction by one puts `ROT` at address 10, which enciphers into `HLT`,
killing b = 0 and b = 1 instead (dispatch reach 251/256 versus 253/256 for prior
art's phase). **The four low inputs are a prologue-phase search problem.** I
found the tool, quantified the trade, and did not solve it.

## What was actually binding: the joint tape, not per-input freedom

The 229 record already identified coupling as the constraint and reported it as
"a joint constraint-satisfaction problem over ~90 shared cells that I did not
get to." This run got to it. Three things had to be right.

**1. The model has to match the VM exactly.** `hero.c` computes the
post-prologue state in closed form (addresses 0..31 enciphered; `m[71] =
crazy(b,121)`; `m[72] = 9b`; `A = 9b`; `c = 9b+1`, `d = 73`) and simulates from
there over the full 59049-cell memory. Two details cost real coverage and are
invisible until the native VM disagrees:

* the dispatch JMP enciphers `m[9b]` — the **last cell of block b−1** — before
  block `b` runs, so that cell's value differs between its owner's run and its
  neighbour's;
* memory must be the full 59049 cells, not the program. Prior art's own 229
  program uses the crazy-filled tail: input 17's block reads `m[19713]`.

With both in, the model reproduces prior art's candidate at **229/256 and the
identical 27-byte miss set**, and reproduced this run's candidates at 238 and
249 before any native check was run. Every number below is a native
measurement (`native_check.sh`, all 256 bytes through `execute`).

**2. The shared surface is small and includes the tail.** Every block starts
with `d = 73`, and MOVD can never point `d` below 34 (it reads a byte ≥ 33), so
the operand cells the whole population competes for are roughly `34..135` — the
blocks of `b = 4..14` — plus whatever a block reaches by running past its own
nine cells. Everything above ~163 is private to its owner. The one shared
surface prior art did not use: the crazy-filled region past the program end is a
function of the **last two program bytes**, so those are design variables. At
`N = 2305` they belong to b=255's block; the optimiser treats them as such and
re-scores globally when they move (getting this wrong is a silent scoring drift,
which cost this run one bad intermediate result before it was found).

**3. Search has to be joint, exact, and incremental.**

| stage | what it does |
|---|---|
| exact block-local DFS | full search over the 8^9 assignments of a block's own cells, pruned on crash / `OUT` when `A mod 256 ≠ target` / `IN` (banned) / step cap; enumerates up to 256 witnesses per input rather than the first |
| incremental scoring | each input records the addresses its trace touches; changing a cell re-simulates only the inputs that can be affected, which is exact — an input whose trace never reads a changed cell cannot change |
| annealing | repair an unsolved input / reroll a solved one to a different witness / jitter a shared cell then repair, with Metropolis acceptance |
| coordinate sweep | for every shared cell and all 8 codes, apply, repair, keep the best — directed, and worth more per second than the annealing |
| assembly pass | exhaustive block-local search per input at a higher step cap, applied whenever it costs nothing globally |

The sweep and the assembly pass are where the gains came from. Raising the DFS
step cap from 14 to 16 alone unlocked inputs the annealer could not see: an
assembly pass at cap 16 took a 238 program to 240 by itself.

Trajectory, every number a native all-256 measurement: prior art **229** →
annealing **238** → coordinate sweep + assembly **241** → annealing **244** →
assembly at step cap 26 / span 16 **248** → sweep + assembly **249**.

The step cap is worth calling out on its own. Prior art searched blocks as
straight-line nine-instruction programs; this run let a block run on past its
own nine cells into whatever its neighbours left there, and raising the DFS
step cap 14 → 16 → 18 → 26 was worth +2, +2 and +2 respectively on an otherwise
finished program, in seconds of compute each. The last +4 of this run is
entirely "look further ahead", not "search harder".

## The remaining misses

    b = 0, 1, 3, 8, 9, 151, 255        (7 of 256)

`b = 0, 1, 3` are the sled / prologue-phase problem above — `b = 2`, the fourth
of that group, is solved. `b = 8, 9` own blocks at 73..81 and 82..90, which is
the hottest part of the shared tape: cell 73 is a forced data cell and those
cells are the operands the other 240 inputs read first, so their own code is the
most constrained on the board. `b = 151, 255` are tape-limited: an
exhaustive block-local DFS run to completion (not node-capped) finds no
assignment of their own cells that works against the shipped tape, so they need
a different shared tape rather than a better search over their own cells — and
every tape change that helps one of them breaks something else.

## Budget and what I would do next

Spent: roughly 550k tokens and 130 minutes of the 900k / 150-minute cap, about
70% of it on search compute (14 cores, ~2.5 core-hours). Neither the program
length cap (2305 of 4096 bytes) nor the step cap (≤ 60 of 2048) binds.

**Is this a wall or a budget problem? Both, in different places, and that is the
useful answer.**

* The four tape-limited misses (`8, 9, 151, 255`) are a **budget/search problem**. Coverage was
  still moving when the clock ran out (241 → 249 in the last 25 minutes, still improving when the clock ran out),
  the objective decomposes almost perfectly once the shared tape is fixed, and
  the right next step is obvious and was not run: **anneal the shared tape
  directly** with the objective "number of inputs with an exhaustive block-local
  solution" rather than annealing the assembled program. That evaluation is 256
  independent DFS calls and it removes the assembly conflicts from the search
  landscape entirely. I would also run the sweep over the full `34..163` window
  at step cap 18 and let the assembly pass close it, and sweep the last two
  program bytes exhaustively (64 tail families) instead of jittering them.
* `b = 0, 1, 3` are a **different, small, exact problem**: enumerate prologue
  phases (NOP padding positions × d-chain routes × the two CRAZY-pair sites
  (71,72) and (106,107) × the two rotation-cycle pointers) and keep the ones
  whose enciphered image contains **no real instruction** at any of the four
  sled entries; then tune `m[104]`, `m[95]`, `m[86]`, `m[77]` — four cells — so
  each of the four re-dispatches lands somewhere useful. `prologue2.py` already
  does the chain search and prints the sled; what it does not do is enumerate
  phases. This is hours of compute at most, not a research question, and it is
  the single highest-value thing left on this rung.

If both land, 256/256 is reachable in this architecture. I no longer believe
this rung is capped below a solve, and I would rank it easier than its current
position rather than harder.

## Two warnings for the next agent

**`verify` is a sampling event on this rung.** One case is drawn per epoch from
the seed, `min_epochs` is 5, so a program correct on `n`/256 passes the default
run with probability `(n/256)^5`. At 249/256 that is about 87%.
The 229 record is a live example: it returns `RESULT: PASS`, exit code 0, and is
not a solve. The only honest measurement is all 256 bytes through `execute` —
that is what `native_check.sh` does and what every number here is.

**Do not inherit "provably unreachable" without re-deriving it.** The claim that
cost this rung two records was one `match` arm in the VM.
