# Claude attempt: `L2.R0d.xor-1-len4096` (the last wall, and a search bug)

Date: 2026-08-11

Outcome: **unsolved**. This run does not beat prior art's coverage number. It
does two things that matter more for whoever takes this rung next:

1. **`b = 0` is reachable, and that is proven natively.** Three records have now
   framed this rung around the four low inputs. The first two called `b = 0,1,2,3`
   "provably unreachable"; hero1 retracted that for `b = 1,2,3` but kept `b = 0`
   as blocked by the prologue and priced the fix at "hours of compute" for a
   four-dimensional phase enumeration. The actual fix is **two prologue bytes and
   two chain cells**, and `research/xor-1-len4096-hero2/proof_b0.mal` is a program
   that the native VM runs on input `0x00` to output `0x51`.
2. **hero1's block-local DFS was unsound on exactly the inputs this rung is stuck
   on.** It enciphered a JMP's own cell; the VM enciphers the jump *target*. Every
   witness whose path crosses a JMP was spurious — which is every witness for
   `b = 0,1,2,3`, because their path *is* the dispatch JMP. No wrong program ever
   shipped (the assembly pass re-scored with the correct simulator before
   accepting), but the search was blind on the hard cases while reporting
   hundreds of hits on them.

Solver: Claude (Opus 5) via Claude Code, autonomous single-session run under a
hard cap of 900k tokens / 150 minutes.

Builds on [`2026-08-11-claude-hero1-xor-1-len4096.json`](2026-08-11-claude-hero1-xor-1-len4096.json)
(249/256; its simulator, DFS and optimiser are reused with the fix above, and its
`would_try_next` list is what this run executed), and through it on
[`2026-08-11-claude-push-xor-1-len4096.json`](2026-08-11-claude-push-xor-1-len4096.json)
(229/256, the private-code-block architecture) and
[`2026-08-11-claude-xor-1-len4096.json`](2026-08-11-claude-xor-1-len4096.json) (119/256).

Artifacts: [`research/xor-1-len4096-hero2/`](../../research/xor-1-len4096-hero2/) —
`sled.py` (the finite table that collapses the prologue problem), `swap.py` (the
chain-route derivation), `hero9.c` (corrected DFS + the new search modes),
`hero3.c`/`hero4.c`/`hero5.c`/`hero6.c` (the intermediate modes, kept so the
progression is auditable), `proof_b0.mal`, `swap.mal`, `swap_rep.mal`, `nc.sh`
(parallel all-256 native check), `cand.mal`, run logs.

## 1. The prologue problem is a two-cell constraint, not a search

Input `b` resumes at `9b + 1`. For `b = 0,1,2,3` that is address 1, 10, 19, 28 —
inside the prologue, already executed and therefore enciphered. hero1 established
why that is survivable: the VM errors only on a **non-printable** word, XLAT2 maps
`33..126` onto `33..126`, and a printable word decoding outside the eight codes
hits `_ => {}` and is a runtime NOP. So the enciphered prologue is a NOP sled, the
input slides to the dispatch JMP at address 32 (never enciphered, because the VM
sets `c = m[d]` *first* and enciphers the target), and re-dispatches through
`m[104]`, `m[95]`, `m[86]`, `m[77]` for `b = 0,1,2,3`.

hero1 then treated "find a prologue phase whose enciphered image is clean at all
four entries" as a four-dimensional search: NOP padding positions × d-chain routes
× CRAZY pair × rotation-cycle pointer. It is not a search. `sled.py` enumerates
the whole thing in one table — for every sled entry and every source code that
could sit there, what does the enciphered image decode to:

```
     addr  JMP     OUT     IN      ROT     MOVD    CRZ     NOP     HLT
  b=0   1  -       -       -       -       IN      -       -       -
  b=1  10  -       -       -       HLT     -       -       -       -
  b=2  19  -       -       -       -       -       -       -       -
  b=3  28  -       -       -       -       -       -       -       -
        ('-' = decodes outside the eight codes = runtime NOP = safe)
```

**Exactly two of the 32 combinations are unsafe.** Don't put MOVD at address 1;
don't put ROT at address 10. Addresses 19 and 28 are safe for every code, which is
why prior art's phase was already clean there. There is nothing to enumerate.

### The fix is a swap, not an insert

Address 1 holds the first MOVD because a MOVD executed while `d == c` reads its own
cell, and that is the only way to get `d` off the `c` track. `byte_for(MOVD, 1) = 39`
uniquely, and `X2[39]` decodes to IN at address 1 — that is the whole of `b = 0`'s
problem, and it is why hero1's DFS reported `nodes=1`.

hero1's candidate fix inserted a NOP at address 1. That starts the chain at 39
instead of 40, the shortest route from 39 to the forced `(71,72)` CRAZY pair is one
hop longer, so the insert costs **two** addresses, and old address 8 (ROT) lands on
address 10 — the one other unsafe square on the board. hero1 measured the trade and
stopped there.

Swapping instead of inserting avoids the shift entirely:

* address 0 = MOVD. With `d = c = 0` it reads its own cell, `m[0] = byte_for(MOVD,0) = 40`
  (unique), so `d = 40`, then 41.
* address 1 = IN. Reads `b`, `d` becomes 42. Its enciphered image at address 1 is a
  runtime NOP — the table above, IN column.
* address 2's MOVD now reads `m[42]` instead of `m[40]`.

The prologue is still 33 bytes and every instruction from address 2 on is at the
same address as before, so no block moves and no other input's code is disturbed by
the phase itself. Only the d-chain needs re-seating, and `swap.py` shows the route
is forced: `m[42]` must be legal at address 42 *and* land one hop from the CRAZY
pair, and over all 94 residues **`m[42] = 91` is the unique solution** (ROT at 42,
then `m[92] = 70`, NOP at 92). Cells 40 and 123 are freed; 42 and 92 become forced.

Native check of the swapped program built from hero1's 249 tape: **207/256**, with
`b = 2` still solved — the architecture survives. One assembly pass at step cap 60
takes it to **240/256**, and the model reproduces both numbers with byte-identical
miss sets.

### Native proof for b = 0

`hero9 -solve1 0` runs the corrected block-local DFS for `b = 0` against the
swapped tape, applies witness 0 verbatim with **no repair**, and writes the program.
That program scores 113/256 overall — it is not a candidate, it is a proof — and:

```
$ malbolge-rungs execute --program proof_b0.mal --input-hex 00
  "output": [ 81 ],  "output_hex": "51",  "status": "Halted",  "steps": 78
```

`0 ^ 0x51 = 81`. **`b = 0` is not a wall.** No input on this rung is now known to be
structurally unreachable.

## 2. The DFS bug, and why it hid precisely the hard cases

The first `b = 0` witness I extracted did not reproduce: the native VM returned 223
instead of 81. Model and native agreed exactly on the resulting program (120/256,
identical miss sets), so the simulator was right and the *search* was wrong.

`simulate()` implements JMP the way the VM does — `C = mem[D]`, then encipher
`mem[C]`, which is now the target. `rec()`, the DFS, computed `nC = mem[D]` into a
local and then enciphered `mem[C]`, the JMP's own cell. The two models disagree on
every path containing a JMP.

The dispatch JMP at address 32 is on the path of `b = 0,1,2,3` **by construction** —
that re-dispatch is the entire mechanism hero1 discovered. So every witness ever
reported for those four inputs was computed under the wrong semantics. The
consequences were invisible because `try_input` and the assembly pass apply a
witness and then re-score with `simulate()`, accepting only on a non-negative
global delta: bad witnesses were silently rejected. The pipeline was safe and the
shipped 229 and 249 are real. But the searcher spent its time on the four inputs
that mattered most while unable to solve any of them, and reported large witness
counts that were not witnesses.

The fix (`hero9.c`) is two lines plus one subtlety: encipher `nC` rather than `C`,
and — because the byte the DFS chooses is the *raw* cell while what executes is
`X2[byte]` — branch on the jump target *before* the encipherment. With it, `b = 0`
has 20 witnesses at step cap 45 instead of 232 bogus ones, and witness 0 reproduces
natively.

## 3. Two of hero1's three "prologue" misses were never prologue misses

Running the DFS for `b = 1` and `b = 3` against **prior art's own unmodified
prologue** finds witnesses: 3 for `b = 1`, 1057 for `b = 3`. They are tape problems,
reachable through the re-dispatch with no prologue change at all. Only `b = 0` ever
needed the swap.

What hid them is the **step cap**. `b = 0`'s sled is 31 steps of NOP just to reach
the dispatch JMP; `b = 1`'s is 22. hero1 searched at caps of 14, 16, 18 and 26 and
reported the cap as its cheapest lever, worth +2 each time. Nothing below about 35
can see a sled route at all. The lever was real and hero1 stopped one notch short of
where it changes the answer rather than the count.

Likewise `b = 151`, which hero1 reported as tape-limited on the evidence of an
exhaustive block-local DFS that ran to completion and found nothing: on the swapped
tape it is solved by a plain assembly pass. That finding was true of *that tape*,
not of the architecture.

## 4. What is actually exhausted

Two of hero1's suggested levers are spent, and saying so is worth as much as the
gains:

* **Step cap and span, on hero1's tape.** Assembly passes at `(steps, span)` of
  (26,16), (40,18), (40,27) and (60,27) all return exactly 249/256 with the
  identical miss set. The "+2 per cap raise" trajectory ended at 249.
* **Single-cell coordinate descent.** A full sweep of the shared window `[34,210]`,
  all 8 codes per cell, each probe followed by exhaustive assembly repair and a
  reroll pass — 68 s per pass — moves nothing from 249. hero1's sweep used a random
  `repair_pass(120)`; replacing it with an exact repair does not rescue the move
  class. The tape is at a strict single-cell local optimum.

The `-map` mode quantifies why. Cell 73 is read by 233 of 256 inputs, 62 by 117, 74
by 120, 75 by 84; 367 cells are read by more than one input, and the contested
surface reaches into the crazy-filled tail. The moves that matter are **coordinated
and multi-cell**: `-need` shows `b = 8` and `b = 9` both require `m[74] = 118` and
`m[75] = 117` *together*, which no single-cell move can reach. That motivated the
`-hunt` mode (apply a whole witness including its shared-cell changes, then pay for
the damage with exhaustive repair, least-disruptive witness first, gains compounding
within a run).

## 5. Coverage, honestly

Prior art's 249/256 (old prologue) remains the best coverage number on this rung;
this run did not beat it. The shipped candidate is `cand2.mal`, **247/256** measured
natively on all 256 bytes, missing `0, 1, 3, 4, 5, 8, 9, 10, 255` — note that
`b = 151` is solved. It reached that from a 207 start with the fleet still climbing
when the clock ran out. That is the cost of the swap: it buys `b = 0` — and, on the tapes seen
here, `b = 151` — but it re-forces `m[42]` and `m[92]`, which are read by many
inputs, and re-optimising the tape around them is most of a hero1-sized search.

The two lines are not competing architectures. The swap is a two-byte edit to
hero1's program. The right next run seeds the swapped prologue with hero1's 249
tape (which is what `swap.mal` already is), runs the corrected DFS at step cap ≥ 45,
and spends its whole budget on the tape rather than on rediscovering the structure.

## Budget and what I would do next

Spent: roughly 300k tokens and 145 minutes of the 900k / 150-minute cap; time was
the binding constraint, not tokens, and about 60% of the wall clock was search
compute on 14 cores. Neither the program-length cap (2305 of 4096 bytes) nor the
step cap (≤ 80 of 2048) binds.

**Wall or budget? Neither, now. It is a plain optimisation problem.** Every one of
the 256 inputs has a demonstrated witness — `b = 0` natively, the rest in a
simulator that agrees with the native VM byte for byte at 120, 207, 240 and 249.
Nothing on this rung is known to be structurally impossible any more. What remains
is getting one tape to satisfy all of them at once, and that is search.

With more budget, in priority order:

1. **Re-run hero1's full pipeline on the swapped prologue with the corrected DFS
   and step cap ≥ 45.** hero1 went 229 → 249 in one session on the old prologue with
   a DFS that was unsound on four inputs and a cap that could not see the sleds.
   The same pipeline, fixed, starting from `swap.mal`, is the obvious next run and
   was not affordable here.
2. **Escape to private tape.** The re-dispatch for `b = 0,1,2,3` lands at
   `m[104] + 1 ≤ 127`, deep in the contested region, which is why `b = 0`'s
   witnesses rewrite 15–40 shared cells. But a CRZ writes `crazy(A, m[d])`, which can
   be any word up to 59048, so a block can compute a large value into a cell and
   then JMP or MOVD through it into private territory. The program is 2305 of an
   allowed 4096 bytes: **give the hard inputs a private landing area at 2305..4095**
   and their solutions stop costing anything globally. hero1 tried `N = 4096` only
   as a free tail and found it slightly worse; as a jump destination it is a
   different and much stronger idea. This is the single highest-value untried thing
   on this rung.
3. **Tape annealing with the decomposed objective**, which hero1 named and this run
   only partly built: with the shared window fixed, score a tape by "number of
   inputs with an exhaustive block-local solution" (256 independent DFS calls) rather
   than by the assembled program, so assembly conflicts leave the landscape. The
   `-hunt` mode here is the coordinated-move half of that; the decomposed objective
   is the other half.
4. **Sweep the last two program bytes exhaustively** (64 tail families). Still not
   done — hero1 flagged it, this run treated them as ordinary sweep cells.

## Three warnings for the next agent

**`verify` is a sampling event on this rung.** One case is drawn per epoch from the
seed and `min_epochs` is 5, so a program correct on `n`/256 passes with probability
`(n/256)^5` — 87% at 249. hero1 already flagged this; it is worth repeating because
a green `verify` on this rung means nothing. Measure all 256 bytes through
`execute`. `nc.sh` does it in under a second on 14 cores.

**Check your searcher against your simulator, not just your simulator against the
VM.** hero1 validated the simulator against the native VM meticulously and that
validation was sound. The bug was one level down, in the DFS that proposed
candidates *to* the simulator, and the pipeline's own safety check hid it. If your
search reports a witness, apply it verbatim with no repair and confirm the input
actually flips.

**Don't inherit a cost estimate either.** hero1 correctly retracted "provably
unreachable" and then priced the remaining piece at hours of compute across a
four-dimensional phase space. It was a 32-entry table and a two-byte swap. This
rung has now had a structural claim overturned three times running; the pattern is
that the claims are about the *architecture* and the answers are in the *VM source*.
