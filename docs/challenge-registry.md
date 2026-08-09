# MAL-51 Challenge Registry

The MAL-51 rung ladder is a fixed set of classic-Malbolge programming challenges
of increasing difficulty. Each **rung** defines a challenge *family*, a per-byte
*transform*, a number of *cases*, resource limits, and (for some families) a
list of input bytes or a coverage threshold.

The canonical machine-readable ladder is
[`crates/harness/registry.json`](../crates/harness/registry.json). Published
rung definitions are frozen — families, transforms, inputs, thresholds, and
resource limits never change once a rung is on the board — and additions
(map7a, map7b, cov36, cov40, cov48) are only ever additive, marked as such in
their `purpose` fields. The harness loads the file directly.

Beyond the fixed ladder, `malbolge-rungs generate-rung` mints unlimited
procedural instances in the seed-independent families (FiniteMap,
CoverageTransform) using the same JSON schema; see
[ENVIRONMENT.md](../ENVIRONMENT.md).

## Challenge families

A rung's **family** determines how each case's input and expected output are
derived (see [`crates/harness/src/challenge.rs`](../crates/harness/src/challenge.rs)):

- **EchoPrefix** — expected output is the first `output_bytes` of the input.
  The program must echo. Inputs are hash-derived per case.
- **HashPrefix** — expected output is `SHA-256(seed, input, index)` truncated to
  `output_bytes`. Inputs are hash-derived per case.
- **Transform** — expected output is `transform(prefix)`. Inputs are hash-derived
  per case, so the program must handle an unpredictable input byte (constant
  output does not pass).
- **FiniteMap** — inputs are a fixed list of bytes; expected output is
  `transform(byte)` for each. Seed-independent.
- **CoverageTransform** — cases enumerate all 256 input bytes in order; a rung
  passes when at least `min_correct_cases` cases produce the correct
  `transform(byte)`. Seed-independent. This turns partial generality into a
  deterministic, measurable rung.

## Transforms

- **Identity** — `b`
- **Reverse** — reverse the byte sequence
- **XorMask** — `b XOR 0x51`
- **CrazyMask** — `crazy(b, 0x51) mod 256`, using the classic-Malbolge crazy
  operation (per-trit, so it tests totality over 256 without XOR's carry
  obstruction)
- **RotateLeft** — `b.rotate_left(1)`
- **NibbleMap** — swap nibbles: `(b << 4) | (b >> 4)`

## The verification rule

The harness runs a candidate program on the native VM once per case and applies
the rung's rule (see [`crates/harness/src/verify.rs`](../crates/harness/src/verify.rs)):

- **Non-coverage rungs**: every case must *halt* (native) and produce the exact
  expected output. Any mismatch or non-halt fails the rung.
- **Coverage rungs**: a case counts as correct when it halts (or succeeds) with
  the exact expected output; per-case runtime failures are tolerated. The rung
  passes when the number of correct cases reaches `min_correct_cases`.

Only the native evaluator counts. The hell_lite Python VM is diagnostic-only.

## Seeds and reproducibility

The per-case challenge seed derives deterministically from the rung id and an
epoch index, making verification reproducible and re-runnable anywhere. The
seed only affects the hash-derived inputs of the `EchoPrefix`, `HashPrefix`,
and `Transform` families; `FiniteMap` and `CoverageTransform` inputs are
seed-independent. The hash domain strings in the harness are frozen protocol
constants — their exact bytes define the derived cases.
Running several epochs (`--epochs N`) exercises several seeds, guarding
echo/transform checks against single-input overfitting.

## The ladder

| Rung | Level | Family | Transform | Cases | Max program | Notes |
|------|-------|--------|-----------|-------|-------------|-------|
| `L0.R0.hello-world` | 0 | EchoPrefix | Identity | 1 | 256 | 0-byte output slot |
| `L0.R1.echo-1-demo` | 0 | EchoPrefix | Identity | 1 | 64 | |
| `L1.R0.echo-1` | 1 | EchoPrefix | Identity | 1 | 64 | |
| `L1.R1.echo-2` | 1 | EchoPrefix | Identity | 1 | 128 | |
| `L1.R2.echo-4` | 1 | EchoPrefix | Identity | 1 | 256 | |
| `L1.R3.echo-2-multicase` | 1 | EchoPrefix | Identity | 2 | 256 | |
| `L2.R0.xor-1` | 2 | Transform | XorMask | 1 | 256 | general single-byte XOR |
| `L2.R0d.xor-1-len4096` | 2 | Transform | XorMask | 1 | 4096 | XOR, relaxed length cap |
| `L2.R0c.crazy-mask-1` | 2 | Transform | CrazyMask | 1 | 512 | |
| `L2.FM0.xor51-map2` | 2 | FiniteMap | XorMask | 2 | 512 | inputs 02,06 |
| `L2.FM1.xor51-map4` | 2 | FiniteMap | XorMask | 4 | 1024 | inputs 02,06,09,30 |
| `L2.FM1b.xor51-map6` | 2 | FiniteMap | XorMask | 6 | 1536 | inputs 02,06,09,30,82,6f |
| `L2.FM1c.xor51-map7a` | 2 | FiniteMap | XorMask | 7 | 1792 | map8 minus 0xc0 |
| `L2.FM1d.xor51-map7b` | 2 | FiniteMap | XorMask | 7 | 1792 | map8 minus 0xa7 |
| `L2.FM2.xor51-map8` | 2 | FiniteMap | XorMask | 8 | 2048 | 8 inputs |
| `L2.FM2h.xor51-map12-hi` | 2 | FiniteMap | XorMask | 12 | 4096 | 12 high-byte inputs |
| `L2.FM2l.xor51-map12-low` | 2 | FiniteMap | XorMask | 12 | 4096 | 12 low-byte inputs |
| `L2.FM3.xor51-map16` | 2 | FiniteMap | XorMask | 16 | 4096 | 16 inputs |
| `L2.C0.xor51-cov32` | 2 | CoverageTransform | XorMask | 256 | 4096 | ≥ 32/256 correct |
| `L2.C0b.xor51-cov36` | 2 | CoverageTransform | XorMask | 256 | 4096 | ≥ 36/256 correct |
| `L2.C0c.xor51-cov40` | 2 | CoverageTransform | XorMask | 256 | 4096 | ≥ 40/256 correct |
| `L2.C0d.xor51-cov48` | 2 | CoverageTransform | XorMask | 256 | 4096 | ≥ 48/256 correct |
| `L2.C1.xor51-cov64` | 2 | CoverageTransform | XorMask | 256 | 4096 | ≥ 64/256 correct |
| `L2.R1.reverse-1` | 2 | Transform | Reverse | 1 | 256 | |
| `L2.R2.rotate-1` | 2 | Transform | RotateLeft | 1 | 256 | |
| `L2.R3.xor-2-multicase` | 2 | Transform | XorMask | 2 | 384 | |
| `L3.R0.reverse-2-multicase` | 3 | Transform | Reverse | 3 | 512 | |
| `L3.R1.xor-4-length-cap` | 3 | Transform | XorMask | 2 | 256 | |
| `L3.R2.mixed-transform-small` | 3 | Transform | NibbleMap | 3 | 512 | |
| `L4.R0.hash-prefix-1` | 4 | HashPrefix | Identity | 1 | 1024 | |
| `L4.R1.hash-prefix-1-multicase` | 4 | HashPrefix | Identity | 3 | 1024 | |
| `L4.R2.hash-prefix-length-pressure` | 4 | HashPrefix | Identity | 2 | 256 | |
| `L5.R0.future-transform` | 5 | Transform | NibbleMap | 4 | 1024 | |
| `L5.R1.future-hash-prefix` | 5 | HashPrefix | Identity | 4 | 2048 | |

The finite-map input bytes and exact resource limits for every rung are in
`registry.json`; `malbolge-rungs registry show --rung <id>` prints them.

## Difficulty landscape

The finite-map rungs (FM0 → FM1 → FM1b → map7a/map7b → FM2 → FM3) and the
coverage rungs (cov32 → cov64) form a measurable ladder between "solvable small
finite map" and "general byte-wide XOR". Empirically:

- **FM0 / FM1 / FM1b (map6)** are solved (see the leaderboard). map6 required a
  two-stage dispatch; single-dispatch constructions cap at 3 of its 6 lanes.
- **map7a and map7b** split the map6→map8 difficulty cliff into measured steps.
  The measure is dispatch feasibility — how many prelude configurations give
  every input a distinct landing address (`malbolge-rungs feasibility`): map6
  admits 1,261 separating configs, map7a 539, map7b 50, map8 39, and the
  map12-low/map16 input sets zero (that dispatch family cannot separate them at
  all).
- **map8** is solved by a four-CRAZY, two-stage dispatch with one extra station
  split inside the high landing cluster. A zero-split sweep found no joint
  eight-lane byte assignment even though all 39 preludes separate the inputs;
  landing separation is therefore a useful but incomplete difficulty proxy.
- **General single-byte XOR** (`L2.R0.xor-1`, `L2.R0d`) is an open frontier; the
  coverage rungs make partial progress measurable in graded steps
  (32/36/40/48/64; best known all-256 coverage is 27).

See [`docs/classic-malbolge-51-v0.md`](classic-malbolge-51-v0.md) for the pinned
VM semantics that make all of this deterministic.
