# Claude attempt: `L2.R2.rotate-1`

Date: 2026-08-10

Outcome: **unsolved**, no verified candidate. The contribution is an exact
ceiling that rules the coverage-rung architecture out of this rung entirely.

Solver: Claude (Opus 5) via Claude Code, autonomous single-session run under a
hard cap of 150k tokens / 25 minutes.

DP: [`research/rotate-1/dp.c`](../../research/rotate-1/dp.c),
[`research/rotate-1/dp2.c`](../../research/rotate-1/dp2.c),
results [`research/rotate-1/dp-results.txt`](../../research/rotate-1/dp-results.txt).

Builds on [`docs/attempts/2026-08-10-claude-cov48.json`](2026-08-10-claude-cov48.json)
and [`docs/attempts/2026-08-10-claude-map16.json`](2026-08-10-claude-map16.json).
This is the cov48 table-dispatch architecture carried onto a full transform, and
the answer is that it does not reach.

## The rung, restated

`RotateLeft`, `cases = 1`, `output_bytes = 1`. The Transform family derives its
input from the epoch seed (`crates/harness/src/challenge.rs`), so the single case
is a *different* random byte every epoch and the verifier is all-or-nothing per
epoch. Epoch 0 is input `cb...` → expected `97`; epoch 1 is `8c...` → `19`. A
program that is correct on `n` of the 256 possible first bytes passes one epoch
with probability `n/256`, so unlike a coverage rung there is no partial credit
and one epoch is *not* definitive. The honest target is 256/256.

The binding constraint is not the transform. It is this line of the registry:

    max_program_len:  256        (cov48 had 4096; cov64 shipped 3813 bytes)

## Two facts that shape every architecture here

**1. `rotate_left(b,1)` is `2b mod 255` (with `0→0`, `255→255`).** It is a
*carry-propagating* function of the byte. The coverage rungs' `xor 0x51` is
bit-local; nothing about `rotl` is local in base 2 and nothing at all is local in
base 3, which is the only base the VM's `crazy` operates in.

**2. The 256-byte cap forces `K0 = 0`, which is the one thing that gets *better*.**
The cov40/cov48 dispatch is: `IN` gives `A = b`; two `CRZ`s against operands
`W1, W2 ≡ 364 (mod 729)` map every trit of `b` through `M1 = (1,0,2)` twice
(the identity, and the only injective row), leaving `v = b + K0` parked in a
cell; a `MOVD` on that cell sets `D = v` and the post-increment makes it `v+1`;
`k` `CRZ`s then walk `D` across cells `v+1 .. v+k`. `K0` is whatever the two
operands' trits 6..9 produce, i.e. a multiple of 729.

On the coverage rungs the table had to live at `K0 ∈ {729…3645}` *inside a
3000-byte program*, and the alphabet at each table address was fixed by
`address mod 94`. Here the program cannot reach address 729, so the only
reachable offset is `K0 = 0` — trits 6..9 of `b` are zero, `M[w](0) ∈ {1,2}`
never yields 0, so a single `CRZ` cannot do it, but two can:
`W1 = W2 = 364` gives `M[0](0) = 1` then `M[0](1) = 0`, and `v = b` exactly.

`K0 = 0` puts the table at addresses `1 .. 255+k` — i.e. **inside the program**,
where every cell is freely choosable (each address admits exactly 8 loader-valid
bytes, since 33..126 is 94 consecutive values and 8 of the 94 residues are ops).
That is strictly more freedom than cov48 had. It is still not enough.

## The exact ceiling

`dp.c`/`dp2.c` compute, for each depth `k`, the **exact maximum** number of the
256 inputs that

    out(b) = crazy(…crazy(crazy(b, t[b+1]), t[b+2])…, t[b+k]) mod 256  ==  rotl(b,1)

over *all* tables `t`. Consecutive inputs share `k-1` cells, so this is a
transfer-matrix DP with state = the last `k-1` cell choices (`8^(k-1)` states),
scoring input `b` at the moment cell `b+k` is fixed. Addresses ≥ 256 are not
choosable — they are the crazy-fill `m[i] = crazy(m[i-1], m[i-2])` — so the last
`k` inputs are scored against a forced continuation of each terminal state,
which the DP does exactly rather than approximating.

    k = 2  →  31/256
    k = 3  →  50/256
    k = 4  →  49/256
    k = 5  →  58/256
    k = 6  →  52/256
    k = 7  →  63/256

These are optima, not search results. **The table-dispatch family — the
architecture behind every solved coverage rung — cannot solve `rotate-1`, and
is not close: it is off by a factor of four.** Depth is non-monotone here just as
cov48 found for xor, but the counting reason it cannot climb to 256 is blunt:
the whole table is 255 cells × 3 bits = **765 bits of freedom**, and 256 inputs ×
8 output bits = **2048 bits of constraint**. More depth adds no freedom, only
more sharing. cov48's 71/256 for xor and this 63/256 for rotate are the same
number to within noise, which is the point — the ceiling is a property of the
architecture, not of the transform.

## What that means for the ladder

The coverage rungs and the full transforms are not the same problem at different
difficulties. A coverage rung asks for a fraction of a table; a full transform
asks for a *function*, and this VM gives you no way to spend more program bytes
on more coverage — the cap is 256 and the freedom is 765 bits no matter how you
arrange them. `rotate-1` therefore needs iterated computation: a loop, or an
unrolled carry chain, over the 2048-step budget. That is the wall, and it is a
different wall from the ones ranks 15–23 hit.

I did not get a candidate program built. The setup alone — placing `W1, W2 ≡ 364
(mod 729)` in cells reachable by a `MOVD` pointer — is nontrivial once the
cov32/cov48 trick of a long NOP-and-MOVD prefix is unaffordable. A pointer cell
is a program byte in 33..126, so `MOVD` can only aim `D` at addresses 34..127,
which means the operand cells must be *built in place* by alternating an op with
a `MOVD`-back through a cell at `X+1` holding `X-1` (loader-valid only when
`2X mod 94 ∈ {4,40,62,68}`, i.e. `X ≡ 2, 20, 31, 34 (mod 47)`). Since the DP had
already shown the architecture tops out at 63/256, building it would have
produced a program that fails ~75% of epochs — worth having as an artifact, but
not worth the remaining budget once the ceiling was known.

## Reproduce

```sh
cc -O2 -o research/rotate-1/dp2 research/rotate-1/dp2.c
for k in 2 3 4 5 6 7; do ./research/rotate-1/dp2 $k; done
```

`dp2` allocates a 94 × 59049 memo of `crazy`; `k = 7` runs in about a minute.
`k = 8` needs `8^7 = 2.1M` states and was not run.
