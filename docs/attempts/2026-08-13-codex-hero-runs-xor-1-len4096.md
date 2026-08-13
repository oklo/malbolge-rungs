# Codex attempt: `L2.R0d.xor-1-len4096` (phase alignment and a 253/256 reconstruction)

Date: 2026-08-13

Outcome: **unsolved**. The new best candidate is correct on **253 of 256** input
bytes under an exhaustive native run. It is 2605 bytes long, has SHA-256
`38f593429e9ea02a07209e5ee9e732bcfccdac63845fd94a93d5c7c6df9c7a64`,
and fails only inputs `0, 1, 3`.

Candidate:
[`research/xor-1-len4096-codex/runs/round2-route9-desc-r0-o0.mal`](../../research/xor-1-len4096-codex/runs/round2-route9-desc-r0-o0.mal)

Artifacts:
[`research/xor-1-len4096-codex/`](../../research/xor-1-len4096-codex/)

## What changed

The inherited hero1 and hero3 candidates both covered 249/256, but on different
prologues and with different misses:

| candidate | native score | failures |
|---|---:|---|
| hero1 | 249/256 | `0 1 3 8 9 151 255` |
| hero3 | 249/256 | `0 1 3 4 8 9 255` |

The first pass found phase-aligned extensions. An exhaustive scan of every
program length from 2305 through 4096 and every legal pair of final opcodes
found lengths that preserve all 249 hero1 successes. Length 2605 provides
writable extension space without paying the expected tail-reader penalty.

That enabled three exact constructions:

1. Route byte 255 into the extension, then repair byte 254 with the byte-255
   trace frozen: 250/256.
2. Exactly cross the coupled byte-150 and byte-151 witness families: 251/256,
   failing `0 1 3 8 9`.
3. Use route-then-reconstruct steps for bytes 8, 11, and 9. The byte-8 route
   initially displaces byte 11; solving 11 under a frozen byte-8 trace reaches
   252/256. A byte-9 route followed by reconstruction with 8, 9, and 11 frozen
   reaches 253/256 without losing another success.

The last construction is not a sequence of greedy patches. Each raw low-byte
route is allowed to damage other inputs; a descending reconstruction then
restores those inputs while treating the new route as fixed. Twelve variants
of the final reconstruction reached 253/256, and multiple variants agreed with
the canonical evaluator.

## Native verification

```text
program_len: 2605
sha256: 38f593429e9ea02a07209e5ee9e732bcfccdac63845fd94a93d5c7c6df9c7a64
correct: 253
failures: [0, 1, 3]
```

Reproduction command:

```sh
./target/release/malbolge-rungs verify \
  --rung L2.R0d.xor-1-len4096 \
  --program research/xor-1-len4096-codex/runs/round2-route9-desc-r0-o0.mal \
  --epochs 256 --json |
jq '{program:.results[0].program,
     program_len:.results[0].program_len,
     sha256:.results[0].program_sha256,
     correct:([.results[0].outcome.epochs[]|select(.passed)]|length),
     failures:[.results[0].outcome.epochs[]|select(.passed|not)|.epoch]}'
```

## Four-hour continuation: closing the local neighborhoods

The continuation began from the native 253/256 tape and concentrated on
inputs `0`, `1`, and `3`. The champion did not move, but the search produced
stronger exact evidence and, importantly, a tape that solves inputs 1 and 3
simultaneously.

The exact legal-source searches established the following:

| seed / constraint | exhaustive result |
|---|---|
| 253 champion, one edit | no repair of input 1 or 3 |
| 253 champion, two edits | exact local maximum overall; unique input-1 repair at cells 66 and 100 scores 209/256; no input-3 repair |
| 253 champion, three edits | best input-1 repair 242/256; best input-3 repair 234/256 |
| reconstructed joint 249 basin | exact two-edit local maximum while inputs 1 and 3 remain solved |
| raw joint four-edit basin | pair-coordinate ascent `231 -> 232 -> 233 -> 234`, then an exact two-edit fixed point |

Reconstructing the best input-1 triple reaches 251/256 with failures
`0 3 8 10 145`. Attempts to add input 3 by an exact fourth edit, subsequent
two-cell ascent, route search, and monotone reconstruction all return to a
249/256 attractor. A separate exact triple at the residual input 145 reaches
250/256 but replaces it with adjacent failures 144 and 146.

The complementary five-edit partition succeeds jointly. Starting with the
unique exact two-edit repair for input 1 and then applying an exact three-edit
repair for input 3 gives a native 192/256 tape with both inputs solved.
Descending reconstruction with semantic locks on 1 and 3 reaches 246/256,
failing `0 2 7 8 9 11 13 14 144 154`. All eight DFS orders reach the same
failure set, and an exhaustive two-cell rescan finds no admissible improvement.
An exact input-144 triple followed by reconstruction changes the high-byte
boundary but remains at 246/256. These tapes are retained as
`round3-pair-b1-plus-triple-b3.mal` and
`round3-exact-joint13-desc-o0.mal` in the research run ledger.

The byte-0 side was also tightened. Exhaustive prologue scans tested all 4,096
legal width-four prefixes, all width-five prefixes, all width-six and
width-seven suffixes beginning at source cell 1, and all 26,103 legal sparse
one- and two-cell edits across the 33-byte prologue. The original width-four
prefix is the only tested one retaining 253/256. Six sparse prologue edits make
input 0 succeed, but the best such program scores only 1/256. On the inherited
hero2 architecture, corrected exact routing solves input 0 at 121/256 and
the first monotone reconstruction reaches 206/256. An exhaustive protected
two-cell coordinate ascent then improves that tape through 207, 208, 209, and
210/256, where a complete rescan is empty. Feeding the 210 tape back through
the corrected descending reconstruction reaches a native-verified 239/256
while retaining input 0, failing
`1 3 4 5 8 9 10 11 12 13 14 15 16 27 252 254 255`. This is still below the
old-prologue champion, but it closes most of the previous architectural gap and
leaves a concrete byte-0-compatible continuation artifact.

The same architecture can also retain inputs 0 and 1 simultaneously. A
14-cell input-1 route initially scores 115/256; descending reconstruction with
semantic locks on both inputs reaches a native-verified 235/256 tape, failing
`3 4 5 6 7 8 9 10 11 12 13 14 15 16 133 147 159 177 241 252 255`. An
exhaustive protected Hamming-2 scan of 23,479,869 legal pairs finds no
improvement. Thus the low-input compatibility is constructive, but the
resulting basin remains four successes below the input-0-only hero2 tape.

An exact three-cell input-1 witness is less destructive: it retains 209/256
before reconstruction and reaches a native-verified 237/256 afterward, failing
`3 4 5 8 9 10 11 12 13 14 15 16 144 145 146 235 252 254 255`. A further
exhaustive protected scan of 22,037,496 legal two-cell edits is empty. This is
the strongest retained tape known to solve both inputs 0 and 1, but the input-3
and shared low-byte cluster still prevent it from surpassing 239/256.

The practical conclusion is sharper than before: 253/256 is not just the best
sample encountered. It is an exact legal Hamming-2 local maximum, nearby
input-1 and input-3 repairs lie in measured reconstruction attractors, and the
remaining input-0 requirement demands an architectural crossover.

## Negative results and limits of the claims

The remaining failures need qualitatively different work.

- Byte 0 is unreachable under the champion's fixed old prologue. Protecting a
  byte-0 trace on the alternate prologue and rebuilding the rest reached only
  227/256. A full solution must cross architectures, not locally edit this
  champion.
- Directly freezing every solved trace leaves only one mutable cell for byte 1
  and no safe witness. Wide byte-1 routes exist, but protected reconstruction
  topped out at 250/256. Forcing each legal opcode at its principal shared
  address did not improve that result.
- Byte 3 traverses the common byte-8/9 machinery and emits an unwanted second
  byte. Wide routes were substantially destructive; their reconstructions did
  not approach 253.
- On the earlier 251 tape, exact enumeration found 529 byte-8 and 13,542 byte-9
  witnesses, with 3,298 compatible pairs. The best pair solved only 12 of the
  18 low inputs, explaining why the successful path needed an intervening
  byte-11 reconstruction.
- On the 253 tape, hashed crossings of the exact byte-8/9 families with wide
  byte-1 and byte-3 route families found no compatible triple in the tested DFS
  rotations. Several families exhausted their configured 65,536-witness cap;
  others hit their node cap. This is strong bounded negative evidence, not an
  impossibility proof.
- A direct byte-1/byte-3 crossing covered all 64 pairs of DFS branch-order
  rotations. Every pair had zero hash-compatible signatures among its sampled
  families; most reached 65,536 witnesses and the rest reached the
  three-billion-node cap. The routes disagree before reconstruction can begin.
- Diversified annealing, sweep-style search, and semantically protected
  reconstruction from byte-1 and byte-3 route basins did not exceed 253/256.
- Transplanting the champion delta onto phase-compatible tapes of lengths 2887
  and 3451 retained 253/256. A swapped, byte-0-reachable prologue assembled
  around the downstream structure reached 231/256, an improvement over the
  separate 227/256 rebuild but not a competitive crossover.
- Length 3451 makes the address near 3268 available as private code. Exact
  input-1 searches across all eight branch-order rotations reached that
  extension. The best raw witness changed 78 source cells and retained 59/256;
  both facts were confirmed natively. A bounded descending reconstruction
  reached 131/256 in the surrogate, but the native evaluator scored 130/256
  and showed that input 1 had been lost despite the surrogate trace lock. Thus
  the private-code route exists, but entering it perturbs much more of the
  shared computation than the final output stub itself suggests, and this
  longer-tape reconstruction needs native checking at every milestone.

## Structural conclusion

Stride 9 is forced under the 4096-byte cap, but extension is not inherently
fatal: the memory-fill recurrence has phase-aligned lengths, and those lengths
unlock byte 255. The old-prologue line now solves every input except 0, 1, and
3, but byte 0 cannot execute under that prologue. The most plausible remaining
direction is therefore a joint prologue/shared-window synthesis that imports
the 253 tape's downstream structure into a byte-0-reachable architecture. The
longer-tape experiment also leaves a concrete secondary direction: synthesize
the input-1 path and its private extension jointly, instead of routing first
and attempting to reconstruct nearly the whole shared program afterward.

## Reproducibility notes

Exact build commands, intermediate candidates, and the tool index are in the
research [continuation index](../../research/xor-1-len4096-codex/CONTINUATION-253.md).
Search notes distinguish exhaustive enumeration from node- or witness-capped
evidence.

The structured attempt record names the champion as `best_candidate` with a
contract score of 253/256. For this rung, that means the evaluator-owned
aggregate over the complete 256-epoch first-byte sweep—not the `0/1` or `1/1`
score of an individual epoch. Admission repeats that complete sweep before the
score can appear on the board.
