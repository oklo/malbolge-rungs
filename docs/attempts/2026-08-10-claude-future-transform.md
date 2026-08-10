# Claude attempt: `L5.R0.future-transform`

Date: 2026-08-10

Outcome: **unsolved** — 0/4 cases. Two candidates authored and natively
verified; the whole straight-line family ruled out exhaustively.

Solver: Claude (Opus 5) via Claude Code, run as a calibration probe under a hard
cap of 100k tokens / 20 minutes. The cap is the point: the question this run was
asked was whether rank 34 is a wall or a budget problem.

Candidates:
[`research/future-transform/cand-4stage-crazy.mal`](../../research/future-transform/cand-4stage-crazy.mal)
(688 bytes) and
[`research/future-transform/cand-identity.mal`](../../research/future-transform/cand-identity.mal)
(9 bytes).
Builder: [`research/future-transform/build.py`](../../research/future-transform/build.py).
Ceiling: [`research/future-transform/straightline_ceiling.c`](../../research/future-transform/straightline_ceiling.c),
output in [`ceiling-output.txt`](../../research/future-transform/ceiling-output.txt).

Builds on [`docs/attempts/2026-08-10-claude-cov32.json`](2026-08-10-claude-cov32.json),
whose family enumeration, operand invariant, and NOP-prefix pointer table are
reused directly.

## What the rung actually asks

The registry entry is terse ("Reserved for a future calibrated transform rung"),
so the first job was to read the derivation out of the harness rather than the
title. From `crates/harness/src/challenge.rs`:

- family `Transform`, so each case's input is a 32-byte hash of
  `(seed, index)` — **not** a fixed byte list. The seed is
  `hash("malbolge-rungs:v0:challenge-seed", (rung_id, epoch))`, so the inputs
  move with the epoch.
- transform `NibbleMap`: `out = ((b << 4) | (b >> 4)) & 0xFF`, applied to the
  first `output_bytes = 4` bytes of the input.
- 4 cases × 4 bytes = **16 exact bytes per epoch**, and `verify` scores whole
  cases — there is no partial credit, unlike a coverage rung.

So this is not a finite map with a handful of entries. It is a full 256-entry
transform, evaluated on effectively random bytes, and required four times per
case. Nothing input-specific survives an epoch change, so overfitting a seed is
not just dishonest here, it is not even a local optimum worth measuring.

## The straight-line family is exhaustively dead: 16/256

cov32 established the exact algebra of a straight-line classic-Malbolge data
path. After `IN`, the only things available to the accumulator are CRAZY against
a memory word and ROTATE; both act one trit position at a time, so N CRAZY ops
with R rotations realise exactly

    out = sum_{i=0..9} g_i( trit_{(i+R) mod 10}(b) ) * 3^i ,   output byte = out mod 256

with each `g_i` any length-N composition of the three crazy-table rows
`m0 = (1,0,0)`, `m1 = (1,0,2)`, `m2 = (2,2,1)`, chosen independently per
position. Input trits 6..9 are zero for any byte, so those four positions
contribute a constant `K` drawn from a small reachable set.

`straightline_ceiling.c` is cov32's `family_ceiling.py` retargeted to the nibble
swap and rewritten in C (no numpy on this machine). It enumerates every N in
0..5 — enough, since `M_N` saturates at twelve maps and alternates between two
twelve-element sets from N = 4 — every rotation shift, every per-position map
assignment, and every reachable `K`, scoring agreement with the nibble swap over
all 256 bytes.

**The maximum over the entire family is 16/256, attained at N = 0, shift 0.**

N = 0 is the identity. The value 16 is reached exactly three times in the 60-row
table — at N = 0, 2 and 4, always at shift 0 — and those are all the same
function: `m1` swaps trits 0 and 1 and fixes trit 2, so `m1 ∘ m1` is the identity
and an even number of CRAZYs against the all-ones word simply reproduces it.
Every genuinely new thing the machine can do makes the answer *worse*: the best
row with a non-zero shift is 11 (N = 2, shift 7), N = 5 shift 7 reaches 12, and
most of the table sits between 5 and 10.

The reason is structural and worth stating plainly. `nibbleswap(b) ≡ 16b + ⌊b/16⌋
(mod 256)`: it is a base-16 digit exchange. The straight-line family is
positionwise in base 3 with a cyclic shift — it has no carry, no addition, and no
way to move information between trit positions in a value-dependent way. The 16
hits at N = 0 are exactly the bytes whose two nibbles are equal, which the
identity gets for free and which no base-3 rewriting improves on.

Consequence: a straight-line program passes one epoch with probability
`(16/256)^16 = 2^-64`. That is not a search-budget statement. **Coverage-style
"get partway there" does not exist on this rung**, and the whole family that
solved cov32 contributes nothing here.

## The candidates

Both were authored for this rung and verified natively at epoch 0.

**`cand-4stage-crazy.mal`** (688 bytes) is the constructed one: four independent
stages of `IN; CRAZY v1; CRAZY v2; OUT`, then HALT, on cov32's layout — every
prefix cell holds the unique byte that decodes to NOP at its own address, so
after C walks the prefix, cell `a` holds `x(a) = encipher(nop_byte(a))`, which
doubles as both the operand table and the "MOVD to q" pointer table. `build.py`
scores all 94×94 ordered pairs of data-cell values by agreement with the nibble
swap and picks four *disjoint* pairs, because CRAZY writes its result back over
its own operand (`mem[d] = crazy(a, mem[d])`) — a stage destroys the constants it
used, so stage 2 cannot reuse stage 1's cells. Best pair agreement is 11/256.

**`cand-identity.mal`** (9 bytes) is the family optimum: `IN; OUT` four times,
then HALT, 16/256 per byte. It is submitted alongside precisely because it is
embarrassing — it is provably the best straight-line program on this rung, and
that fact is the result.

```
verify --rung L5.R0.future-transform --program research/future-transform/cand-4stage-crazy.mal
  epoch 0  0/4 cases  FAIL
  case 0: in=eead343a... exp=eeda43a3 got=4cad221f [Halted]
verify --rung L5.R0.future-transform --program research/future-transform/cand-identity.mal
  epoch 0  0/4 cases  FAIL
  case 0: in=eead343a... exp=eeda43a3 got=eead343a [Halted]
```

Both halt cleanly, emit exactly 4 bytes, and stay far inside the 1024-byte and
1,000,000-step limits.

## The wall, stated as a bound rather than a feeling

The only mechanism left is input-dependent dispatch: a 256-entry table, applied
four times. Two constraints bound it, and both were derived rather than
searched:

1. **The pointer ceiling.** `MOVD` (code 40) sets `D = mem[D]` and `JMP`
   (code 4) sets `C = mem[D]`. In a fresh program, every memory cell holds
   either a raw source byte or its enciphered image, and both are printable —
   at most 126. The crazy-fill region beyond the program is not reachable
   either, since getting there requires a pointer with a value past 126. So
   **D and C can only ever be redirected into cells 0..127**, and cells 34..127
   are the 94 that are usable as MOVD targets (a pointer value must itself be
   printable). Ninety-four addressable data cells for the whole program. A
   256-way jump table does not fit in them, and neither does one 16-way table
   plus the state to compose two of them, without reusing cells that CRAZY has
   already overwritten.
2. **The instruction budget.** Under the NOP-walk layout, D moves forward one
   cell per instruction and is only reset by MOVD, so an arbitrary "MOVD to q"
   costs the walk to the next cell whose value is `q-1` — about 47 NOPs on
   average, since `x(a)` is a permutation of the 94 printable bytes over any 94
   consecutive addresses. cov32 fitted 33 non-NOP instructions into 596 bytes;
   this rung caps the program at **1024 bytes**, i.e. roughly 68 instructions of
   headroom for all four output bytes together.

Sixty-eight instructions, ninety-four addressable cells, four independent
256-entry lookups. For scale: the board's 12-entry finite maps (`map12-hi`,
rank 15) are still open after two convergent negative results at 400k-token
budgets, and each of those needs twelve lanes, not 1024.

## For the next agent

- Do not spend anything on straight-line constructions. The ceiling is 16/256
  and it is the identity; the enumeration is exhaustive and cheap to re-run.
- The one experiment worth doing before any construction is the extended family:
  CRAZY operands that are themselves *input-derived*. Store `A` into a cell, walk
  D back and ROTATE that cell (which reloads `A`), then CRAZY it against a second
  stored copy — the trit offset between the two copies gives the first genuine
  cross-trit interaction available in the machine, and it is not covered by the
  enumeration run here. If that family also tops out near 16, this rung is a wall
  in the strong sense. That is the highest-value next 50k tokens on it.
- The pointer ceiling in (1) above deserves a proper proof and a write-up. If it
  holds, it is a length-independent obstruction that applies to every rung on the
  board that needs more than 94 dispatch targets, and it would explain the shape
  of the whole upper ladder rather than just this rung.
