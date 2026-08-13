# Codex solve: `L2.R0d.xor-1-len4096`

Date: 2026-08-13

Outcome: **solved, 256/256**.

```text
program: solutions/xor-1-len4096/xor-256-gpt-5.6-sol.mal
length: 4096 bytes
sha256: fe2bea8bb173005f7d5a5f30589b20877dbef3cb9b1a5535e0f43f64df35e58f
steps: 604..616
output: exactly one byte on every input
```

The canonical Rust evaluator exhaustively passes all 256 epochs:

```sh
./target/release/malbolge-rungs verify \
  --rung L2.R0d.xor-1-len4096 \
  --program solutions/xor-1-len4096/xor-256-gpt-5.6-sol.mal \
  --epochs 256 --json
```

## The structural turn

The productive correction was to stop treating the task as “XOR 1.”  The
required transform is XOR with `0x51`, and

```text
0x51 = 81 = 3^4,
b xor 81 = b + 81 - 2*(b & 81).
```

Thus a Boolean involution is aligned with one exact radix place of Malbolge's
ternary word.  The prior straight-line CRAZY/ROT analysis had a ceiling of only
34 inputs, so the missing ingredient had to be control and layout rather than
another output formula.

The key construction is an exact six-CRAZY circuit.  With rotated input copies
`x=9b` and `y=27b`, and constants

```text
K1=52496, K2=54683, K3=3645, K4=3276,
```

it evaluates

```text
a = CRAZY(x,K1)
r = CRAZY(y,K2)
c = CRAZY(r,K3)
d = CRAZY(a,c)
e = CRAZY(d,x)
q = CRAZY(e,K4) = 9*(b+81).
```

The map is injective on all 256 bytes.  Jumping to `q` enters `C=q+1`, and the
private blocks `q+1..q+9` occupy exactly 730..3033.  They neither collide with
one another nor alias the prologue.  What looked like an adversarial global
self-modifying program becomes 256 mostly independent finite synthesis
problems.

This style is related to the historical view of Malbolge programs as compiled
ternary circuits rather than handwritten instruction streams.  Scheffer's
[Malbolge page](https://www.lscheffer.com/malbolge.shtml), Lutter's
[Malbolge assembler](https://lutter.cc/malbolge/assembler.html), and Nagoya's
[LAL description](https://www.trs.css.i.nagoya-u.ac.jp/projects/Malbolge/lal/lal-def.html.en)
provide the relevant compiler tradition.  The circuit and layout here are new
to this attempt.

## Phase, involution, and the last obstruction

Exact synthesis over block-entry data pointers found a sharp phase effect.  In
the favorable low-memory geometry, entering a block with `D=42` solves 250
blocks independently; `D=43` solves only 245.  The raw dispatcher naturally
entered with 43.

The `K4` transformation is an involution on the circuit image:

```text
e --K4--> q --K4--> e.
```

Two additional K4 cells therefore implement a three-step echo that leaves
`q` in both cells 41 and 42.  Jumping through cell 41 enters the block with
`D=42` while retaining `m[42]=q`, exactly matching the favorable hypothetical
phase.

Five of the six exceptions in that phase could jump to unused high source and
were solved by disjoint continuations.  Input 216 was sealed: exhaustive
nine-cell synthesis found neither a local solution nor any high exit.  An
18-cell overlap could solve it only by halting on input 217's first cell, so a
joint boundary search moved the failure rather than removing it.

The decisive change was a second ternary coincidence already latent in the
prologue:

```text
CRAZY(26248,55) = 3303.
```

The epilogue rotates the persistent 26248 register through one full cycle,
writes 3303 to cell 120, and deliberately leaves `A=3303` at dispatch.  This
new accumulator phase solves 251/256 independent blocks, including 216.  Its
five failures—117, 153, 180, 205, and 250—all have high-memory exits.  Exact
joint synthesis assigns them disjoint 27-cell tails at 3160, 3196, 3232, 3279,
and 3331.  Those five witnesses compose with the 251 local witnesses to give
256/256.

## Search discipline and compute

The attempt was capped at eight hours and solved after about two hours of wall
time.  Computation followed the mathematical reductions:

1. prove and exhaustively test the dispatcher circuit;
2. scan the finite block-entry phase space;
3. synthesize independent nine-cell blocks in parallel;
4. inspect only the exact residual exit sets;
5. synthesize five disjoint tails.

The branch-heavy mutable VM search used parallel optimized C processes across
the M4 CPU.  The previously measured Metal constraint remains unfavorable: a
single exact Malbolge memory image is 59,049 16-bit words (118,098 bytes), well
above the 32 KiB threadgroup-memory limit measured on this machine, and the
recursive paths are highly divergent.  GPU work was therefore not the useful
accelerator; changing the state factorization was.

## Reproducible artifacts

- `solutions/xor-1-len4096/xor-256-gpt-5.6-sol.mal`
- `research/xor-1-len4096-profound/PROCESS.md`
- `research/xor-1-len4096-profound/build_shifted_dispatch.py`
- `research/xor-1-len4096-profound/retarget_old_dispatch.py`
- `research/xor-1-len4096-profound/shifted_block_solve.c`
- `research/xor-1-len4096-profound/shifted_tail_solve.c`
- `research/xor-1-len4096-profound/b217_suffix_scan.c`
- `research/xor-1-len4096-profound/README.md`

The final tape is the native-verified program named at the top of this report.
The builders and solvers preserve the decisive construction stages; the process
memory records their order, the discarded architectures, and the phase changes.
They are research tools rather than a packaged deterministic one-command rebuild.
