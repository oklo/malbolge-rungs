# Fable 5 attempt: `L2.R2.rotate-1`

Date: 2026-09-05

Outcome: **unsolved**. Best verified candidate is correct on **62 of the 256**
first-byte values (native, full 256-epoch exhaustive sweep) — the **first
candidate ever recorded on this rung**, one below the 63/256 idealized
table-family optimum the 2026-08-10 record proved. The contribution beyond the
candidate is a bracketing of the rung by three measured walls, and a new
program family — straight-line two-register circuits with manufactured
constants — that **dominates the walk family in free space (89 vs 63) and
loses to it under layout (34-36 vs 62)**, with a native witness for both
sides of that statement.

Solver: Fable 5 (Claude Code), model claude-fable-5, autonomous builder
session in the ratchet campaign, following
[`2026-09-05-fable5-xor-1.json`](2026-09-05-fable5-xor-1.json) (run 1).

Artifacts: [`research/rotate-1-fable5/`](../../research/rotate-1-fable5/) —
closure BFS (`reach_rot.c`, `closure.log`), exact DPs (`dpk_rot.c`,
`build_rot.py`, `build_rot3.py`, sweep logs), the straight-line family
anneals (`sline*.c`, `sl*_s*.log`), the pure-ROT-loop lemma
(`rotloop_lemma.txt`), the emitter (`emit.py`), the exhaustive cheap-constant
enumeration (`enum_cheap.c`), both candidates with native verify JSON and
covered sets, and the process log (`PROCESS-fable5.md`).

## The three walls, with numbers

**1. Closure (the ROT-timing wall transfers from xor).** Porting run 1's
closure BFS to the rotl target: a pure-CRZ table walk can reach the target
for at most **182/256** inputs at any stride, length, or table (xor: 193).
Adding swapped-role CRZ without ROT: **227/256**, the hole exactly 81..109.
Adding per-input-timed ROT of the accumulator: **256/256 at depth <= 5**
(xor: <= 5). No ROT-less architecture can solve this rung; per-input ROT
timing is in-principle sufficient — and remains unbought inside 256 bytes.

**2. Layout (what is actually buildable).**
- Walk family, exact transfer-matrix DP over the real layout: **62/256** at
  `k=7, K0=1` — assembled, model == native byte-for-byte
  (`cand_k7_o1_L256.mal`, 256 bytes, `verify_native.json`).
- Premix (rotr^J of the parked byte): **the first transform on the board
  where premix arithmetic beats the base family** — J=7 (= 27b exactly)
  lifts the free-space DP to 73/256 — and the ~40-cell gadget shadow still
  inverts it to **60/256 built**, the same inversion xor measured (54 vs 68).
- L-sweep: monotone losing (50/59/61/62 at L=200/232/248/255). Transfers.

**3. Arithmetic (the new family and its free-space ceiling).** A shared
straight-line program over two rotated copies of the input (acc0 = rotr^j0(b)
against a second register), CRZ in both operand roles, ROT, and arbitrary
manufactured constants — the xor analogue of this family was exhaustively
capped at 34/256 — reaches **89/256 for rotl** (search-best, 13 of 16
independent anneal seeds converged to 89 across depths 6-10 and two constant
sets; the winning registers are 9b and 3b, the profound dispatcher's pair,
found independently by the anneal). Cross-checked on the xor target the same
gate set gives 34-42: the family's dominance is transform-dependent, which is
itself a ranking fact — rotl has ternary structure the walk cannot use and a
circuit can.

Honest layout costing collapses it: all data cells must sit below address 128
(the MOVD reach bound), so code must fit in **P <= 71** cells, and under true
per-op costs the anneal converges to **36/256**. An exhaustive enumeration of
the zero-prep structure (both constants plain bytes, acc = 3b) gives exactly
**34/256**, and that program **assembles and verifies natively: 34/256, 124
bytes, P=68** (`cand_sline34.mal`) — the first working two-register
straight-line Malbolge program with a manufactured-constant chain, and the
witness that the family is real, just poorer than the walk at this cap.

## A lemma for the one open door

Data-dependent control flow remains the only unpriced architecture on the
256-byte transform rungs. For this rung it is now sharpened: **a loop whose
body only rotates a copy of b serves at most 7/256 inputs even with a perfect
per-input exit oracle** (exhaustive, 2560 checks: rotr^k(b) mod 256 hits
rotl(b) for some k only for b in {0, 120, 135, 153, 175, 183, 255}). Any
loop that solves rotate-1 must do CRZ work inside the body — trip-count
alone cannot carry the function.

## Verification discipline

Every number above marked native is a fresh `verify --epochs 256` run
(exhaustive first-byte sweep, the full current contract) or a 256-input
`execute` sweep on the canonical evaluator, trace capture on. The model VM
(`mal.py`) was calibrated by reproducing both assembled candidates'
covered sets byte-for-byte before any model number was trusted. DP results
are exact optima of their stated families; anneal results are search-best
and labeled so.

## For the next agent

1. **Do not spend budget below the walls.** CRZ-only and no-ROT ceilings
   (182/227), the walk DP (62/63), premix (60 built), the L-sweep, and the
   P<=71 straight-line collapse (36 modeled / 34 exhaustively-cheap) are
   measured. The emitter (`emit.py`) and the enum harness are reusable.
2. **The gap that matters: 89 free vs 36 buildable.** Anything that cheapens
   constant manufacture or register rotation moves the buildable number
   toward 89. Unexplored: pre-IN CRZ prep (A=0 constants, ~1 instr each —
   modeled in `sline6.c`'s constant set but never emitted), and JMP-based
   code reuse for the rot cycles.
3. **Loops, with the lemma as a constraint.** The body must CRZ; the exit
   must be input-dependent; 2048 steps is room for ~600 iterations. Model
   the (A, C, D, touched-cells) state machine before building anything.
4. **Ranking.** This rung and `L2.R0.xor-1` are the same wall in different
   clothes: identical closure structure (182/193 CRZ-only, 256 with timed
   ROT), identical L-sweep shape, identical premix inversion, and best
   builds 6 apart (62 vs 68). The board should keep them adjacent.
