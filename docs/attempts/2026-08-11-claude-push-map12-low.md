# Claude attempt: `L2.FM2l.xor51-map12-low` — **solved, 12/12**

Date: 2026-08-11

Outcome: **solved.** `verify` exits 0 at 12/12 on the native evaluator.

Program: [`solutions/map12-low/map12-low-spaced-walk.mal`](../../solutions/map12-low/map12-low-spaced-walk.mal)
(also copied to `docs/attempts/2026-08-11-claude-push-map12-low.best.mal`) —
1512 bytes, 1099 steps, well inside the 4096-byte / 2048-step limits.

Solver: Claude Opus 5 via Claude Code, autonomous single-session run under a
hard cap of 700k tokens / 100 minutes, as part of a board-calibration survey.

Builds on [`docs/attempts/2026-08-10-claude-map12-low.json`](2026-08-10-claude-map12-low.json)
(architecture, algebra, and the 10/12 candidate this supersedes) and
[`docs/attempts/2026-08-11-claude-push-map12-hi.json`](2026-08-11-claude-push-map12-hi.json)
(the trit-4 argument, which turns out to govern this rung's *walk depth*).

## Summary

The prior record on this rung closed with a numbered list of what to try next.
Item 2 was:

> **Break the window overlap.** The `K` CRAZYs need not be consecutive: NOPs
> between them make lane `b` read cells at offsets `O` inside a longer span, the
> same `O` for every lane. […] This is the first thing I would run with real
> budget, and it is cheap.

It is cheap, and it is the whole rung. Spacing the walk with NOPs, plus one
freedom that record did not name, takes the architecture from the 10/12 it was
stuck at to 12/12 on the first program built. No new architecture, no dispatch
search, no solver.

## 1. The two freedoms

The architecture is unchanged from `cov48` → `map12-low`:

```
IN                      A = b
CRZ W1, CRZ W2          A = b + K0     (K0 a multiple of 81), parked in Q_W2
MOVD on Q_W2            D = b + K0 + 1
NOP^s                   D = base + b            base = K0 + 1 + s      <-- NEW
CRZ/NOP pattern P       A = crazy^K(b+K0, mem[base+b+p_1], …)          <-- NEW
OUT, HALT               out = A mod 256
```

**Freedom A — the walk pattern `P`.** `NOP` advances `D` (and `C`) by one
without touching the accumulator, so a `CRZ NOP…NOP CRZ` string makes lane `b`
read cells `base + b + p_i` for an arbitrary increasing `P = (0 = p_1 < … < p_K)`.
Two lanes share a cell iff their input difference lies in `P − P`. The twelve
inputs have 40 distinct pairwise differences, the largest 51, so the gaps that
never collide are

```
allowed gaps < 80: 10, 15, 19, 20, 25, 28, 38, 41, 44, 49, 50, 52..79
                   (and every gap >= 52 is safe by construction)
```

A pattern whose pairwise differences all avoid that difference set makes the
twelve lanes **cell-disjoint**, and the joint transfer-matrix problem the prior
record proved UNSAT over all 83 live configurations simply ceases to exist:
twelve independent problems, each with 8 free bytes per cell.

**Freedom B — the phase shift `s`.** This one is not in the prior record. The
eight source-valid bytes at an address depend only on `address mod 94`. With the
walk starting immediately after the `MOVD`, the table base is pinned to
`(K0 + 1) mod 94`, and `K0` is already spoken for — it fixes the frozen high
part `H` and the starting trit 4. Inserting `s` NOPs between the `MOVD` and the
first `CRZ` moves the base to **any** residue mod 94 at a cost of `s` NOPs and
nothing else. That decouples "which constant the dispatch adds" from "which byte
alphabet the table gets", which were previously the same choice.

`research/map12-low-push/lowmodel.py` is the shared model; `search2.py`
enumerates collision-free patterns and scans residues.

## 2. Walk depth parity is the binding constraint, not window overlap

With the lanes decoupled, per-lane liveness is the only thing left, and it is
governed by the algebra the prior two records established. Every table operand
is a printable byte, so its trits 5..9 are 0, so those trits of the accumulator
are a function of `K0` and the **parity of `K`** alone:

```
H = 243 * hi_final,   hi_final trit j = (min(trit_j(K0/243), 1) + K) mod 2
out = (H + Lstar) mod 256,   Lstar in [0,242] = 81*t4 + r
```

`research/map12-low-push/explore.py` enumerates all 32 reachable `H`: 20 leave
every lane's `Lstar` in range. `stage2.py` then intersects that with what is
actually *buildable* — `K0 = 243*hi_src + 81*start_t4` must be large enough to
hold the code and small enough to fit the file — leaving twelve
`(K0, K-parity)` configurations, all with `start_t4 = 2`.

Parity then decides everything:

| K | H | lanes needing final trit4 = 2 | outcome |
|---|---|---|---|
| 4, 6 (even) | 729 or 972 | `0x2a`, `0x2f` | **dead** |
| 3, 5 (odd) | 28431 or 28674 | none | live |

This is the *same* obstruction that makes `map12-hi` unsolvable, met from the
other side. Trit 4 of the accumulator starts at 2 (because `K0/81 ≡ 2 mod 3`),
and CRAZY preserves a 2 there only when the operand's trit 4 is 1, i.e. only
when the operand byte is `>= 81` — of the eight legal bytes at an address only
3 to 5 qualify (`parity.py`). A lane that needs `t4 = 2` must therefore take
*every* operand from that residual half-alphabet and still hit an exact 4-trit
remainder, and measured over 2000 free residue sequences per lane it never does:

```
K=4 K0=2106 H=972   0x2a t4=2 rate 0.000    0x2f t4=2 rate 0.000
                    all ten other lanes     rate 0.89 .. 0.99
K=6 K0=2106 H=972   identical
K=5 K0=2106 H=28431 no lane needs t4=2; every lane 0.83 .. 1.00
```

On `map12-hi` the dead lanes' inputs carried the wrong trit 4 and nothing could
be done. Here the lane inputs are fine and it is the *target* that demanded a 2,
so moving `H` by flipping the walk depth's parity removes the demand outright.
**`K` odd is the rung's real requirement**, and it costs nothing.

## 3. How wide the solution set is

A single hit could be luck, so `research/map12-low-push/census.py` samples
(pattern, base residue) pairs uniformly for each buildable offset and depth:

```
K   K0     patterns  sampled  solve%   min span solving
3   1863   2076      1500      0.27    108
3   2106   2076      1500      0.20    109
4   *      11417     1500      0.00    -        (parity: 0x2a, 0x2f dead)
5   891    19368     1500     56.20     80
5   1134   19368     1500     43.00     79
5   1377   19368     1500     45.40     88
5   1620   19368     1500     56.13     79
5   1863   19368     1500     44.07     83
5   2106   19368     1500     46.60     84
6   *      10649     1500      0.00     -        (parity)
```

At `K = 5` roughly **half of all collision-free patterns solve all twelve
lanes**, at every buildable offset. `K = 3` works but only barely (the reachable
set after three CRAZYs is too small), and even depths are dead for the reason
above. This is not a needle: once the lanes are decoupled and the depth parity
is right, the rung is comfortably inside the family.

## 4. Layout — the one thing that actually needed care

`C` and `D` advance in lockstep, so the walk's spacing NOPs are code cells that
march forward at exactly the same rate as the table walk. The code must finish
before the first table cell:

```
movd_end + span + 2  <  K0 + 9         (the phase shift s cancels)
```

With 16 `MOVD` walks the code ends at 1022, so `K0 >= 1134` is required at
`span = 74`. Two further constraints picked the final configuration:

- **`chain.c` has a trap.** It searches for the constant pair `(W1, W2)` but
  does not require the two legs to end on *different* cells. `W1` has to survive
  until after `IN`, and its printed shortest chains for `K0 = 1134`, `1620` and
  `1863` all end leg 2 by rotating the very cell leg 1 left `W1` in — following
  them literally destroys `W1` before it is used. `K0 = 1377` and `K0 = 2106`
  are the two offsets in range whose printed chains end the legs on distinct
  cells; `1377` is the smaller and is what shipped.
- **`minimize.py`** then picks the `(s, span)` pair minimising the file, since
  program length is `K0 + 1 + s + 59 + span + 1`. `s = 0` (base residue 62) with
  `P = [0, 10, 20, 64, 74]` solves, giving 1512 bytes.

## 5. The result

```
$ ./target/release/malbolge-rungs verify --rung L2.FM2l.xor51-map12-low \
      --program solutions/map12-low/map12-low-spaced-walk.mal --verbose
  epoch 0 seed=fa5cb378…  12/12 cases  PASS
    case  0: in=08 exp=59 got=59 [Halted] ok
    case  1: in=37 exp=66 got=66 [Halted] ok
    case  2: in=35 exp=64 got=64 [Halted] ok
    case  3: in=1a exp=4b got=4b [Halted] ok
    case  4: in=2a exp=7b got=7b [Halted] ok
    case  5: in=32 exp=63 got=63 [Halted] ok
    case  6: in=38 exp=69 got=69 [Halted] ok
    case  7: in=2f exp=7e got=7e [Halted] ok
    case  8: in=0d exp=5c got=5c [Halted] ok
    case  9: in=18 exp=49 got=49 [Halted] ok
    case 10: in=3b exp=6a got=6a [Halted] ok
    case 11: in=14 exp=45 got=45 [Halted] ok
RESULT: PASS (native evaluator)
```

Configuration: `K0 = 1377`, `K = 5`, `P = [0, 10, 20, 64, 74]`, base residue 62
(`s = 0`), `H = 28431`, prefix 128, code ends at 1099, table at 1386..1512.

The two cases the prior 10/12 candidate missed, `0x35` and `0x38`, were the two
whose consecutive windows overlapped their neighbours' the most. Under
`P = [0, 10, 20, 64, 74]` no lane touches another's cells at all.

## What this rung was, in the end

`feasibility` calls it a wall — "dispatch family cannot separate this input
set", 0 of 143808 configurations — and that is true and was correct to act on.
But the rung was never hard for the *table* architecture; it was hard for one
gratuitously constrained corner of it. The prior attempt read the correct
architecture, derived the correct algebra, built a correct program, and then hit
a ceiling created by a modelling choice it had already flagged as arbitrary
(consecutive cells). The distance from 10/12 to 12/12 was two NOP-insertion
patterns and about forty minutes.

## What I ruled out

- **The dispatch family.** Not searched, on the board's own feasibility report
  (0 separating configs of 143808), exactly as the prior attempt argued.
- **Even walk depths.** `K = 4` and `K = 6` are dead at every buildable offset,
  and not for lack of search: they force `H ∈ {729, 972}`, which demands final
  trit4 = 2 on lanes `0x2a` and `0x2f`, and those two lanes measure 0.000 over
  2000 free residue sequences each while every other lane measures 0.89+.
- **Consecutive-cell walks.** Nothing here contradicts the prior record's exact
  UNSAT DP; it is confirmed and simply escaped rather than refuted. Its scope
  was consecutive cells with `K <= 8`, which is a measure-zero corner of the
  pattern space.
- **`chain.c`'s shortest chains at `K0` = 1134 / 1620 / 1863** — unusable as
  printed, both legs end on the same cell.
- **Needing a solver.** The final search is 200 lines of Python with bitset
  reachability over 243 states; no SAT, no ILP, no DP over shared state.

## Budget and what I would do with more

Spent roughly 190k of a 700k token cap and about 55 of 100 minutes. The rung
solved on the first program built from the spaced-walk model, so nothing here
was budget-limited. With the remainder I would:

1. **Retarget the same two freedoms at `L2.FM3.xor51-map16` (rank 25).** That
   record reports a `15/16` ceiling for "the data-dispatch table architecture
   with a CRZ/NOP walk", proved by a trit-4 forcing law over all 80 realisable
   configurations, with `0xa7` dead in every one. Its 80 configurations are
   `K0`-and-depth configurations; the phase shift `s` is a 94-fold widening of
   that set that the ceiling argument does not cover, and this rung shows the
   walk-depth *parity* moves `H` and can retire a trit-4 demand outright. Both
   deserve to be checked against that ceiling before it is treated as settled.
   This is the single highest-value follow-up and it is cheap.
2. **Shrink the program.** 1512 bytes is dominated by `K0 = 1377`, which is
   dominated by the 16 `MOVD` walks (~890 cells) needed to build two constants.
   Each walk costs `(r_q − d) mod 94` because `xval` is a bijection on residues,
   so choosing the constant cells jointly with the visit order — the prior
   record's item 1, still unspent — should cut the code by a large factor and
   let `K0 = 891` or lower become buildable. A ~700-byte program looks reachable.
3. **Fix `chain.c`** to require the two legs to end on distinct cells, and to
   cost chains by actual `MOVD` walk length rather than op count. Both bugs cost
   real offsets on this rung and will cost them on every future finite-map rung.

## Reproduce

```sh
cargo build --release
python3 research/map12-low-push/explore.py              # allowed gaps; the 20 live H
MLP_FLOOR=700 python3 research/map12-low-push/stage2.py # buildable configurations
python3 research/map12-low-push/search2.py 5 140 700    # 12/12 patterns, all offsets
python3 research/map12-low-push/parity.py 2000          # why even depths die
python3 research/map12-low-push/census.py 1500 140      # how wide the solution set is
python3 research/map12-low-push/minimize.py 1377 74 12  # smallest (s, span)
python3 research/map12-low-push/build_spaced.py cand.mal 1377 62 0,10,20,64,74
./target/release/malbolge-rungs verify --rung L2.FM2l.xor51-map12-low --program cand.mal --verbose
```

## Honest limits

- The solve is a solve: `verify` exits 0 at 12/12, and this rung's inputs are
  fixed in the registry, so one epoch is definitive.
- The census percentages are sampled (1500 draws per cell), not exhaustive. The
  12/12 configurations they report are individually exact — each is a full
  reachability check over all twelve lanes — but "≈46% of patterns solve" is a
  measurement, not a theorem.
- The even-depth negative is measured the same way: 2000 free residue sequences
  per lane, zero hits on the two `t4 = 2` lanes. The *reason* (a `t4 = 2` lane
  must draw every operand from the `>= 81` half of its alphabet) is exact
  arithmetic, but I did not prove the residual alphabet can never hit the
  remainder, only that it did not in 2000 tries per lane at three offsets.
- The layout inequality `movd_end + span + 2 < K0 + 9` is checked by assertion
  in the builder for the shipped configuration, not proved in general.
