# Claude attempt: `L2.FM3.xor51-map16` — **unsolved, 15/16 natively verified**

Date: 2026-08-11

Outcome: **unsolved.** `verify` reports `15/16 cases FAIL`, failing only on
case 6, input `0xa7`. That is the first program ever emitted on this rung: the
prior record ([`2026-08-10-claude-map16`](2026-08-10-claude-map16.json)) had
**zero** verified cases and a model-level best of 12/16.

Program: [`2026-08-11-claude-push-map16.best.mal`](2026-08-11-claude-push-map16.best.mal)
— 1988 bytes, 1107 steps, well inside the 4096-byte / 2048-step limits.

Solver: Claude Opus 5 via Claude Code, autonomous single-session run under a
hard cap of 700k tokens / 100 minutes, as part of a board-calibration survey.

Builds on [`2026-08-10-claude-map16.json`](2026-08-10-claude-map16.json)
(architecture, the trit-4 forcing law, and the diagnosis of its own stopping
point) and [`2026-08-11-claude-push-map12-low.json`](2026-08-11-claude-push-map12-low.json)
(NOP-spaced walks, the phase shift `s`, and the working builder skeleton).

## Summary

Three results, in descending order of what they cost and what they are worth.

1. **15/16 is verified, not modelled.** The prior record's item 1 — "finish the
   chain builder, this is the whole gap between 0 verified and ~12" — was
   right about the blocker and wrong about the size of the prize. Fixed, the
   architecture lands on its own ceiling exactly.
2. **The 15/16 ceiling is exact over the whole spec space, not 80
   configurations.** The prior record swept 5 trit-4 maps × 2 parities × 8 high
   parts. Sweeping *all* 8⁶ = 262144 per-trit dispatch specs × all 81 constant
   choices × all walk depths gives the same answer: 15/16, dead lane `0xa7`,
   every time.
3. **A second forcing law, on trit 3.** The prior record's ceiling argument
   stops at trit 4. There is one more level, and it bites: it cut the surviving
   15/16 configurations from 4088 to 408 and it is what made the difference
   between a build that stalls at 13/16 and one that reaches 15/16.

And one negative: **the prior record's item 3 — "put a ROT inside the walk …
this is the only idea on the list that can beat 15/16" — cannot work.** See §5.

## 1. The blocker the prior record stopped on, and the fix

That record ended inside its operand-chain builder: leg 2 of the chain left `W2`
as a rotation of `W1` *in the same cell*, so the two dispatch operands could not
coexist, and adding a filter requiring leg 2 to end in a CRAZY returned nothing.

The filter was on the wrong end of the leg. What matters is that leg 2 **opens**
with a CRAZY into a fresh cell — that is what stops the first op from rotating,
and destroying, the cell holding `W1`. Leg 2 may then rotate freely, because it
is rotating its own new cell.

Stated as a graph problem the whole thing collapses. Every prefix cell `q` in
`34..127` is a NOP in the initial sled, so by the time `D` reaches it the cell
holds `xval(q) = ENC[codebyte(q,NOP)-33]`; `xval` is a bijection on that range,
so *every* printable byte is available as a CRAZY operand at exactly one cell
(and therefore each CRAZY in the chain must use a distinct operand byte). A ROT
re-navigated to the cell the previous op wrote rotates the accumulator. So the
chain is a shortest path in

```
a -> rot_r(a)                 (rotate the current cell)
a -> crazy(a, v)  v in 33..126 (crazy against a fresh cell holding v)
```

from `0` to `W1`, then from `W1` to `W2` with a crazy first. That graph has
26944 reachable words and BFS over it costs under two seconds
(`research/map16-push/chainfind.py`). The shipped chain is ten ops:

```
leg1 (0 -> W1 = 30361):  CRZ(62) ROT ROT ROT ROT ROT ROT ROT
leg2 (W1 -> W2 = 29521): CRZ(33) CRZ(54)          <- opens with a CRAZY: W1 survives
```

## 2. Dropping two assumptions the earlier records carried

Both prior records on this family fixed **identity dispatch on trits 0..3** and
a **crushed trit 5**. Neither is required. `W1` and `W2` are ordinary memory
words, so the trit map `g_i = M[w2_i] ∘ M[w1_i]` may be chosen *independently
per trit*; all that is actually required is that the sixteen dispatched
addresses `A0(b) = Σ_i g_i(b_i) 3^i` are distinct and in range.

That turns "which `K0`" into "which of 8⁶ low specs, times which four
constants". Of the 262144 low specs, **3094 keep the sixteen addresses
distinct**. `research/map16-push/spec.py` scores all of them against all 81
constant choices and all walk depths. Relaxing the assumption is what produced
a configuration that is simultaneously high-scoring *and* cheap to build — the
shipped spec dispatches trits 3 and 4 by `(2,2,0)` and trit 1 by `(0,1,0)`,
which no earlier sweep could reach.

The freedom does **not** raise the ceiling. It is still 15/16 and still `0xa7`.

## 3. The trit-3 forcing law (new)

The prior record's law: table operands are printable, so their trit 4 is never
2, so once the accumulator's trit 4 leaves 2 it alternates and cannot return.
A lane whose required `L*` has trit 4 = 2 must therefore hold trit 4 = 2 for the
whole walk, which forces **every one of its `K` operands to be a byte ≥ 81**.

Push that one level down. A byte `v` in `81..126` has `v − 81 ∈ [0,45]`, and
`45 < 54 = 2·27`, so **trit 3 of such a byte is 0 or 1 — never 2**. The two
crazy rows trit 3 can then select are `(1,0,0)` and `(1,0,2)`, which agree on
`a = 0` and `a = 1`. So for exactly the lanes that need trit 4 = 2, trit 3 obeys
the same law: it is pinned to `(start + K) mod 2` unless it starts at 2.

This is not decoration. Measured:

| model | configurations reaching 15/16 | build outcome |
|---|---|---|
| trit-4 law only | 4088 | stalls at **13/16** (`0x82`, `0x85` unreachable) |
| trit-4 + trit-3 | 408 | reaches **15/16** |

The 13/16 program was built, verified natively, and failed on exactly the two
lanes the trit-3 law predicts are impossible — `0x82` needs trit 3 = 1 from a
start of 1 at odd `K`, which is arithmetically unavailable. A random search over
4000 `(P, s)` pairs at `K = 5, 7, 9` never made all three trit-4 = 2 lanes pass
together, because one of them never can. Choosing the spec with the trit-3 law
in the objective fixed it on the first build.

## 4. The verified program

```
$ ./target/release/malbolge-rungs verify --rung L2.FM3.xor51-map16 \
      --program docs/attempts/2026-08-11-claude-push-map16.best.mal
  epoch 0 seed=d345d26d…  15/16 cases  FAIL
    reason: case 6 mismatch: expected f6, got 5f (status Halted)
RESULT: FAIL (native evaluator)
```

Configuration: `g(trits 0..5) = [(0,1,2),(0,1,0),(0,1,2),(2,2,0),(2,2,0),(0,1,2)]`,
constants `(2,0,0,0)`, `W1 = 30361`, `W2 = 29521`, `K = 3`, walk pattern
`P = [0,5,32]`, phase `s = 34`, addresses `1476..1920`, code ends at 1107.
`K = 5` (`P=[0,5,28,33,79]`, `s=5`) and `K = 7` also reach 15/16 natively — the
same `H` is shared by every odd depth, so depth is free above the parity.

**The model is exact.** Every build in this run predicted its native score to
the case: 13/16 predicted → 13/16 native; 15/16 predicted → 15/16 native, with
the identity of the failing lane matching too. The earlier record's caveat that
its numbers were "a model prediction … not run against the native VM" no longer
applies to this architecture.

## 5. Why ROT inside the walk cannot beat 15/16

The prior record's item 3 names this as "the only idea on the list that can beat
15/16, and the one I would run first if the goal is a solve". It cannot, and the
reason is one line of the VM:

```rust
39 => { let rotated = rotate_right_word(self.memory[self.d]);
        self.memory[self.d] = rotated;
        self.a = rotated; }
```

ROT **overwrites** the accumulator with a function of the cell alone; it does
not combine with it. (The board's own site text says as much: "it does not
combine with the accumulator entirely — it rotates what d points at.") So a ROT
placed in the walk discards everything accumulated so far. Worse for the stated
purpose: `rot_r(v)` of a printable byte has trit 4 = 0 identically, so after a
walk ROT *every* lane's trit 4 is 0 and pinned, and every lane's final trit 4 is
the same value — strictly weaker than the status quo, where lanes starting at 2
can each choose their own drop-out step. The one thing a walk ROT does buy is a
per-lane high part (trit 9 becomes `v mod 3`, worth an offset of 227 mod 256),
but two choices per lane cannot bring sixteen targets spanning the whole byte
range into a single 81-wide window. This item should be struck from the list.

## 6. What I ruled out

- **The dispatch family.** 0 separating configs of 143808, by the board's own
  tool. Inherited, not re-searched.
- **16/16 in the data-dispatch table architecture.** Exact, now over the full
  spec space: all 262144 per-trit specs (3094 of which keep the addresses
  distinct) × 81 constant choices × walk depths 2..9. Best is 15/16 and the
  dead lane is `0xa7` in every one. The earlier 80-configuration sweep was a
  strict subset and reached the same number.
- **Identity dispatch on trits 0..3, and a crushed trit 5.** Both are optional.
  Dropping them does not raise the ceiling but it is what makes a 15/16 spec
  buildable in ten chain ops.
- **ROT inside the walk.** Refuted from the VM's semantics (§5).
- **More walk depth as a cure for the hard lanes.** `K = 5, 7, 9` all fail the
  same lane; depth above the parity is free but does not touch the laws.
- **Chain searches that do not model cells.** The reason the prior record
  stalled; the fix is to require leg 2 to *open* with a CRAZY, not to end with
  one.

## 7. What I would try next, with more budget

The honest reading is that **this rung is now a wall, not a budget problem** —
inside this architecture. 15/16 is exact, the last lane is `0xa7`, and no
parameter of the family moves it. Getting the sixteenth case needs a different
shape, and there is exactly one candidate I would spend on:

1. **JMP into the table — a staircase of per-lane code lengths.** Everything
   above rests on one fact: every lane executes the same number of CRAZYs, so
   the trit-4 and trit-3 parities are shared. Break that and both laws
   dissolve. The VM's `4 => self.c = self.memory[self.d]` makes it possible.
   After the dispatch, cell `Q_W2` holds `A0(b)`; navigating `D` there and
   executing **JMP** instead of MOVD sets `c = A0(b)` and then `c++`, so lane
   `b` begins executing at its *own* table address while `d` stays at the
   lane-independent `Q_W2 + 1`. All lanes then run forward to one common
   `OUT`/`HALT`, so lane `b` executes `E − A0(b)` instructions: a CRAZY placed
   at an address *between* two lanes' entry points is executed by one and not
   the other. The sixteen addresses have all consecutive gaps ≥ 1, so **any
   monotone profile of CRAZY counts is realisable, and in particular any
   assignment of parities**. `H` and the trit-4/trit-3 laws all become per-lane.
   The costs to model: the operand at step `j` is cell `Q_W2+1+j`, shared as a
   sequence but aligned to each lane's own start, and the first `J − Q_W2` of
   those cells lie in the already-executed sled and are forced to their
   encrypted values. That is a real constraint, not a fatal one — push `Q_W2`
   toward 127 and the JMP as early as the chain allows, and the rest of the
   operand array is free. I estimate this as one solid session of work and it
   is the only thing on my list that can produce 16/16.
2. **If (1) fails: audit whether `0xa7` can be made non-dead by moving it, not
   by moving the walk.** `0xa7` is dead because its target `0xf6 = 246` sits
   too far from the other three trit-4-pinned targets for any reachable `h` to
   bring all four into one 81-wide window (the four span an arc of 101 > 81 on
   the 256-circle, and the same holds for the other pinned grouping, arc 107).
   That arc argument is what makes 15/16 exact, and it is independent of the
   table entirely — so it also tells you that no amount of walk engineering
   helps. Only per-lane `H` helps, which is again (1).

I would **not** spend anything on: dispatch geometries; window-overlap DPs
(NOP-spacing makes the lanes independent and collision-free patterns are
plentiful — 322 free gaps); larger walk depth; beam searches over `P` (the
per-lane DP is exact and cheap, so `P` should be enumerated, not searched);
or ROT anywhere in the walk.

## 8. Reproduce

```sh
cargo build --release
python3 research/map16-push/model.py         # reproduces the 80-config sweep, 15/16
python3 research/map16-push/spec.py 900      # full 262144-spec ceiling, still 15/16
python3 research/map16-push/chainfind2.py 15 900   # buildable spec + chain, 10 ops
python3 research/map16-push/build.py cand.mal 3 200
./target/release/malbolge-rungs verify --rung L2.FM3.xor51-map16 --program cand.mal
```

`research/map16-push/scan.py` is the first (failed) formulation, kept because
its failure is informative: extending a chain node by a single CRAZY can never
produce the trit pair `(1,1)`, so identity dispatch is unreachable that way and
every candidate it generates collides addresses. `research/map16-push/solve.py`
is the fast per-lane `(P, s)` search that established, empirically, that the
three trit-4 = 2 lanes never pass together under the uncorrected model.

## 9. Honest limits

- 15/16 is a **failing** verify. Nothing here claims a solve.
- The 15/16 ceiling is exact for the data-dispatch table architecture with a
  CRZ/NOP walk and a two-CRAZY dispatch. Longer dispatches (three or more
  CRAZYs) would enlarge the trit-map monoid, but only `id` and the transposition
  `(1,0,2)` are injective in it and neither is a new lever on trit 4; I did not
  sweep those specs exhaustively, so treat the ceiling as exact for two-CRAZY
  dispatch and very likely for longer ones.
- The JMP-staircase in §7 is designed and argued from the VM source, not built.
  It is a proposal, not a result.
