# Process log: L2.R2.rotate-1, Fable 5 run (2026-09-05)

Builder session, Fable 5 (Claude Code), model claude-fable-5, autonomous.
Order below is chronological; every score is model-VM-measured unless marked
native. Native = `./target/release/malbolge-rungs` at scratch-clone HEAD 1b6ec77,
trace dir on.

## 1. Closure BFS (port of research/xor-1-fable5/reach.c, target rotl(b,1))

`reach_rot.c`, results in `closure.log`:

- A (CRZ-only): **182/256** reachable, worst min-depth 3.
  Unreachable set has block structure: {0, 63..109, 150..161, 209..215,
  243..248, 255}. Compare xor51: 193/256. The wall statement transfers:
  no ROT-less table-walk architecture can exceed 182 at ANY stride/length,
  and the exact table-family ceiling (63/256, 2026-08-10 record) stands as
  the buildable reality.
- B (CRZ+ROT): **256/256** at depth <= 5 (xor: 256/256 at <= 5). Per-input
  ROT timing is in-principle sufficient here exactly as for xor.
- C (B + swapped-CRZ): 256/256 at depth <= 4.
- D (CRZ + swapped-CRZ, NO ROT) — new variant, not in the xor run:
  **227/256**; unreachable exactly 81..109. So even giving the walk both
  CRZ roles, ROT-less architectures are dead; the 29-input hole is
  contiguous and centered on the b-range whose rotl images sit at 162..219.

## 2. Exact DP, base stride-1 layout (dpk_rot.c = dpk2.c with rotl target)

Sweep k in {3,5,7} x K0 1..23 at L=256 (`sweep_L256.log`):
best **62/256 at k=7, K0=1** (k=5 best 61 at K0=3/4). The 2026-08-10
idealized bound for this family is 63; the buildable layout costs 1.

Assembled `cand_k7_o1_L256.mal` (build_rot.py): DP=62, model=62,
**native 62/256** (`verify --epochs 256 --json`, exit 1, 62/256 epochs
passed; `verify_native.json`, covered set in `covered_native.txt`, model
covered set identical byte-for-byte). First candidate ever recorded on this
rung.

## 3. Premix (rotr^J of parked b before the walk)

- Optimistic probe (J on the base spec, no gadget cost, `premix_probe.log`):
  J=7 (= 27b exactly, since rotr^7 trit-shifts b left 3 with no wrap for
  b<=255) lifts the DP to **73/256** (k=5, K0=2). First transform on the
  board where premix arithmetic BEATS the base family (xor: premix lost,
  54 vs 68).
- True premix layout (build_rot3.py = build3.py ported, P=19+3j+K0+k;
  `premix_sweep.log`): best **60/256** (j=7). The 40+-cell code shadow
  poisons the low-b operand windows and eats the entire gain, same
  inversion the xor run measured. Premix does not build past the base 62.

## 4. L-sweep spot check (`lsweep_rot.log`)

k=7 K0=1: L=200 -> 50, 232 -> 59, 248 -> 61, 255 -> 62, 256 -> 62.
Monotone losing, exactly as the xor L-sweep closed. Crazy-fill operands
buy nothing here either.

## 5. Pure-ROT-loop lemma (`rotloop_lemma.txt`)

A loop whose body only rotates a copy of b — even with a PERFECT per-input
exit oracle n(b) — yields acc in {rotr^k(b)}, and rotr^k(b) mod 256 hits
rotl(b) for some k for exactly **7/256** inputs ({0,120,135,153,175,183,
255}). Exact, exhaustive, 2560 checks. Data-dependent control flow must do
CRZ work inside the loop body; rotation-only loops are dead on this rung.

## 6. Shared straight-line two-register family (`sline.c`)

The rotl analogue of xor's "branchless CRAZY/ROT = 34/256": same op
sequence for all inputs, acc0 = rotr^j0(b), second source s = rotr^j1(b)
(second park), ops = crazy(acc,c) / crazy(c,acc) / rotr(acc) /
crazy(acc,s) / crazy(s,acc), constants free (envelope: any word).

- rotl: **89/256** search-best, 7 of 8 independent seeds converge to 89 at
  depths 6 and 8 (`sline_s*.log`). Winning depth-6 genome: acc0=9b, s=3b —
  crazy(25873,acc); crazy(47535,acc); crazy(acc,9414); crazy(13515,acc);
  crazy(acc,s); rotr(acc). The 9b/3b register pair is the profound
  dispatcher's style, arrived at independently by the anneal.
- xor51 cross-check (`sline_xor.c`, `slx_s*.log`): 34-42 search-best —
  consistent with the recorded exhaustive 34 for one register; the second
  register + free constants buys xor only ~8 and stays far under the walk's
  68. The family DOMINATES for rotl (89 > 63-ceiling walk) and is minor for
  xor. Transform-dependence noted for the ranking.
- Cost-restricted anneals (constants limited to rotr^k(legal byte)):
  k<=3 (`sl2_s*.log`, interim before timeout): ~51 best — too weak.
  k<=9 (`sl3_s*.log`): see below.

## 7. Buildability of the 89-family

The family reads NO b-indexed table, so the premix code-shadow tax does not
apply — but the MOVD reach bound (D targets <= 127, program bytes <= 126)
forces ALL data cells (parks, pins, constants) below 128, hence CODE length
<= ~85 (build3.py's own layout_valid check). Cost accounting per gate:

- op0 crazy(acc,c): 1 code + 1 constant cell (k_i prep rots)
- op2 rotr(acc): 2 code + 1 pin (2X mod 94 constraint on the acc cell)
- op3/op4 with s=b: read park1's m[72] directly — final-op only (CRZ
  destroys it) — 3 code; earlier uses need park2 (+10)
- op1/op4 swapped with constant: A must be ROT-loaded from a staged cell:
  ~6 code + 2 pins + 1 constant
- register j0: park2 (+10) + 3*j0; constant prep: ROT/NOP sweep passes =
  k_max*(m_rot+3) code

The 89 winners are op1-heavy with j0 in {7,8,9} and deep-orbit constants:
~150-170 cells — NOT assemblable under the 85-cell code cap.

Gate-restricted anneals bracket what is buildable:
- gates {0,2,3} only (assembly-trivial), constants k<=9: **49/256**
  (4 seeds, depth 9, `sl4_s*.log`). The swapped gates carry the 89.
- constants k<=3, all gates: ~51 interim (`sl2_s*.log`).
- cost-modeled anneals: 74/256 at a naive 85-cell budget (`sl5_s*.log`);
  **36/256** under the true per-op costs and the real P<=71 cap
  (`sline8.c`, `sl8_s*.log`, 4 seeds converged). Honest layout costs
  collapse the family from 89 to 36 — BELOW the walk family's 62.

## 8. The emitter, and two native witnesses

`emit.py` assembles any j1=0 genome exactly: concrete D simulation
(D is b-independent throughout the family), BFS pin routing with
on-demand assignment, C=40 pad-and-renav (the 122 pin doubles as NOP),
P<=71 enforcement, model-VM check against the genome's Python semantics.
Two emitter bugs found and fixed en route are recorded here because they
are layout facts, not code accidents: (a) an instruction landing exactly
at C=40 must be the pad NOP, and the pad shifts D, so every act needs
re-navigation; (b) any op targeting cell 107 clobbers the register —
genomes with swp-before-first-crz or reg-after-a-107-rot are unbuildable.

The three 36-scoring genomes emit at P=74-81 — over the cap; their fat is
multi-rot constant prep. An exhaustive enumeration of the zero-prep
structure acc=rotr^j0(b); rot^l; crz(c1); swp(c2); rot^t; crz(acc,b) over
all byte-or-one-rot constants (`enum_cheap.c`) gives exactly **34/256**
(j0+l = 9, i.e. acc = 3b; c1 = 78; c2 = 41 staged as byte 123). Assembled
at **P=68, 124 bytes** (`cand_sline34.mal`, placement override at cell 84)
and natively verified: **34/256 epochs** (`verify_sline34.json`), model ==
native. First working two-register straight-line Malbolge program with a
manufactured-constant chain on the board.

## 9. Where the rung stands

Best build: the walk-family `cand_k7_o1_L256.mal` at **62/256 native**.
The straight-line family dominates in free space (89 vs 63) and loses
under layout (34-36 vs 62): rotate-1 at 256 bytes is now bracketed by
three measured walls — arithmetic (89 free-space ceiling of the richest
known gate set), layout (P<=71 collapses it to ~36), and the closure
theorem (182 CRZ-only / 227 no-ROT / 256 with per-input ROT timing).
The one unpriced door is unchanged: data-dependent control flow, which
must do CRZ work inside the loop body (the pure-ROT-loop lemma's 7/256).
