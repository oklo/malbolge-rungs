# Claude attempt: `L3.R0.reverse-2-multicase`

Date: 2026-08-11

Outcome: **solved**. A 122-byte program that halts in 71 steps and emits the
first two input bytes in reverse order, for every one of the 65536 possible
`(b0,b1)` pairs. Native `verify` passes 3/3 cases on epoch 0 and 192/192 cases
over 64 epochs.

Solver: Claude (Opus 5) via Claude Code, autonomous single-session run under a
hard cap of 200k tokens / 30 minutes.

Artifacts:
[`research/reverse-2-multicase/mal.py`](../../research/reverse-2-multicase/mal.py)
(model VM mirroring the Rust one),
[`research/reverse-2-multicase/build_rev2.py`](../../research/reverse-2-multicase/build_rev2.py)
(layout search + assembler),
[`research/reverse-2-multicase/exhaustive.py`](../../research/reverse-2-multicase/exhaustive.py)
(all-65536-pairs check + control-flow identity check),
[`research/reverse-2-multicase/cand-rev2.mal`](../../research/reverse-2-multicase/cand-rev2.mal)
(the program).

Builds on [`2026-08-11-claude-xor-2-multicase.json`](2026-08-11-claude-xor-2-multicase.json).
`api/attempts.json` carries no record for this rung.

## The ranking result first

That prior record — the only recorded attempt on the neighbouring multicase
rung — closes with an explicit prediction:

> Consequence for the whole multicase family (`L3.R0.reverse-2-multicase` and
> `L4.R1.hash-prefix-1-multicase` inherit it): **a second dispatch is not a
> second copy of the code.** It is a new problem.

**That inheritance does not hold, and the reason is the transform, not the
multicase-ness.** The D-pollution wall is a consequence of *dispatch*: on
`xor-1`/`xor-2` the program must index an in-program operand table by the input
byte, which is exactly what makes `D` input-dependent and unrecoverable.
`Reverse` needs no table. `derive_expected_output` takes `prefix = input[..2]`
and `transform_bytes` returns `prefix` reversed, so the required output is
`[b1, b0]` — a **byte swap**, a pure data movement with no arithmetic on the
byte values at all. The program can be **straight-line and input-independent**:
`exhaustive.py` confirms the sequence of `(C, D)` pairs is bit-identical for
every sampled input, so `D` is never polluted and there is nothing to reset.

So rank 28 is too high for this rung. It sits above `L2.R0.xor-1` (26) and
`L2.R3.xor-2-multicase` (27) and is strictly easier than both: those two need a
per-input value map that provably tops out at 68/256, with 77/256 bounding the
whole known family, while this one needs no map at all. Its real difficulty is
**one gadget above the L1 echo rungs** — the store-across-an-output gadget —
and it belongs below every `xor51-mapN` and `xor51-covNN` rung.

The `Reverse` transform is worth stating plainly, because the ladder's shape
around it is misleading in both directions. `transform_bytes` reverses the
`output_bytes`-length prefix, so at `output_bytes = 1` `Reverse` **is
`Identity`** — which is why `L2.R1.reverse-1` is already solved and sits low.
The jump from `reverse-1` to `reverse-2` is therefore not "one byte to two
bytes of a hard transform"; it is exactly the appearance of the store, and
nothing else. That is a real step (Malbolge has no load instruction), but it is
one step, not the compounding wall the rank implies. "Reverse two bytes across
multiple cases" sounds harder than "xor one byte" and is much easier; the
ladder's own warning that difficulty is the rank and not how the transform
sounds cuts the other way here.

## The one real obstacle, and the instruction that solves it

The output order is fixed: `b1` must be emitted before `b0`, but `b0` arrives
first. So `b0` has to be stored across the `b1` input and output. Only `A` holds
a value, and the store/reload is the whole problem:

> **`CRZ` is not a load.** `62` computes `crazy(A, m[D])` — it mixes the old `A`
> in. Reloading `b0` after `A` has been overwritten by `b1` through `CRZ` gives
> a function of both. `4` (`JMP`) and `40` (`MOVD`) write `C`/`D`, not `A`.
> **`39` (`ROT`) is the only instruction in the language that loads `A` from
> memory without reading the old `A`** — and it loads `rotr(m[D])`, a one-trit
> right rotation, not `m[D]`.

That single fact dictates the architecture. Two sub-results make it work.

**Parking `b0` exactly.** With `m[P] = 121 = 11111₃`, the crazy table
`crazy_trit(a, d)` indexed by memory trit `d` gives `R₁ = [1,0,2]` = `swap01`
for the five low trits (an involution) and `R₀ = [1,0,0]` for the rest, which
*agrees with* `swap01` on `{0,1}`. Since `b0 ≤ 255 < 2·3⁵`, trit 5 of `b0` is in
`{0,1}` and trits 6–9 are 0. So two `CRZ`s against consecutive 121-cells leave
`A = b0` **and** `m[P] = b0`, every trit exact — including the high trits, which
go `0 → 1 → 0`. Exactness matters here in a way it did not for the `xor` rungs:
the rotation arithmetic below reads all ten trits, so a value merely congruent
to `b0` mod 256 would not survive.
The loader admits exactly three usable parking cells: `(v + a) mod 94 ∈ opset`
with `v = 121` forces `(27 + a) mod 94 ∈ opset`, and consecutive addresses need
consecutive opcodes, of which the set has only `(4,5)` and `(39,40)` — giving
`Q ∈ {13, 72, 107}` at addresses ≤ 127 (the `MOVD` reach bound). This confirms
the `xor-1` record's parking-pair enumeration from the other direction.

**Beating the rotation.** `ROT` is a cyclic rotation of a 10-trit word, so
`rotr¹⁰ = id`. Applying `ROT` to the parked cell **nine** times before the `b1`
phase leaves `m[Q] = rotr⁹(b0) = rotl(b0) = 3·b0` (legal because `b0 < 3⁹`);
the **tenth** `ROT`, placed after `OUT b1`, returns `A = rotr(3·b0) = b0`
exactly. No trit-local operation can do this instead: the shift is not
trit-local, and I checked the alternative — resetting `A` to a known constant
`c` and reloading with one `CRZ` gives `C_c ∘ R_w`, and a parity argument kills
it. The only injective row is `R₁ = swap01` and the only injective column is
`C₂ = swap12`; every product `swap01^i ∘ swap12 ∘ swap01^j` is a transposition
or a 3-cycle, never the identity. **`ROT` is not one option among several — it
is the only load, and the rotation must be paid for.**

`D` cannot stay on the parked cell (every instruction increments `D`), so each
rotation needs a `D` reset. The one-hop reset `m[Q+1] = Q-1` needs
`2Q mod 94 ∈ opset`, which fails for all three of `Q ∈ {13,72,107}` (giving 26,
50, 26). A two-hop reset costs three instructions per rotation:

    MOVD  at D=Q+1 -> D = m[Q+1]+1 = X      (m[Q+1] = X-1)
    MOVD  at D=X   -> D = m[X]+1   = Q      (m[X]   = Q-1)
    ROT   at D=Q

`MOVD` never writes memory, so both cells are reusable forever.

## The program

122 bytes; code at 0–70, data at 71–121. `Q = 72`, `X = 121`, `X2 = 85`,
`D1 = 105`, three `NOP`s of `D`-walk before the final reset.

      0        IN            A = b0
      1- 29    NOP x29       D tracks C; positions the first MOVD so its own
                             byte (104) points at a data cell above the code
     30- 31    MOVD x2       D: 30 -> 105 -> 72-1 = 71   (m[105] = 70)
     32- 33    CRZ  x2       m[71], then m[72] = b0 exactly; A = b0; D -> 73
     34- 60    (MOVD,MOVD,ROT) x9    m[72] = rotr^9(b0) = 3*b0 ; D -> 73
                             m[73] = 120 -> D=121 ; m[121] = 71 -> D=72
     61        IN            A = b1 ;  D -> 74
     62        OUT           emit b1   <-- first output byte
     63- 65    NOP x3        walk D 75 -> 78
     66- 67    MOVD x2       m[78] = 84 -> D=85 ; m[85] = 71 -> D=72
     68        ROT           A = rotr(3*b0) = b0
     69        OUT           emit b0   <-- second output byte
     70        HALT

    uCBA@?>=<;:9876543210/.-,+*)('hg|{dcaa`^^][[ZXXWUUTRRQOONLLKI8%cbaDCA|iyyx+*)(T&%$#"!G/.-,+*)('&%$#"!!654F210/.-,+*)('&%$G

The 29 leading `NOP`s are not padding for its own sake: the first `MOVD`
executes at `C = D` and so reads *its own instruction byte*, which fixes
`D1 = m[a1] + 1` as a function of the address `a1`. Only a few `a1` give a
legal `MOVD` byte large enough to land above the 71-byte code region.
`build_rev2.py` searches `(Q, a1, k, X, X2)` against the loader predicate and
returns 65 valid layouts; the shortest was taken.

## Verification (native)

```sh
./target/release/malbolge-rungs verify --rung L3.R0.reverse-2-multicase \
    --program research/reverse-2-multicase/cand-rev2.mal --verbose
# epoch 0 seed=b32a5a23…  3/3 cases  PASS
#   case 0: in=d4f303ca… exp=f3d4 got=f3d4 [Halted] ok
#   case 1: in=6408ba9e… exp=0864 got=0864 [Halted] ok
#   case 2: in=4c065ceb… exp=064c got=064c [Halted] ok
# RESULT: PASS (native evaluator)     exit 0
```

Transform inputs are seed-derived, so one epoch is *not* definitive on this
family. Three independent hardenings:

- `--epochs 64` → 192/192 cases, `RESULT: PASS`, exit 0.
- `exhaustive.py` runs all **65536** `(b0,b1)` pairs through the model VM:
  **0 failures**, always `Halted` in 71 steps.
- The same script records the `(C,D)` trace for a sample of inputs and compares
  it to the `b0=b1=0` trace: **identical for every one**. The program has no
  input-dependent control flow, which is why 65536/65536 is not a coincidence
  to be re-tested per seed.

Native spot checks agree with the model on the extremes:
`ff00→00ff`, `00ff→ff00`, `f2f3→f3f2` (both sides above the 3⁵ boundary that
makes trit 5 live), `0001→0100`, `7f80→807f` — all `Halted` in 71 steps.

Resource use: 122/512 bytes, 71/8192 steps, 2/2 output bytes.

## Budget

Solved inside roughly 12 minutes and ~75k of the 200k token cap. The single
best-spent input was the `L2.R3.xor-2-multicase` record in this clone: reading
its D-pollution analysis is what made me check whether this rung needs a
dispatch at all, and finding that it does not is the whole solve. The
parking-pair trick and the 121 constant came from it directly, already proved.

## For the next agent

1. **`L3.R1.xor-4-length-cap` and `L5.R0.future-transform` do not inherit
   anything from this.** The separation is dispatch vs. data movement, not
   number of cases. Before assuming a multicase rung is hard, read
   `challenge.rs::transform_bytes` and ask whether the transform is a
   permutation of the input bytes (`Identity`, `Reverse`) or a function of their
   values (`XorMask`, `RotateLeft`, `NibbleMap`, `CrazyMask`). The first kind
   needs no table and is straight-line; the second kind hits the 68/256 wall.
2. **`L4.R1.hash-prefix-1-multicase` really does inherit the wall**, because a
   hash prefix is a value function of the input, not a rearrangement of it.
3. **The park-and-rotate gadget here is reusable verbatim** for any rung that
   must hold a byte across an intervening input or output: `CRZ,CRZ` against a
   121-pair to store exactly, `9 × (MOVD,MOVD,ROT)` to pre-rotate, one `ROT` to
   reload. It costs 34 instructions and four data cells, and it is the general
   answer to "Malbolge has no load instruction". `L3.R2.mixed-transform-small`
   (`NibbleMap`, `(b<<4)|(b>>4)`) is worth a look with it: that transform *is* a
   value function, so it needs a table — but `NibbleMap` on a byte is a rotation
   by 4 bits, and `ROT` rotates by trits, so the two do not compose. Expect the
   `xor-1` wall there.
4. **The `reverse-1` → `reverse-2` step is the store and only the store.**
   `L2.R1.reverse-1` is solved and is literally `echo-1` (a 1-byte reverse is
   the identity). This program fails that rung only because it emits two bytes
   against a 1-byte output cap — direct confirmation that the two rungs differ
   in exactly one gadget. If the board wants a genuine L3 step in this family,
   `reverse-4` would need three bytes parked across two intervening outputs and
   three separate rotation counts, which is where the `D`-navigation cell budget
   (four cells per reset path, all below address 128) actually starts to bite.
