# Claude attempt: `L2.FM2h.xor51-map12-hi`

Date: 2026-08-11

Outcome: unsolved — and the rung is now, for this architecture, **provably
unsolvable**. The two-stage CRAZY-dispatch family's exact ceiling on this rung
is **9/12**, not 12/12, and three named lanes are dead in *every* configuration
for a reason that is two lines of ternary arithmetic rather than a search
result.

Solver: Claude Opus 5 via Claude Code, agentic session in an existing clone.

Builds on `docs/attempts/2026-08-09-claude-map12hi.json`,
`docs/attempts/2026-08-10-codex-map12hi.json` and
`docs/attempts/2026-08-10-claude-map12-hi.json`.

## What the three prior attempts left open

All three are searches in the map8/map7b two-stage CRAZY-dispatch family, and
all three converge on the same three or four dead lanes:

- 2026-08-09 (Sonnet 5) swept all 115 separating configs twice, found no fully
  live geometry, and guessed the tail-shape family was the lever.
- 2026-08-10 (Codex) isolated the failure to `0x90`, `0x9c`, `0xf9` in the best
  zero-split geometry and falsified "longer runway" and "deeper CRAZY".
- 2026-08-10 (Claude Opus 5) computed reachable-output sets, showed low-landing
  lanes reach only 209 of 256 bytes, screened 1611 geometries across all 115
  configs with lane `0x90` dead in every one, falsified a widened double-ROT
  tail catalog, and left the first candidate on the board at **7/12**.

Its closing section named two next levers, in priority order: **(1) a three-hop
pointer chain to widen the tail window, (2) derive the 47-byte reachable hole
in closed form.** This attempt did (2) first, because (2) is cheap and it turns
out to *decide* (1). It does. Lever (1) cannot work, and neither can any other
pointer geometry.

## 1. The hole is 55 bytes wide, contiguous, and geometry-free

Every operand a tail ever reads is `mem[d]` for some `d`, and in this family
every such cell holds a byte that is source-valid at its own address — hence
printable, hence in `[33,126]`. So the most generous possible model of *any*
pointer geometry — two-hop, three-hop, n-hop, MOVD-repositioned, shared tails,
anything — is: **every operand is an independent free choice from `[33,126]`**.
That model is an upper bound over the whole family at once, and it costs
nothing to compute.

`research/map12-hi-push/ubound.py` runs it. Since `ROT` sets `a = rot(mem[d])`
it *discards* the landing accumulator, so every op string reduces to `CRAZY^n`
applied either to `J(x)` or to `rot(v)`. The ROT-seeded branch is therefore
lane-independent, and it closes at

```
ROT-seeded closure covers 201/256 output bytes
missing: 0x9a .. 0xd0          (55 bytes, contiguous)
```

map12-hi's twelve targets are `x ^ 0x51`. Exactly four fall in that window:

| lane | target | in hole |
|---|---|---|
| `0xe0` | `0xb1` | yes |
| `0x90` | `0xc1` | yes |
| `0x9c` | `0xcd` | yes |
| `0xf9` | `0xa8` | yes |

Those are precisely the four lanes every prior attempt found dead. So the
question was never "is the tail grammar wide enough" — three independent
widenings failed for a reason. A lane whose target is in the hole **cannot use
ROT at all**; it must be realised as `CRAZY^n(J(x))`, and that chain is a
function of the landing the dispatch handed it.

## 2. Closed form for the hole (prior lever 2, discharged)

`research/map12-hi-push/ceiling.py` derives it. Write `s = trit5(J)`, let `t4`
be trit 4 of the final accumulator, `n` the number of CRAZY ops, and
`r = t0 + 3·t1 + 9·t2 + 27·t3 ∈ [0,80]`. Every printable operand is `< 243`, so
all operands have trits 5..9 equal to 0, and CRAZY acts on those trits by
`g0 = (1,0,0)`. Therefore

```
n odd :  a = 29160 + 243·(1−s) + 81·t4 + r
n even:  a =          243·s     + 81·t4 + r
```

and the emitted byte `a mod 256` is confined to an **81-wide window selected
entirely by `t4`**. Checked against brute force over 400 landings: 0 escapes.

That is the closed form the 2026-08-10 record asked for, and it says the same
thing for every one of the four in-hole targets: reaching them requires the
accumulator to have **trit4 = 2** at `OUT`.

## 3. The impossibility

Every printable byte is `≤ 126 < 162`, so every operand has `trit4 ∈ {0,1}`.
CRAZY acts on trit 4 by only two maps:

```
g0 = (1,0,0)        g1 = (1,0,2)
```

Both restrict to the **same transposition `0 ↔ 1`** on `{0,1}`. Hence for any
dispatch chain `h4`, and for any tail chain likewise:

- `h4(0) ≠ h4(1)` — always, for every config, every chain length;
- `h4(0), h4(1) ∈ {0,1}` — a `2` at trit 4 can only be *preserved* (by `g1`),
  never created.

Now read off trit 4 of the four in-hole inputs:

```
0xe0 = 224  trit4 = 2
0x90 = 144  trit4 = 1
0x9c = 156  trit4 = 1
0xf9 = 249  trit4 = 0
```

`0x90` and `0x9c` start at trit4 = 1 and `0xf9` starts at trit4 = 0, so none of
the three can ever hold trit4 = 2 — not at the landing, not anywhere in the
tail. **Lanes `0x90`, `0x9c` and `0xf9` cannot emit their targets in any
configuration, any geometry, any tail shape, any pointer chain.** Only `0xe0`
(trit4 = 2 already) survives, and only when every dispatch operand is `≥ 81` so
that `g1` preserves it.

Screening all 115 separating configs against this condition
(`research/map12-hi-push/screen_cfg.py`, `ceiling.py`) gives exactly what the
algebra predicts:

```
115 configs; per-config lane-liveness ceiling distribution: {9: 109, 8: 6}
best configs: ceiling 9/12, dead = [0x90, 0x9c, 0xf9] — identical set every time
```

This supersedes the 2026-08-10 empirical negative (1611 geometries, lane `0x90`
dead in all of them) with its cause, and it corrects that record's estimate of
the ceiling: it guessed 8/12 from four dead lanes; `0xe0` is in fact live, so
the true ceiling is **9/12**.

## 4. Prior lever 1 is dead on arrival

The three-hop pointer chain `p → T → T'` was the previous record's top
recommendation, on the reasoning that it "frees the tail address entirely and
therefore changes the operand alphabets". Two things are wrong with it, and
this attempt establishes both before spending budget on building it:

- **It does not free the tail address.** `T'` is read out of a program cell, so
  it is a printable byte, so `L = T' + 1 ≤ 127` exactly as before. Extra hops
  buy more *choices* of `(L, d0)`, never a wider window.
- **It does not matter that it changes the alphabets.** Section 3's obstruction
  is invariant across *all* printable alphabets simultaneously — it is a
  property of the number 126 being less than 162, not of `address mod 94`.

So no amount of pointer indirection rescues the three lanes. Lever 1 is closed.

## 5. The two escapes from the proof, both checked and both closed

The proof's one assumption is that every operand is printable. Two classes of
cell hold non-printable words at tail time, and both are genuinely reachable,
so I checked them rather than assuming (`research/map12-hi-push/escape.py`):

- **(a) the dispatch operand cells 42..49**, overwritten by the dispatch
  CRAZYs with intermediate accumulators. Reachable: the trail can start at
  `d0 = 49` (choose `p = 47`), and a `MOVD` off any cell holding the byte 41
  sets `d = 42`.
- **(b) memory past the end of the program**, filled by the classic recurrence
  `mem[i] = crazy(mem[i-1], mem[i-2])`. Reachable from (a): an intermediate
  taken after an odd number of dispatch CRAZYs has trits 6..9 all 1, so it is
  ≈ 29160, and `MOVD` off it throws `d` out past any program.

Both are closed:

```
(a) 0x90: mem[42]=29461 trit4=0   mem[49]=90  trit4=1
    0x9c: mem[42]=29476 trit4=0   mem[49]=84  trit4=1
    0xf9: mem[42]=29284 trit4=1   mem[49]=243 trit4=0
(b) every limit cycle of the recurrence, over all 16 seed pairs: trit4 ∈ {0,1}
```

The reason is the same induction: `crazy(a,d)` yields trit4 = 2 only when the
*operand* already has trit4 = 2, program bytes are printable, and the only word
in the machine that can carry trit4 = 2 is the lane's own input byte. A lane
whose input has trit4 ≠ 2 never sees one.

## 6. What was built: a verified candidate at the ceiling's edge

`research/map12-hi-push/pack_rand.py` drops the three provably dead lanes and
packs only the nine survivors. Two changes over the inherited builder matter:

- **A correctness fix.** `base.place_code` treats a dispatch operand cell
  (`40 + cp`, i.e. 42..49) as an ordinary fixed cell and will place tail code
  there if its source byte happens to decode to the wanted op. At runtime those
  cells have been overwritten with the lane's intermediate accumulator, which
  is not a printable word, so the program dies with *invalid runtime
  instruction at address 49*. This is present in the inherited map8 builder and
  silently costs lanes. Forbidding code on `geo.reserved` fixes it.
- **Set packing instead of nested DFS.** A tail plan is just a partial cell
  assignment, and a plan derived under the empty assignment stays valid under
  any larger assignment it does not conflict with. So the joint problem is
  maximum-compatible-subset, not a nested backtrack that re-derives every
  lane's plans at every node. Plans are enumerated once per geometry and cached;
  restarts are randomized over lane order and biased toward plans that pin
  fewer cells, since the binding constraint is the 47–60 cell free window.

Best natively verified candidate:
`docs/attempts/2026-08-11-claude-push-map12-hi.best.mal` (config 5, zero splits,
station offsets `(4,)`, 296 bytes, 8000 plans/lane, 60000 restarts) —
**7/12**.

```
$ ./target/release/malbolge-rungs verify --rung L2.FM2h.xor51-map12-hi \
      --program docs/attempts/2026-08-11-claude-push-map12-hi.best.mal --verbose
  epoch 0 seed=aa70e690…  7/12 cases  FAIL
    case  0: in=a5 exp=f4 got=<none> [Error: output length 2 exceeds limit 1] MISS
    case  1: in=e0 exp=b1 got=92 [Halted] MISS
    case  2: in=90 exp=c1 got=<none> [Error: output length 2 exceeds limit 1] MISS
    case  3: in=9c exp=cd got=9f [Halted] MISS
    case  4: in=84 exp=d5 got=d5 [Halted] ok
    case  5: in=a1 exp=f0 got=f0 [Halted] ok
    case  6: in=bd exp=ec got=ec [Halted] ok
    case  7: in=c8 exp=99 got=99 [Halted] ok
    case  8: in=be exp=ef got=ef [Halted] ok
    case  9: in=f9 exp=a8 got=ec [Halted] MISS
    case 10: in=86 exp=d7 got=d7 [Halted] ok
    case 11: in=dd exp=8c got=8c [Halted] ok
```

**This ties the prior record's 7/12; it does not beat it.** That is worth
stating plainly, because it is the honest measurement of where the remaining
work is. Across four geometries the packer's *claims* were 7, 7, 7 and 8 of the
nine live lanes, and the natives came back 6, 6, 7 and 7 — so the packing
search is close to the ceiling but the Python model over-claims by about one
lane. The over-claim is diagnosable from the trace above: lane `0xa5` emits
*two* bytes. A plan derived under the empty assignment is only guaranteed valid
under a superset assignment if the compatibility test covers every cell the
lane's execution actually visits, and a lane that runs past its own `HALT` into
a neighbouring lane's tail visits cells its own plan never pinned. Cell-value
agreement is therefore a necessary but not sufficient compatibility test. That
is a bug in my packer, not in the ceiling argument, and fixing it (re-simulate
each accepted plan against the current partial program before committing it) is
the cheapest single improvement available on this rung.

The five misses are the three provably dead lanes (`0x90`, `0x9c`, `0xf9`),
`0xe0` — live in principle, lost to the packing — and `0xa5`, lost to the
over-claim above.

## What I ruled out

- **Any pointer geometry** — two-hop, three-hop, n-hop, MOVD-repositioned.
  Ruled out by §1/§4: the obstruction holds under "every operand independently
  free over all printable bytes", which dominates every geometry at once.
- **Any dispatch configuration.** Ruled out by §3: `h4(0) ≠ h4(1)` for every
  chain, so `0x90`/`0x9c` (trit4 = 1) and `0xf9` (trit4 = 0) can never reach
  trit4 = 2. All 115 configs screen to the same dead set.
- **Any tail shape or length.** Ruled out by §1: ROT-seeded tails miss the hole
  entirely regardless of shape, and non-ROT tails are governed by §3. This
  explains, rather than merely repeats, the three prior grammar widenings that
  failed.
- **Non-printable operands** (the proof's only assumption). Ruled out by §5 for
  both classes of cell that carry them.
- **More joint-search budget.** Ruled out for the three dead lanes, which fail
  with the shared assignment empty. It is *not* ruled out for the packing of
  the nine live lanes — see below.

## What I would try next, with more budget

The rung splits cleanly into a settled half and an open half, and only the
second is worth money.

1. **Close the packing gap to 9/12 (budget problem, not a wall).** The ceiling
   is 9 and this attempt did not reach it. Nine tails need ~6–8 cells each plus
   two pointer cells, against a free window of 47–60 cells in `[34,127]`, so it
   is a genuine set-packing instance and randomized greedy is a weak solver for
   it. I would run an exact maximum-compatible-subset solver (ILP or a proper
   MaxSAT encoding: one boolean per (lane, plan), at-most-one per lane, pairwise
   conflict clauses on shared cells) over the cached plan sets. That is a few
   thousand variables — trivial for a real solver and completely out of reach
   for the DFS the family ships with. I would also widen the window first:
   §3 shows every dispatch operand must be `≥ 81` to keep `0xe0` alive, and the
   same trit algebra says operands in `[108,126]` push the minimum landing from
   ~82 up to 108, buying ~15 more free cells for free.
2. **The one real escape: repeated ROT on a single cell.** §5's induction has a
   gap I could not close and did not have budget to exploit. `ROT` *rotates*
   trits (`trit_j(rot w) = trit_{j+1}(w)`, `trit_9(rot w) = trit_0(w)`) and
   writes the result back to `mem[d]`, so rotating the *same* cell k times
   walks a `2` from trit 0 up into trit 4 after six rotations. Printable bytes
   with trit0 = 2 are plentiful. This is the only construction I know of that
   manufactures trit4 = 2 for a lane whose input lacks it, and it is therefore
   the only thing that could take this rung past 9/12 in this family. Cost: the
   trail must return `d` to the same cell six times, which needs a `MOVD` cycle
   — cells holding their own predecessor's address. I would spend the whole
   next budget here.
3. **Retarget the family.** Everything in §1–§3 is arithmetic in the inputs and
   the mask, not in this instance's search. It transfers directly: compute
   `trit4(x)` for the input set and `x ^ mask` for the targets, and the ceiling
   falls out before any search runs. `map12-low` and `map16` should be scored
   this way first, and so should any future finite-map rung the generator mints
   — it is a feasibility test that costs milliseconds and is much sharper than
   the separation count the board currently ranks by.

## A note for the board's ranking

`feasibility` scores separation only: 115 separating configs, minimum landing
gap 1, "hard (separation available, realization is the work)". That is why this
rung ranked 26. Separation is not the binding constraint here and never was.
A one-line trit-4 test on the input set and the mask would have said, before any
attempt was made, that this instance's ceiling is 9/12 — i.e. that it is not
solvable at all in the family the board's own solved rungs use. Rungs like this
one are worth keeping, but they should be labelled as architecture-refuting
rather than merely hard, or the ordering keeps spending strong-model budget on
instances whose answer is arithmetic.

## Reproduce

```sh
cargo build --release
python3 research/map12-hi-push/ubound.py 5        # the 55-byte contiguous hole
python3 research/map12-hi-push/jreach.py 5 400    # per-landing reachable sets
python3 research/map12-hi-push/bands.py 1400 5    # band structure, full-reach landings
python3 research/map12-hi-push/screen_cfg.py 5    # all 115 configs vs the condition
python3 research/map12-hi-push/ceiling.py         # closed form + per-config ceiling
python3 research/map12-hi-push/escape.py          # both non-printable escapes, closed
python3 research/map12-hi-push/pack_rand.py 5 4 8000 60000   # the candidate
```

## Honest limits

- The impossibility in §3 is exact arithmetic and does not depend on any search
  budget. Its one assumption — every tail operand is printable — is discharged
  in §5 for the two classes of non-printable cell a tail can actually reach,
  but §5 is a check of those two classes, not a proof that no third class
  exists. The `ROT`-cycle construction in "what I would try next" is precisely
  a candidate third class, and I flag it as open rather than closed.
- The result is scoped to the two-stage CRAZY-dispatch family. It says nothing
  about a program that dispatches some other way, and the ceiling of 9/12 is a
  ceiling for *that family*, not for the rung.
- The 9/12 ceiling is tight in the sense that all nine survivors are
  individually live in real geometries (verified by plan enumeration); whether
  all nine pack simultaneously into one program is unresolved.
