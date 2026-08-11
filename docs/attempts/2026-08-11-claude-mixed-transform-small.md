# Claude attempt: `L3.R2.mixed-transform-small`

Date: 2026-08-11

Outcome: **unsolved**. The shipped candidate is 512/512 bytes, halts in 30
steps, and is correct on **78 of the 65536 `(b0,b1)` pairs** — an epoch pass
probability of about **1.7e-9**. Native `verify` on epoch 0 is `0/3`, but two of
the three cases have the **first** output byte right.

Solver: Claude (Opus 5) via Claude Code, autonomous single-session run under a
hard cap of 200k tokens / 30 minutes.

Artifacts:
[`research/mixed-transform-small/build_mts.py`](../../research/mixed-transform-small/build_mts.py)
(layout, DP driver, overlay VM, exhaustive pair scorer),
[`research/mixed-transform-small/dpk_nib.c`](../../research/mixed-transform-small/dpk_nib.c)
(`research/xor-1/dpk.c` with the target changed from `b^0x51` to
`(b<<4)|(b>>4)`),
[`research/mixed-transform-small/cand-mts.mal`](../../research/mixed-transform-small/cand-mts.mal),
[`research/mixed-transform-small/model-mts.txt`](../../research/mixed-transform-small/model-mts.txt).

Builds on
[`2026-08-11-claude-xor-4-length-cap.json`](2026-08-11-claude-xor-4-length-cap.json)
(the D-funnel result and the ride-chain architecture I reuse),
[`2026-08-11-claude-xor-1.json`](2026-08-11-claude-xor-1.json) (whose exact DP I
reuse with one line changed), and
[`2026-08-11-claude-reverse-2-multicase.json`](2026-08-11-claude-reverse-2-multicase.json)
(which named this rung explicitly as the next place to look). `api/attempts.json`
carries **no** record for this rung; this is the first.

## What the rung actually asks

`crates/harness/registry.json` gives family `Transform`, `transform: NibbleMap`,
`output_bytes: 2`, `cases: 3`, `max_program_len: 512`, `max_steps_per_case:
16384`. `challenge.rs` then fixes the rest:

- inputs are the 32 bytes of a seed-derived hash, **fresh every epoch**, so one
  epoch is *not* definitive here;
- `derive_expected_output` takes `prefix = input[..2]` and
  `transform_bytes` maps `NibbleMap: b -> (b<<4)|(b>>4)` over it.

So the required output is `swap(b0), swap(b1)` — **two independent value
functions of two independent bytes**. The `reverse-2` record's classification is
the right one and it lands this rung on the hard side of it: `Reverse` and
`Identity` are rearrangements and need no table, while `NibbleMap` is a function
of the byte's value and needs one. Its closing prediction for this rung —
"`NibbleMap` on a byte is a rotation by 4 bits, and `ROT` rotates by trits, so
the two do not compose. Expect the `xor-1` wall there" — **is confirmed, with a
number**: the same architecture that reaches 68/256 for `b^0x51` reaches
**63/256** for `swap(b)`. The wall is the same wall and the target function
moves it by five inputs.

## The 512-byte cap buys almost nothing, and the reason is worth recording

This rung's cap is 512 where `xor-1` and `xor-4` are capped at 256. That looks
like the binding difference and it is not. In the forced stride-1 layout the
dispatch offset `K0` is not bounded by the program length at all:

    P = K0 + k + m + 12          (code length)
    data pointer cells live at 40, 62, 71, 72, 73, 123
    they must sit above the code:  P <= 40   =>   K0 <= 28 - k - m

The pointer cell at address **40** is what caps `K0`, because the very first
`MOVD` executes at `C = D = 1` and reads its own instruction byte, which lands
`D` on 40. So `K0 <= 20` here exactly as in the 256-byte rungs, the operand
window for small `b0` still falls inside the code, and the extra 256 bytes buy
only one thing: the window for large `b0` (`b0 + K0 + k <= 511`) is now
**designable instead of crazy fill**. Worth roughly nothing — the DP's optimum
moved from `k=5` to `k=7` and the score is within five of `xor-1`'s.

**A length cap above ~300 bytes is not a difficulty variable on this family.**
The `xor-1` record measured length as worth ~51 inputs going 256 → 4096; that
gain is entirely the stride-9 private-block layout, which needs 2302 cells of
table. Between 256 and 512 there is no architecture change to buy, so the cap
change is inert. If the board wants length to be the lever between two rungs,
the step has to cross 2302 cells, not 512.

## What was built

The `xor-4` architecture cut to two outputs: one real DP-designed dispatch on
`b0`, then one ride chain for `b1`.

    0        IN            A = b0
    1,2,3    MOVD x3       D: 1 -> 40 -> 123 -> 71
    4,5      CRZ x2        m[71]=m[72]=121 -> cell 72 holds b0 exactly
    6,7,8    MOVD x3       D: 73 -> 62 -> 72 -> m[72]+1 = b0+1
    9..17    NOP x 9       dispatch offset K0 = 10
    ..       CRZ x 7       operands m[b0+10 .. b0+16]      <- DP-designed
    ..       OUT           out0 = swap(b0)
    ..       IN            A = b1
    ..       CRZ x 1       rides the cell the first walk left D on
    ..       OUT           out1
    ..       HALT          P = 30, 512 bytes total

Exact DP (`dpk_nib.c`, transfer-matrix over the shared operand table) swept
`k ∈ {3,5,7} × K0 ∈ 1..19 × m ∈ {1,2,3}`, 135 exact optimisations. Best 62 at
`k=7, K0=10, m=1`; the assembled program measures **63/256** (the DP scores the
`b0` whose window straddles `L` conservatively).

| | best phase A | cap | outputs |
|---|---|---|---|
| `L2.R0.xor-1` | 68/256 | 256 | 1 |
| `L2.R3.xor-2-multicase` | 66/256 | 384 | 2 |
| **this rung, `NibbleMap`** | **63/256** | **512** | **2** |
| `L3.R1.xor-4-length-cap` | 61/256 | 256 | 4 |

Exhaustive measurement over all 65536 pairs (overlay VM, cross-checked
natively): phase A **63/256**, good pairs **78/65536 = 1.19e-3**, epoch pass
`(78/65536)^3 = 1.7e-9`. The single ride chain loses a factor of ~50 against
what a second real dispatch would give.

## Verification (native)

```sh
./target/release/malbolge-rungs verify --rung L3.R2.mixed-transform-small \
    --program research/mixed-transform-small/cand-mts.mal --verbose
# epoch 0 seed=311027c7…  0/3 cases  FAIL
#   case 0: in=25f9…  exp=529f got=5261 [Halted]   <- byte 0 correct
#   case 1: in=4e4c…  exp=e4c4 got=3849 [Halted]
#   case 2: in=8eaf…  exp=e8fa got=e8a0 [Halted]   <- byte 0 correct
```

Model VM and native VM agree byte for byte:

```sh
execute --input-hex 1417 -> [65,113] = 4171  Halted, 30 steps   both bytes right
execute --input-hex 1400 -> [65,123] = 417b  Halted, 30 steps   ride misses, as predicted
```

`swap(0x14) = 0x41`, `swap(0x17) = 0x71`. Every number above is an exhaustive
model measurement spot-checked natively; none of them is an epoch result.

## Ranking: this rung is easier than the one below it

The board has `L3.R1.xor-4-length-cap` at 29 and this rung at 30. The evidence
here says that ordering is **inverted**, and the comparison is unusually clean
because the two were built with the same DP, the same parking gadget and the
same ride architecture within a day of each other:

| | this rung | `xor-4` |
|---|---|---|
| real dispatches needed | **2** | **4** |
| fresh 121-parking pairs needed | 2 | 4 |
| parking pairs MOVD-addressable (≤127) | **2 available — exactly enough** | 2 available — **half short** |
| program cap | 512 | 256 |
| measured epoch pass probability | **1.7e-9** | 1.2e-14 |

`xor-4`'s recorded blocker is precisely the parking-pair shortage: four
dispatches need four pairs, only `(71,72)` and `(106,107)` are addressable, and
NOP-walking `D` up to `(165,166)`/`(200,201)` costs ~38 and ~35 bytes that do
not fit in 256. **This rung needs exactly two, and exactly two exist.** Its
binding constraint is therefore the 63/256 arithmetic ceiling alone, while
`xor-4` has that ceiling *and* a cell-budget problem *and* raises it to the
fourth power. On every axis the two records share, this rung is the easier one.
It should sit at 29 and `xor-4` at 30.

Against `L2.R0.xor-1` (26) the board is right: this rung is strictly harder,
because it needs the `xor-1` ceiling broken **twice** and a `D` reset in
between. Passing an epoch needs `p^3` where `p` is the pair rate, so nothing
short of `p` near 1 — i.e. near 256/256 on a single dispatch — ever passes
reliably. **The `xor-1` wall is a hard prerequisite for this rung**, and no
amount of work on the second dispatch matters until it falls.

## Budget

Full 30-minute wall, roughly 100k of the 200k token cap. Split: about half on
prior art (four records in this clone, all of which bore directly on this rung),
a quarter on establishing what the rung asks and why the 512 cap is inert, a
quarter on the build and the exhaustive measurement.

The single best-spent input was the `xor-4` record's funnel result. It is what
told me the second dispatch is buildable here, which is what makes the ranking
argument above sharp rather than speculative — I did not have the wall-clock to
build it, but I know what it costs and what it is worth.

## For the next agent

1. **Build the two-dispatch program. It fits here, and it is the one place on
   the board where it does.** `research/xor-4-length-cap/funnel_min.py` gives a
   28-cell pinned tree rooted at `p = 67` and 7 `MOVD`s that collapse any
   polluted `D` onto one known cell. Feed those 28 cells to `dpk_nib.c` as `F`
   cells (the DP absorbs them exactly). Then: dispatch on `b0`, `OUT`, funnel,
   NOP-walk `D` to the second 121-pair at `(106,107)`, `IN b1`, park, `MOVD`
   chain back to 107 giving `D = b1+1`, **re-enter the same operand table**, `OUT`,
   `HALT`.
2. **Both dispatches can share one table**, which is the structural gift this
   rung's transform hands you and the reason it fits in 512 bytes: `swap` is the
   same function for both bytes, so the same operand window serves both walks.
   The only interference is that phase A's `CRZ`s **write** their window, so the
   sharing breaks exactly when `|b0 - b1| < k` — about `(2k-1)/256 = 5%` of pairs
   at `k=7`, and cheaper at `k=5`. Expected result: `(63/256)^2 × 0.95 ≈ 5.7%`
   of pairs, epoch pass `≈ 1.9e-4`. That is a factor of **10^5** over what is
   shipped here, for maybe 60 bytes of code, and it is a build task, not a
   research question.
3. **It still does not solve the rung, and that is the real finding.** Even a
   perfect second dispatch leaves the pair rate at `p^2 ≤ (77/256)^2 = 9%` under
   the family's known free-layout bound. **The only thing that solves this rung
   is breaking the 77/256 ceiling itself**, which is the unrun `ROT`-in-the-walk
   BFS from the `xor-1` record — all operands are `< 243 = 3^5` so trits 5..9
   evolve without choice, and `ROT` promotes a controllable low trit to trit 9
   in one instruction. 59049 states, a trivial BFS, still nobody has run it. It
   lifts `xor-1`, `xor-1-len4096`, `xor-2`, `xor-4` and this rung at once, and
   on this rung it is not one lever among several — it is the whole thing.
4. **Do not spend budget on the length cap.** `K0 <= 28 - k - m` is forced by
   the pointer cell at address 40, not by `max_program_len`. 512 bytes and 256
   bytes are the same rung arithmetically; the next real threshold is 2302
   cells, where stride-9 private blocks become affordable and the `len4096`
   record's 119/256 comes back.
