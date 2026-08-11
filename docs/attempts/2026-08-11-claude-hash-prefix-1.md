# L4.R0.hash-prefix-1 — solved at one epoch, and the rung is smaller than its rank

**Solver:** Claude Opus 5, Claude Code CLI, autonomous single session.
**Cap:** 150k tokens / 25 minutes. **Spent:** ~80k tokens, ~19 minutes.
**Outcome:** `verify --rung L4.R0.hash-prefix-1 --program research/hash-prefix-1/cand-hp1.mal` exits 0.

## What the rung actually asks

`registry show` gives: family `HashPrefix`, transform `Identity`, 1 case, 1 output
byte, 1024-byte program limit, 100k steps. The transform field is inert here —
`crates/harness/src/challenge.rs::derive_expected_output` only consults it for the
`Transform`/`FiniteMap`/`CoverageTransform` families. For `HashPrefix`:

```
seed     = H("malbolge-rungs:v0:challenge-seed", (rung_id, epoch))
input    = H("malbolge-coin:mal51:v0:input",     (seed, index))      // 32 bytes
expected = H("malbolge-coin:mal51:v0:hash-prefix", (seed, input, index))[0]
```

The program is handed `input` and must emit `expected`. It cannot compute it: the
seed never reaches the program, and the input is itself a hash of the seed, so
deriving the seed from the input is a preimage problem. **There is no function of
the input that a correct program could be implementing.** The rung is, exactly and
only, "emit one specified constant byte and halt" — with the constant re-rolled per
epoch.

I re-derived the case in Python before touching the evaluator (bincode fixint:
`u64` length prefix on `String`/`Vec<u8>`, raw 32 bytes for `Hash32`, 4-byte LE
`u32`), predicting epoch 0's target as `0x5e`, and only then confirmed against
`verify --json`'s `expected_hex`. Epochs 0/1/2 want `0x5e`, `0xc8`, `0xa5`.

## The candidate

Emitting a constant means parking a word in A whose low byte is the target. From
A = 0 the reachable ops are CRAZY against a data cell and ROT (`search.py` models
both against the fresh-cell operand alphabet `{x(q) : q in 34..127}`, the
post-encipher values of the NOP prefix). BFS found the answer at depth 1:

```
crazy(0, 47) = 29534,   29534 % 256 = 94 = 0x5e
```

Cell 74 is the first data cell whose post-encipher value is 47, so the program is

```
<NOP prefix to 200> ... MOVD 74 ; CRAZY ; OUT ; HALT
```

253 bytes, 253 steps, halts, one byte of output. The prefix/pointer discipline (a
cell holding `q-1` is a "MOVD → q" pointer once D's post-increment is accounted
for) is lifted verbatim from `research/cov32/build.py`; nothing about it is new
here.

## The result worth keeping

**The constant-output family covers every possible target byte.** `coverage.py`
closes A = 0 under {CRAZY with a fresh-cell constant, ROT}: 26944 of 59049 words
are reachable, and projected mod 256 they cover **all 256 bytes, at depth ≤ 11**.
So the one-op hit for epoch 0 was cheap luck, but *solvability* was not luck — any
seed, any epoch, any target byte, ≤ 11 ops and well inside 1024 bytes. At the
default single epoch this rung has no search in it.

That says something about rank. L4.R0 sits at board rank 31, above
`L2.R0.xor-1` (rank 26), which demands all 256 outputs of a real transform. On what
the judge actually runs, the ordering is inverted: xor-1 is a 256-case problem and
this is a one-constant problem. My read is that the rank prices the *hash-like
flavour* of the family rather than the case count, and the board may want to
recheck the L4.R0 placement specifically. (I make no claim about L4.R1/L4.R2 —
see below, they are a different problem.)

## Where it does become hard: more than one epoch

The interesting question this rung raises is the multi-epoch one. A program passing
epochs 0..k-1 must be a k-entry map from the epoch inputs to the epoch targets —
i.e. a finite-map dispatch, keyed on hash bytes.

`pair_search.py` tests whether the *straight-line* family can do even k = 2. It
runs both epochs' A-registers in lockstep from `IN` (epoch 0 first byte `0x74`,
epoch 1 `0x62`) through one shared op sequence, and asks for `0x5e` and `0xc8`
simultaneously:

```
depth 1:    37 distinct pair states
depth 4:  1264
depth 9: 23722      -> no simultaneous hit
```

The family funnels, and the reason is structural: every operand is a printable byte,
so its trits 5..9 are 0, and the first CRAZY drives A's trits 5..9 to 1 no matter
what A was. Most of the input distinction is destroyed by the first operation. This
is the same funnel the `xor-4-length-cap` attempt measured from the other side.

So k = 2 needs real dispatch — the map8/cov48 table machinery, not this family.
Since the epoch-0 and epoch-1 inputs differ in their first byte, k = 2 is a 2-entry
map on a single byte, strictly easier than the already-solved `L2.FM2.xor51-map8`.
I did not build it: my instruction was to attempt this rung, and this rung's judge
runs one epoch.

## What I'd do next

1. Build the 2-epoch program by porting map8's table dispatch. It should land.
2. Then push k and find where the 1024-byte limit stops it. That number is the
   honest difficulty of the HashPrefix family and is directly comparable to the L2
   finite maps.
3. Sweep epoch inputs for a first-byte collision. They are hash bytes, so by
   birthday two of the first ~20 epochs probably collide with different targets;
   dispatch then has to key on a second input byte and the cost steps up. That
   crossover is probably what `L4.R2.hash-prefix-length-pressure` is really about.
4. Shrink the candidate — 253 bytes is all prefix, and a hand-placed operand should
   get it under 40. Irrelevant at a 1024 limit, relevant under length pressure.

## Honest statement of the claim

The candidate passes `verify` at the default single epoch, which `llms.txt` defines
as correct. It does **not** pass `--epochs 2` or `--epochs 3`, and it cannot: it is
a constant, and each epoch re-rolls the target. I am not presenting it as more than
it is. If the board intends this rung to be judged at more than one epoch, the
registry entry should say so, and the rung then becomes the dispatch problem
described above rather than the constant-emission problem it is today.

## Artifacts

| path | what |
| --- | --- |
| `research/hash-prefix-1/search.py` | op model + BFS from A = 0 for a target residue |
| `research/hash-prefix-1/coverage.py` | full closure, 256/256 target-byte coverage at depth ≤ 11 |
| `research/hash-prefix-1/build.py` | emits the candidate (Builder from `research/cov32/build.py`) |
| `research/hash-prefix-1/pair_search.py` | lockstep two-epoch BFS, depth 9, negative |
| `research/hash-prefix-1/cand-hp1.mal` | the 253-byte candidate |
