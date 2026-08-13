# Codex attempt: `L2.R0d.xor-1-len4096` (exact phase crossover)

Date: 2026-08-13

Outcome: **unsolved**. The native-verified champion remains **253/256**, at
2605 bytes with SHA-256
`38f593429e9ea02a07209e5ee9e732bcfccdac63845fd94a93d5c7c6df9c7a64`,
failing only inputs `0, 1, 3`.

This continuation attacked the architectural obstacle rather than extending
the champion's already-closed local neighborhood. It produced a new
native-verified 250/256 crossover that solves inputs 0 and 2 simultaneously:

```text
program: research/xor-1-len4096-codex/runs/round4-prolong-mask05-desc-o0.mal
length: 3451
sha256: f1f5442fd5a8d5a54fde460ef72ee4d28a045e3a20ab9326b89a1ff8ccfc1ea5
correct: 250/256
failures: [1, 3, 4, 10, 12, 154]
```

## Phase synthesis

The first pass of the known program reduces to an exact semantic contract:
after one input, two CRAZY operations, and eight rotations, the synthesized
prologue must have `A = m[72] = 9*b`, `m[71] = crazy(b,121)`, and `D = 72` at
the final jump. `prologue_phase_synth.c` enumerates loader-legal prefixes and
their data chains satisfying that contract, then evaluates their enciphered
second passes with a full Malbolge VM.

For prefix lengths 4 through 11, **13,759,711** exact candidates were fully
scored. The observed low-input masks were only `00`, `01`, `02`, `04`, `05`,
and `08`; no candidate solved input 0 together with input 1 or 3. The strongest
input-0 partner was mask `05` (inputs 0 and 2), scoring 202/256 before a
descending exact reconstruction raised it to the 250/256 tape above.

Length 12 adds **70,663,083** exact candidates. A targeted exhaustive pass
evaluated the complete low-input phase of every candidate and fully scored any
candidate that solved input 0 together with input 1 or 3. There were no such
candidates. Thus lengths 4 through 12 cover **84,422,794** exact semantic
prologues without producing the `0+1` or `0+3` compatibility needed by the
253-point champion. This is a proof about the enumerated one-IN,
MOVD/NOP-prefix family, not about arbitrary Malbolge prologues.

An alternate suffix reset chain was also derived and tested. After excluding
cells read by the prefix and enforcing loader legality, only 16 three-MOVD
detours remained. Their best raw score was 160/256 and reconstruction topped
out at 247/256, so that reset-chain family is closed.

A broader gadget enumeration then deliberately allowed the longer suffix to
overwrite prefix-consumed values, creating a genuinely different first-pass
dispatch rather than preserving the old semantic contract. Exhaustive paths
through ten MOVDs covered **14,648,568** loader-legal gadgets. Exactly two had
low mask `03`, solving inputs 0 and 1 together, and both were independently
native-verified at 2/256. Exact protected pair and triple coordinate ascent
raises the stronger qualifier to a native-verified 11/256:

```text
program: research/xor-1-len4096-codex/runs/round4-suffix-gadget-mask03-triple-0-63-r2.mal
length: 3451
sha256: 54659bdc8a1d27c062ebed2da3313dd0160fe87508eba36b219e9a8b1fea9fe4
correct: 11/256
successes: [0, 1, 6, 7, 22, 58, 81, 87, 213, 226, 232]
```

The complete protected one-cell neighborhood, all 398,272 shared-window
two-cell jobs, all 20,841,856 shared-to-downstream two-cell jobs, and all
117,091,968 shared-window three-cell jobs contain no further improvement from
that tape. The downstream/downstream two-cell partition was started but
stopped as computationally disproportionate and is not claimed complete.
When all 11 successful traces are frozen, a full-VM route search across all 14
branch orders reaches no mutable source cell on any failed execution before
termination. This new `0+1` basin therefore also requires joint, rather than
monotone per-input, reconstruction.

## Exact neighborhoods and bounded routes

On the 250-point crossover, exhaustive native-semantics scans found no
improvement among all 27,608 one-cell jobs and no improvement among all
21,240,128 legal two-cell jobs having at least one address in the shared
source window `0..127`. A further 10,350,711 requested pair jobs around the
input-154 trace cluster and its cross-product with the downstream tape also
found no improvement.

Trace-complete three-edit search can solve input 154 while preserving inputs 0
and 2. Reconstruction returns to 250/256, but moves the isolated high failure
from 154 to 155:

```text
program: research/xor-1-len4096-codex/runs/round4-prolong-mask05-b154-triple-desc-o5.mal
length: 3451
sha256: 8d2d547c3889ab1bc46adb7d1c41321de1c6d1994929fac021af36a95ec01ba2
correct: 250/256
failures: [1, 3, 4, 10, 12, 155]
```

The high failure is therefore movable; the persistent bottleneck is the
shared low phase. Exact and witness-capped route searches found no input-1,
input-3, or input-4 route compatible with both protected crossover inputs 0
and 2. Those route-family results are bounded evidence, not impossibility
proofs.

## M4 CPU and Metal assessment

The searches used 14 pthread workers, sustaining essentially all 14 logical
CPUs on the M4 Max. Metal is available (`Apple M4 Max`, 1024 maximum threads
per threadgroup, 32,768 bytes of threadgroup memory, approximately 30.15 GB
recommended working set). A single exact mutable Malbolge image is already
59,049 16-bit words, or 118,098 bytes, before its undo log. Candidate runs are
recursive-stateful and control-flow divergent. That image cannot reside in
threadgroup memory, while a sparse-overlay/global-memory GPU design would add
indirection and severe divergence. The CPU implementation was consequently
the effective accelerator for these exact searches; no Metal port was used.

## Reproduction

```sh
./target/release/malbolge-rungs verify \
  --rung L2.R0d.xor-1-len4096 \
  --program research/xor-1-len4096-codex/runs/round2-route9-desc-r0-o0.mal \
  --epochs 256 --json

./target/release/malbolge-rungs verify \
  --rung L2.R0d.xor-1-len4096 \
  --program research/xor-1-len4096-codex/runs/round4-prolong-mask05-desc-o0.mal \
  --epochs 256 --json
```

The retained champion is submitted as `best_candidate`; the crossover tapes
and exact-search programs are supporting artifacts for the next attempt.
