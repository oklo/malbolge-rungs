# Claude attempt: `L2.FM2h.xor51-map12-hi`

Date: 2026-08-10

Outcome: unsolved — best verified candidate **7/12** on the native evaluator.

Solver: Claude Opus 5 via Claude Code, agentic session in a fresh clone.

Builds on `docs/attempts/2026-08-09-claude-map12hi.json` and
`docs/attempts/2026-08-10-codex-map12hi.json`.

## What the two prior attempts left open

Both prior records are searches for a *joint* assignment in the two-stage
CRAZY-dispatch family, and both report the same shape of failure: some lane
has no individually routable tail, so the joint stage is never reached.

- 2026-08-09 (Claude Sonnet 5) swept all 115 separating configs twice, with
  per-lane node budgets up to 300k, and found no fully-live geometry. Its
  stated open question was whether this was a budget problem or a real wall,
  and it guessed the next lever was the *tail-shape family*.
- 2026-08-10 (Codex) drilled into config 0, found 9/12 lanes live under a 30k
  existence probe, and showed that longer NOP runways (to 20), deeper CRAZY
  chains (to 8), and brute-forced tail bodies over `{MOVD, ROT, CRAZY}` up to
  length 5 all fail to rescue `0x90`, `0x9c`, `0xf9`.

Neither produced a candidate program, so neither left a verified number
behind. This attempt does two things they did not: it replaces the yes/no
existence probe with a **reachable-output computation**, and it builds a
**maximal partial program** so the rung carries a native score.

## 1. The tail-placement window is fixed by the encoding, not by the search

A lane's second-stage jump reads `p = mem[q]` (`q = m + 49 - J(x)`) and then
`T = mem[p+1]`; the tail body starts at `L = T + 1` and its operand trail at
`d0 = p + 2`. Both `p` and `T` are *source-valid bytes of the cells they sit
in*, and source-valid bytes are printable. Therefore, unconditionally:

```
every lane's tail body starts in [34, 127]
every lane's operand trail starts in [35, 128]
```

That window is 94 cells wide and it is not a search parameter. The only thing
a dispatch config changes is how much of it is free — cells below the lowest
landing and outside the fixed prefix are assignable; cells from a landing up
to its station are base NOPs.

`research/map12-hi/window_analysis.py` computes that free width `W` for every
config. The result is the first reason to think this rung is structurally
different from map8 rather than merely bigger:

```
115 separating configs, W distribution: max = 60, min = 47
every config's minimum landing lies in [82, 96]
```

Twelve private tails need at least 3 cells each (shape + `OUT` + `HALT`) plus
their operand trails, inside 47–60 free cells. There is no config that buys
its way out of this — the spread across all 115 configs is 13 cells.

This also says the 2026-08-09 search ordering was pointed the wrong way. That
attempt sorted configs **smallest-landing-first**, which is exactly the order
that minimises `W`. Re-sorting by `W` descending (configs 5, 6, then the
59-wide band at 7, 8, 11, …) is what this attempt searched instead. It did
not solve the rung — but it is where the better partial candidates came from,
so the ordering correction is real even though it was not sufficient.

## 2. Reachable-output sets, not existence probes

`research/map12-hi/reach.py` asks, for a lane and geometry, *what is the full
set of bytes this lane can emit* over every `(p, T)` pointer pair, NOP runway
and tail shape, with the shared assignment left empty. Computed with an empty
assignment this is an upper bound: a byte outside the set is unemittable by
that lane no matter what the other eleven lanes do.

Config 0, zero splits, default offsets — the exact geometry Codex drilled:

| input | J | target | | reachable set |
|---|---|---|---|---|
| 0xa5 | 165 | 0xf4 | HIT | 256 |
| 0xe0 | 169 | 0xb1 | MISS | **0** |
| 0x90 | 90 | 0xc1 | MISS | 209 (nearest 0xb1, Δ16) |
| 0x9c | 84 | 0xcd | MISS | 209 (nearest Δ4) |
| 0x84 | 114 | 0xd5 | HIT | 209 |
| 0xa1 | 88 | 0xf0 | HIT | 209 |
| 0xbd | 189 | 0xec | HIT | 256 |
| 0xc8 | 199 | 0x99 | HIT | 256 |
| 0xbe | 190 | 0xef | HIT | 256 |
| 0xf9 | 249 | 0xa8 | MISS | 209 (nearest Δ7) |
| 0x86 | 115 | 0xd7 | HIT | 209 |
| 0xdd | 166 | 0x8c | HIT | 256 |

Two facts here are new. First, lanes split cleanly into `|R| = 256` (target
always hit) and `|R| = 209` (47 bytes structurally unemittable, and four
lanes' targets fall in exactly that hole). The failure is not "the search ran
out of budget" — it is that 47 output bytes are off the reachable orbit for
low-J lanes, and this rung's input draw puts targets there. Second, `0xe0`
has `|R| = 0`: **no** `(p, T, k, shape)` combination is even placeable for it
in that geometry, which is a pure geometry failure distinct from the operand
failure of the other three.

## 3. The wall: lane `0x90 → 0xc1` is dead across the whole family

`research/map12-hi/screen.py` runs the necessary condition — every lane must
be able to emit its own target in isolation — over the whole config space.
A config that fails it cannot be rescued by any joint-assignment budget.

Full sweep, all 115 separating configs, splits 0–1, offset variants `()` and
`(4,)`, 6 workers:

```
1187 geometries screened
0 geometries with all twelve lanes live
maximum lanes live before the first dead lane: 2
892 geometries reached lane 0x90 and proved it dead
109 of 115 configs contained at least one such geometry
```

A follow-up screen restricted to the three hard lanes, splits 0–2 and four
offset variants, added **424 more geometries** — lane `0x90` was dead in every
one of those too.

So across **1611 geometries spanning all 115 separating dispatch
configurations**, the lane `0x90 → 0xc1` never once had a tail that emits
`0xc1`, with maximum operand freedom and no competing lanes. `0xe0 → 0xb1`
and `0xa5 → 0xf4` account for the geometries where the screen stopped even
earlier.

This is the strongest statement available about this rung short of a proof.
It is bounded by the tail grammar (`geometry.SHAPES`: `NOP*k` then
`[MOVD]?[ROT]?[MOVD]?CRAZY*0..4`, `k ≤ 8`) and by the two-stage station
architecture itself. Within those bounds it is not a budget result — the
screen is exhaustive over pointer pairs, runways and shapes, and it is
per-lane, so no amount of joint search changes it.

`map12-hi` should be read the way `map12-low` already is: not "separation is
available so realisation is the work", but **separation is available and
realisation is blocked on a specific lane**. The board's feasibility tool
scores separation only; it reports 115 separating configs and min landing gap
1 for this rung, which is why the rung ranked 15. That number is silent about
whether a separated lane can then *emit* its byte, and on this rung four
lanes cannot.

## 4. What was built anyway: a verified 7/12

Both prior attempts reported no candidate, because the joint search only
emits a program when all twelve lanes route. `research/map12-hi/partial_build.py`
adds a skip branch to the joint backtracking and keeps the assignment that
satisfies the most lanes, so the rung gets a number.

Best natively verified candidate: `docs/attempts/2026-08-10-claude-map12-hi.best.mal`
(config 5, zero splits, station offsets `(4,)`, landings
`[96, 123, 124, 125, 126, 128, 146, 150, 152, 155, 159, 252]`, 296 bytes,
joint-assignment node budget 25,000).

```
$ ./target/release/malbolge-rungs verify --rung L2.FM2h.xor51-map12-hi \
      --program docs/attempts/2026-08-10-claude-map12-hi.best.mal --verbose
  epoch 0 seed=aa70e690...  7/12 cases  FAIL
    case  0: in=a5 exp=f4 got=f4 [Halted] ok
    case  1: in=e0 exp=b1 got=<none> [Error: invalid runtime instruction at address 109] MISS
    case  2: in=90 exp=c1 got=          [Halted] MISS
    case  3: in=9c exp=cd got=ea [Halted] MISS
    case  4: in=84 exp=d5 got=09 [Halted] MISS
    case  5: in=a1 exp=f0 got=f0 [Halted] ok
    case  6: in=bd exp=ec got=ec [Halted] ok
    case  7: in=c8 exp=99 got=99 [Halted] ok
    case  8: in=be exp=ef got=ef [Halted] ok
    case  9: in=f9 exp=a8 got=ec [Halted] MISS
    case 10: in=86 exp=d7 got=d7 [Halted] ok
    case 11: in=dd exp=8c got=8c [Halted] ok
```

The five misses are exactly the four lanes the screen proves structurally
dead in most geometries (`0xe0`, `0x90`, `0x9c`, `0xf9`) plus `0x84`, which is
individually live here but loses the joint packing inside the 47-60 free
cells. The dispatch itself is sound for all twelve: every input reaches its
own lane. A cheaper run of the same builder (node budget 1,500, same
geometry) verifies 6/12 and is kept as a reproducibility check.

Given four lanes are provably out in this geometry, **8/12 is the ceiling for
the two-stage family here**, and 7/12 is one short of it. That is the number
this attempt leaves on the board.

## 5. I tested my own next lever, and it failed

The reachable-set data pointed at one lever above all others: `ROT` sets
`a = rot(mem[d])`, overwriting the accumulator with a function of a *cell
value*, so it severs the dependence on `J(x)` entirely. The stock catalog
allows at most one `ROT`, which is why every lane's reachable set is an orbit
anchored at its landing. A second `ROT` should, on that reasoning, wipe the
anchor and open the 47-byte hole.

`research/map12-hi/tworot.py` widens the catalog from 24 shapes to 56 —
`[MOVD]? [ROT]? [MOVD]? [ROT]? CRAZY*0..4` — and re-runs the necessary
condition:

```
cfg0 offs=()     shapes=56  live=8/12  dead=[0xe0, 0x90, 0x9c, 0xf9]
cfg0 offs=(4,)   shapes=56  live=9/12  dead=[0x90, 0x9c, 0xf9]
cfg0 offs=(0,6)  shapes=56  live=9/12  dead=[0x90, 0x9c, 0xf9]
cfg5 offs=()     shapes=56  live=7/12  dead=[0xa5, 0xe0, 0x90, 0x9c, 0xf9]
cfg5 offs=(4,)   shapes=56  live=8/12  dead=[0xe0, 0x90, 0x9c, 0xf9]
cfg5 offs=(0,6)  shapes=56  live=7/12  dead=[0xa5, 0xe0, 0x90, 0x9c, 0xf9]
```

Identical dead sets. Doubling the ROT budget and adding a mid-tail `MOVD`
changes nothing for `0x90`, `0x9c`, `0xf9`. The 2026-08-09 record guessed the
tail-shape family was the next lever; combined with Codex's brute force over
`{MOVD, ROT, CRAZY}` bodies to length 5, and now this, **the tail grammar is
ruled out as the fix**. Three separate qualitative widenings of the tail
language leave the same three lanes dead.

That moves the diagnosis one level down: the obstruction is not what the tail
can compute, it is *what the tail can read*. Every operand comes from a cell
in `[35, 128]` and must be source-valid at its own address, so each lane's
trail has 8 choices per cell drawn from an alphabet fixed by `address mod 94`.
Whatever fix exists has to change those alphabets — which means changing where
tails live, not what they do.

## What I ruled out

- **More joint-search budget.** Ruled out as the blocker. The obstruction is
  per-lane and holds with the shared assignment empty, which is strictly more
  freedom than any joint search ever has.
- **A better config.** Ruled out within the enumerated family: all 115
  separating configs fail the necessary condition, and `W` varies by only 13
  cells across them.
- **Smallest-landing-first ordering** (2026-08-09's choice). Ruled out as the
  right heuristic — it minimises the free tail window. Largest-`W`-first is
  better and is what produced the 7/12.
- **Longer runways / deeper CRAZY chains** — already ruled out by the Codex
  record; my reachable-set computation explains *why*: for low-J lanes the
  reachable orbit is 209 of 256 bytes and the missing 47 include those
  targets, so extending the same grammar cannot reach them.

## What I would try next, with more budget

Section 5 already spent this attempt's last budget on the lever the data
pointed at, and it failed. That reorders what is left. In priority order:

1. **Widen the tail window — the three-hop pointer chain.** `L ∈ [34, 127]`
   exists only because `T = mem[p+1]` is a single byte. Chaining one more
   indirection (`p → T → T'`, with the second hop's cell holding a value that
   is itself read as an address) places tails anywhere in the program and, far
   more importantly, gives each lane a *different operand alphabet* — which
   Section 5 identifies as the real obstruction. Cost: one extra free cell per
   lane, against a 47–60-cell budget. This is now the first thing I would run.
2. **Characterise the 47-byte hole in closed form.** I have it empirically
   (`|R| = 209` for low-J lanes, 256 for high-J) but not as a function of
   `J(x)` and the trail alphabets. Deriving it would say directly whether any
   placement of tails can emit `0xc1` from `J = 90`, turning this attempt's
   1611-geometry negative into a proof or a counterexample. It would also
   transfer to `map16` and `map12-low` immediately.
3. **Shared tails.** `0x90`, `0x9c`, `0xf9` all have targets in the hole. A
   tail entered at different offsets by several lanes, or a lane falling
   through into another's tail after a corrective CRAZY, spends fewer cells
   and — again — reads a different alphabet.

I would not spend more budget on the two-stage family's tail *language*.
Three independent widenings have now failed against the same three lanes.

## Reproduce

```sh
cargo build --release
python3 research/map12-hi/window_analysis.py             # W per config
python3 research/map12-hi/reach.py 0                     # reachable-output sets
for w in 0 1 2 3 4 5; do
  python3 research/map12-hi/screen.py $w 6 1 2 &         # full necessary-condition sweep
done
MAP12HI_LANES=0x90,0x9c,0xf9 python3 research/map12-hi/screen.py 0 1 2 4
MAP12HI_OFFS=4 python3 research/map12-hi/partial_build.py 5 25000  # the 7/12
python3 research/map12-hi/tworot.py 0 5                   # the falsified lever
```

## Honest limits of the negative result

- The screen's per-lane walk memoises on `(op index, accumulator, data
  pointer)` and drops the partial cell assignment from the memo key. On a
  path where `MOVD` re-reads an already-assigned cell this can in principle
  suppress a branch, so "dead" means dead under that memoisation, not under a
  literal exhaustive enumeration. Every reported dead lane was dead in
  hundreds of independent geometries, so I do not think this changes the
  conclusion, but it is not a proof.
- The result is scoped to the two-stage CRAZY-dispatch family in
  `research/map12hi/`. It says nothing about a different architecture.
