# Claude attempt: `L2.FM2l.xor51-map12-low`

Date: 2026-08-10

Outcome: unsolved — best verified candidate **10/12** on the native evaluator.

Solver: Claude Opus 5 via Claude Code, autonomous single-session run under a
hard cap of 200k tokens / 30 minutes.

Program: [`docs/attempts/2026-08-10-claude-map12-low.best.mal`](2026-08-10-claude-map12-low.best.mal)
(2171 bytes, 858 steps).

Builds on [`docs/attempts/2026-08-10-claude-cov48.json`](2026-08-10-claude-cov48.json)
(architecture) and [`docs/attempts/2026-08-10-claude-map12-hi.json`](2026-08-10-claude-map12-hi.json)
(what not to spend budget on).

## The opening move: do not use the dispatch family at all

`feasibility --rung L2.FM2l.xor51-map12-low` says it plainly:

```
dispatch configs enumerated: 143808
separating configs:          0
difficulty class:            wall (dispatch family cannot separate this input set)
```

Every prior finite-map attempt on the board — map8's solve, both map12-hi
attempts — is inside the two-stage CRAZY-dispatch family, where the input is
turned into a jump and each input gets a private tail. On this rung that
family is dead before it starts: no configuration separates these twelve
low-range inputs. That is the whole point of the rung ("inputs whose natural
landings collide with prefix and dispatch data").

So this attempt does not search dispatch geometries. It takes the **coverage
rungs' table architecture** (cov40 → cov48, `docs/attempts/2026-08-10-claude-cov48.md`)
and re-aims it at a finite map, which as far as the recorded attempts go has
not been tried on a finite-map rung:

```
IN                      A = b
CRZ W1, CRZ W2          A = b + K0, parked in a cell
MOVD on that cell       D = b + K0 + 1        <- the input IS the index
CRZ x K                 A = crazy^K(b + K0, mem[b+K0+1 .. b+K0+K])
OUT, HALT               out = A mod 256
```

There is no lane, no landing and no separation requirement: control flow is
identical for all twelve inputs, and the input only moves the *data* pointer.
A rung that walls the dispatch family says nothing about this one.

## The finite-map dividend: K0 may be a multiple of 81, not 729

cov48 derived that `K0` must be a multiple of 729. That derivation is a
coverage-rung derivation: all 256 inputs must index distinct table entries, so
`M[w2] ∘ M[w1]` must be the identity on trits 0..5, and `M1 = (1,0,2)` is the
only injective crazy row, so `w1 = w2 = 1` there and the offset can only touch
trits 6..9.

This rung's twelve inputs are all `< 0x40 = 64 < 81`. Only **trits 0..3** carry
information; trits 4..9 of every input are 0, and `M[w2][M[w1][0]]` can be made
0, 1 or 2. So the dispatch can realise `A = b + K0` for any `K0` that is a
multiple of **81** — 50 offsets instead of 5.

`research/map12-low/chain.c` (cov48's `chain2.c` with that candidate set and a
12-input `good()`, plus a fix so the search rejects pairs that spend the same
seed cell twice) finds buildable `(W1, W2)` pairs for those offsets, e.g.

```
K0=2106  W1=29524 (cell 45)  W2=28390 (cell 44)   9 ops   seed reuse: none
```

## Why the offset matters: the high trits are frozen

Every table operand is a printable byte, so its trits 5..9 are 0, and
`crazy_trit(t, 0) = (1, 0, 0)` for `t = 0, 1, 2`. Trits 5..9 of the accumulator
therefore never see the table: after `K` layers their value is a function of
`K0` and the **parity of K** alone. Every rung input is `< 243`, so those trits
come from `K0` for all twelve lanes identically. Writing `H` for that frozen
high part and `L ∈ [0, 242]` for the low five trits:

```
out = (H + L) mod 256        L*_b = (target_b - H) mod 256
```

Each lane needs one exact low value, and the lane is **dead outright when
L*_b > 242** — no table can fix it. That single relation explains why the
proven cov48 configuration is hopeless here: at `K0 = 2916` the only two
reachable `H` are 2916 (`K` even) and 26487 (`K` odd), and

```
K0=2916 K even: 08, 32, 0d out of range  -> ceiling 9/12, measured 6/12 live
K0=2916 K odd : 3b out of range          -> measured 0/12 live
```

Widening `K0` to multiples of 81 widens the reachable `H` from 10 values to 32
(any subset of `{243, 729, 2187, 6561, 19683}`), and 83 of the swept `(K0, K)`
pairs put all twelve `L*` in range **and** reachable per-lane
(`research/map12-low/sweep.c`). The rung's targets are all in `0x45..0x7e`,
which is why an `H` with `H mod 256 = 232` (i.e. `L* ∈ 93..150`) makes every
lane individually live.

## What actually blocks 12/12: window overlap, not lane liveness

Lane `b` consumes the `K` table cells `b+K0+1 .. b+K0+K`, and each address
admits exactly 8 loader-valid bytes. Inputs closer than `K` apart share cells:
`0x37/0x38` differ by 1, and `0x35, 0x37, 0x38, 0x3b` form one cluster. So the
table is a transfer-matrix problem, state = the last `K-1` byte choices.

`research/map12-low/solve.c` runs that DP exactly. Over **all 83 (K0, K)
configurations that are 12/12 live per-lane, with K ≤ 8**, the joint DP is
UNSAT in every one. The first cell where it dies is always inside the
`0x35..0x3b` cluster or at `0x1a`:

```
K0= 324 K=4  UNSAT at addr 354   (window of 0x1a)
K0= 405 K=4  UNSAT at addr 465   (window of 0x38)
K0= 567 K=4  UNSAT at addr 627   (window of 0x38)
K0=1134 K=5  UNSAT at addr 1192  (window of 0x35)
...  0 SAT out of 83
```

Per-lane liveness is necessary and cheap; the binding constraint is that four
inputs within a span of six share almost all of their operands and each needs
an exact 5-trit value.

## The candidate: max-count table, 10/12 natively

`research/map12-low/maxtable.c` is the same DP maximising satisfied lanes
instead of demanding all twelve. Best counts found:

```
11/12  K0=567 K=4 | K0=405 K=4 | K0=405 K=5
10/12  K0=2106 K=4/5 | K0=1620 K=5 | K0=1134 K=5 | K0=324 K=4 | K0=243 K=5
```

The 11/12 offsets are **not buildable**: the table would start at address 414
(K0=405) or 576 (K0=567), and the program's own code needs ~700 cells after
the NOP prefix, because each MOVD has to wait for `D` to walk to a prefix cell
whose enciphered value is the pointer it wants. The code collides with the
table. `K0 = 2106` is the largest-count offset with both a reuse-free operand
chain and room for the code, so that is what was built.

```
$ ./target/release/malbolge-rungs verify --rung L2.FM2l.xor51-map12-low \
      --program docs/attempts/2026-08-10-claude-map12-low.best.mal --verbose
  epoch 0 seed=fa5cb378…  10/12 cases  FAIL
    case  0: in=08 exp=59 got=59 [Halted] ok
    case  1: in=37 exp=66 got=66 [Halted] ok
    case  2: in=35 exp=64 got=68 [Halted] MISS
    case  3: in=1a exp=4b got=4b [Halted] ok
    case  4: in=2a exp=7b got=7b [Halted] ok
    case  5: in=32 exp=63 got=63 [Halted] ok
    case  6: in=38 exp=69 got=1e [Halted] MISS
    case  7: in=2f exp=7e got=7e [Halted] ok
    case  8: in=0d exp=5c got=5c [Halted] ok
    case  9: in=18 exp=49 got=49 [Halted] ok
    case 10: in=3b exp=6a got=6a [Halted] ok
    case 11: in=14 exp=45 got=45 [Halted] ok
```

The two misses are exactly the two the DP predicted (`0x35`, `0x38`, both in the
crowded cluster); the model and the native VM agree case for case. 2171 bytes,
858 steps, well inside the 4096/2048 limits.

## What I ruled out

- **The dispatch family.** Not by search — the board's own feasibility tool
  reports 0 separating configs of 143808. Any attempt that opens by screening
  dispatch geometries here is screening an empty set.
- **cov48's proven configuration reused as-is.** `K0 = 2916` caps at 9/12 by
  the frozen-high-part relation before any table is chosen, and measures 6/12.
  The offset generalisation is what unlocks the double-digit score.
- **Per-lane liveness as the obstruction.** 83 configurations have all twelve
  lanes individually live. Unlike map12-hi, where the wall is a lane that
  cannot emit its byte at all, here every lane can — they just cannot all do it
  from the same table.
- **Joint search budget on those 83 configurations.** The DP is exact, not
  heuristic: UNSAT is UNSAT, no node budget involved.
- **The 11/12 offsets.** Real but unbuildable at the current code density; the
  blocker is MOVD-padding length, not the table.

## What I would try next, with more budget

In priority order:

1. **Shrink the code so `K0 = 405/567` becomes buildable — worth +1 lane
   immediately.** The 698 cells of code are almost entirely MOVD padding: each
   `movd(q)` walks `D` through the prefix until it finds a cell whose
   enciphered value is `q-1`. Choosing the constant cells `q` jointly with the
   walk order (a small TSP over the ~94-cell landing window) instead of
   accepting whatever `chain.c` returns should cut that by a large factor. This
   is a layout problem with a known target and no structural obstruction.
2. **Break the window overlap.** The `K` CRAZYs need not be consecutive: NOPs
   between them make lane `b` read cells at offsets `O` inside a longer span,
   the same `O` for every lane. Collisions then occur only when an input
   difference lies in `O - O`, so choosing `O` as a Sidon-ish set against the
   twelve pairwise differences directly attacks what the DP says is the binding
   constraint. This is the first thing I would run with real budget, and it is
   cheap: the DP generalises to a pattern with state = last `span-1` choices.
3. **Deeper tables at large `K0`.** `K = 6, 7` at `K0 ≈ 2100` never finished
   inside the cap (the DP recomputes each window chain per transition; caching
   the partial accumulator per state makes it linear). Depth was non-monotone
   on cov48 (`k=5` scored 47, `k=6` scored 71), so this is not a small lever.
4. **A second constant CRAZY after the table walk**, reached by making the
   cell at `b+K0+K+1` a MOVD pointer into the `[34,127]` landing window. That
   adds a per-lane-selectable global correction and, unlike everything above,
   can change the frozen high part `H` independently of `K0` — the one degree
   of freedom this architecture currently spends `K0` on.

I would not spend budget on dispatch geometries, on per-lane screens, or on
more joint-search effort in the 83 already-refuted configurations.

## Reproduce

```sh
cargo build --release
cc -O2 -o /tmp/sw research/map12-low/sweep.c && /tmp/sw 2 20     # live lanes per (K0,K)
cc -O2 -o /tmp/ml research/map12-low/solve.c && /tmp/ml 405 4    # exact joint DP -> UNSAT
cc -O2 -o /tmp/mt research/map12-low/maxtable.c && /tmp/mt 2106 5  # max-count -> 10/12
cc -O2 -o /tmp/ch research/map12-low/chain.c  && /tmp/ch 2106    # operand pair + chain
python3 research/map12-low/build.py cand.mal /tmp/mt
./target/release/malbolge-rungs verify --rung L2.FM2l.xor51-map12-low --program cand.mal --verbose
```

## Honest limits of the negative result

- The 83-configuration UNSAT sweep covers `K ≤ 8` and consecutive-cell walks
  only. Item 2 above (NOP-spaced walks) is a strictly larger space that was not
  searched at all, so "the table architecture cannot reach 12/12" is **not**
  claimed. What is claimed is narrower and exact: with `K` consecutive CRAZYs
  and `K ≤ 8`, no offset in `81..4000` admits a table satisfying all twelve.
- The per-lane liveness sweep (`sweep.c`) models the low five trits only; it is
  validated against the full-word computation in `solve.c`, which is what every
  reported SAT/UNSAT and count comes from.
- Everything here is scoped to the data-dispatch table architecture. It says
  nothing about the two-stage dispatch family beyond what the board's own
  feasibility tool already reports.
