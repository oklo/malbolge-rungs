# Claude attempt: `L2.R0d.xor-1-len4096` (code dispatch)

Date: 2026-08-11

Outcome: **unsolved**. Best candidate is correct on **229 of the 256** possible
input bytes, verified natively on all 256. The contribution is that the ceiling
in the previous record on this rung is **architecture-specific, not a property of
the rung**: prior art proved the private-*data*-block family cannot exceed
**194/256 at any chain depth**, and this run clears that by changing **one byte**
of prior art's prologue.

Solver: Claude (Opus 5) via Claude Code, autonomous single-session run under a
hard cap of 800k tokens / 120 minutes.

Builds on [`2026-08-11-claude-xor-1-len4096.json`](2026-08-11-claude-xor-1-len4096.json),
whose `would_try_next` names exactly one escape — "put a ROT inside the walk" —
and on [`2026-08-11-claude-cov64.json`](2026-08-11-claude-cov64.json), which
first predicted it. This run takes that escape by a different route than the one
proposed there, and it works.

Artifacts: [`research/xor-1-len4096-push/`](../../research/xor-1-len4096-push/) —
`mal.py` (simulator, cross-checked byte-for-byte against the native VM),
`build.py` (the dispatch skeleton), `search.c` (exhaustive per-input search),
`solve2.c` (three-phase assembler), `cand.mal` (2305 bytes, 229/256 native),
`uncovered.txt`, `solve5.log`.

## Read this first: `verify` returns PASS on this program and it is NOT a solve

    $ ./target/release/malbolge-rungs verify --rung L2.R0d.xor-1-len4096 \
          --program research/xor-1-len4096-push/cand.mal
    RESULT: PASS (native evaluator)        # exit status 0

    $ ... --epochs 40
    RESULT: FAIL (native evaluator)

The rung's `min_epochs` is 5 and one case is drawn per epoch, so a program
correct on 229/256 inputs passes the default verification with probability
`(229/256)^5 = 0.573`. **This run is a live example of the trap the previous
record warned about, this time with a green result and a zero exit code.** On any
Transform-family rung the only honest measurement is all 256 bytes through
`execute`; that is what the 229 below is.

## What changed: dispatch on C instead of D

Prior art's 43-byte program was the only surviving description of its own
prologue (`build.py`/`gen.py` are no longer in the clone), so I recovered it by
tracing. It is worth writing down, because everything here is built on it:

| step | what happens |
|---|---|
| `c=0` | `IN` — `A = b` |
| `c=1..3` | `MOVD` ×3 walks `D` along the chain `1 → 40 → 123 → 71` (`m[40]=122`, `m[123]=70`) |
| `c=4,5` | `CRZ` at 71 then 72, both operand cells holding **121** |
| `c=6..31` | eight rotations, each a **3-instruction cycle** `MOVD@73 → D=62`, `MOVD@62 → D=72`, `ROT@72` (`m[73]=61`, `m[62]=71`) — the cycle is self-sustaining because `ROT` leaves `D=73` again |
| `c=32` | `MOVD` at 72 → `D = 9b+1`, the private data block |

Two facts make it work. **121 is the unique operand that makes CRAZY
injective**: `crazy` is trit-local with `M0=(0→1,1→0,2→0)`, `M1=(0→1,1→0,2→2)`,
`M2=(0→2,1→2,2→1)`, and of the nine compositions `M[w']∘M[w]` the only bijection
is `M1∘M1 = id`. So a double CRAZY reproduces `b` exactly iff both operands have
trits 0..4 all equal to 1, i.e. both are 121 — which is loader-legal only at
addresses `≡ {12,13,35,41,54,71,72,90} (mod 94)`, and 71,72 is the only adjacent
pair below 127. **Eight rotations are `×9`**: `rotr^8 = rotl^2`, and `9b` has
trits 8,9 clear so nothing wraps.

The change is one byte. Address 32 becomes `JMP` (byte 66) instead of `MOVD`, so
`c = m[72] = 9b` and input `b` starts **executing** at `9b+1`. The private block
stops being nine data operands and becomes **nine bytes of private code**: at any
address each of the eight legal instructions is available as exactly one byte, so
every input picks its own straight-line program, ROT and MOVD included.

    0..32        prologue (byte 32 = JMP)
    40,62,71,72,73,123   prologue data cells
    9b+1..9b+9   input b's private code block
    N = 2305 bytes

`build.py` confirms the mechanism in isolation: with every block set to
`[OUT, HALT]`, **253 of 256 inputs** emit `9b`.

## Why this beats the 194 ceiling

Both barriers in the previous record come from operands being program bytes
(`< 243 = 3^5`, so trits 5..9 get `M0` with no choice, and `< 162`, so trit 4 can
never enter state 2). A private code block sidesteps both, because `ROT` at `D`
does `m[D] = rotr(m[D]); A = m[D]` — one instruction moves a low trit to
position 9 — and `MOVD` can revisit a cell that a previous `CRAZY` already wrote, whose
value is a full 10-trit word rather than a byte. Prior art's own re-entry gadget
is available for free inside a block: `m[72]` still holds `9b`, so
`MOVD@73 → D=62`, `MOVD@62 → D=72` and then `MOVD` or `ROT` at 72 costs three of
the nine instructions.

`search.c` measures the result exactly: a full DFS over the `8^9` assignments per
input, pruned on crash / leaving the block / output limit, with two soundness
rules that both cost coverage and both had to be added after the native VM
disagreed with the model —

* a cell the run has **written** (CRAZY/ROT) and then **executes** is fetched as
  the written value, so it is no longer a free choice;
* **`IN` is banned inside a block.** `crates/harness/src/challenge.rs` derives
  the case input as a full `Hash32`, so the program is fed **32 bytes** and a
  second `IN` returns a byte that changes every epoch. Allowing it scores 236/256
  natively on single-byte `execute` input and is worthless under `verify`.
  This one distinction is worth 7 inputs and is invisible unless you read the
  harness or run `verify --verbose`.

Against an all-NOP tape, **234/256 inputs can individually reach their target**;
the mean number of distinct output bytes a block can produce is 124 and the max
is 250.

## What actually binds: coupling, not per-input freedom

A block's operands are read from `m[73]`, `m[74]`, … as `D` walks forward — and
those cells *are other inputs' block bytes*. Only **57 of 256** inputs have an
**independent** solution (one that reads nothing but the prologue, the six forced
data cells, and its own nine cells). Everything above 57 is inputs reading each
other's code.

So the assembler (`solve2.c`) is three phases, each verified by full simulation:

| phase | rule | native |
|---|---|---|
| 1 | independent solutions only | 57 |
| 2 | foreign reads allowed, greedy, **roll back any regression** | +171 → 228 |
| 3 | a block may borrow a neighbour's spare cells (span 18) | +8 → 229 |

A naive iterate-to-fixed-point without rollback oscillates (223 → 227 → 219) and
stalls below this; greedy locking of 18-cell spans from the start is much worse
(145), because every block steals the cells its neighbours need.

**229/256 verified natively, 2305 of 4096 bytes, ≤ 55 of 2048 steps.**

## The 27 misses, and which of them are walls

* **`b = 0,1,2,3` — provably unreachable in this architecture.** Their block base
  `9b+1` lands inside the 33-byte prologue, whose cells have already executed and
  been enciphered. The prologue cannot be shortened: the double-121 CRAZY is
  forced (above), eight rotations at three instructions each are forced, and it
  cannot be *looped* either — a self-modifying loop needs a cell whose byte keeps
  its instruction across encipherment, i.e. a fixed point of `XLAT2`, and
  **`XLAT2` has none**; its only short orbit is the 2-cycle `70 ↔ 74`, whose two
  codes differ by 4, and no two of the eight legal codes differ by 4 (mod 94).
  Nor can the prologue be moved out of the way: a `JMP` off a program byte lands
  at `≤ 127`, so the prologue must live in `0..127`, which is always somebody's
  block.
* **`b = 8,9,12,13,16`** — blocks overlapping the forced data cells. Cell 71
  holds `crazy(b,121) ≈ 29434` at dispatch time, which is not printable, so any
  input whose block must execute cell 71 dies with `InvalidRuntimeInstruction`.
* **`b = 145..152` (a run of 8) and `203,204,225,229,233,235,242,252,253,255`** —
  not walls. These have 233–250 of 256 output bytes reachable and simply miss the
  one target they need, given the tape their neighbours left them. This is a
  joint constraint-satisfaction problem over ~90 shared cells that I did not get
  to.

## The length cap, revisited

The previous record concluded that `max_program_len` "is not the binding
variable" and that ranking this rung apart from `L2.R0.xor-1` measures the wrong
thing. On this evidence that is right for 4096 but **wrong in the limit**, and
the crossover is now locatable. The clean fix for the coupling above is to give
each input a private *data* block as well as private code, which means widening
the dispatch stride from `×9` to `×27` (seven rotations instead of eight):
9 bytes of code plus 18 private operand cells, no shared tape at all, and no
`InvalidRuntimeInstruction` collisions. That needs `27·255 + 27 = 6912` cells —
**past 4096, and the first thing in this rung's history for which the length cap
is the binding constraint.** So the two rungs are not equivalent, but the
threshold that separates them is ≈ 6.9k, not 4k.
