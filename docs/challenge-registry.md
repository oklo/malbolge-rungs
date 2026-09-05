# Challenge registry

The canonical evaluator contracts are in
[`crates/harness/registry.json`](../crates/harness/registry.json).
The [live API](https://oklo.github.io/malbolge-rungs/api/registry.json) publishes
the same data. Inspect any exact contract with:

```sh
malbolge-rungs registry show --rung L2.R0.xor-1
```

Display rank, names, difficulty groups, and placement rationales live separately
in `leaderboard/leaderboard.json` and `leaderboard/ladder.json`. The historical
L0–L6 ID prefixes remain reference names, not the current ordering rule.
See [the methodology](ladder-methodology.md).

## Families and verification scope

| Family | Required behavior | Scope |
|---|---|---|
| EchoPrefix | Copy a fixed input prefix and halt | Public deterministic examples |
| FiniteMap | Transform each listed byte and halt | Complete listed input domain |
| CoverageTransform | Transform at least the threshold number of bytes and halt on correct cases | All 256 one-byte inputs |
| Transform | Transform a fixed prefix and halt | First-byte sweeps where declared; suffixes remain public samples |
| HashPrefix | Emit target bytes derived from seed, input, and case index | Fixed public lookup rows; the seed is not supplied to the program |
| Stream | Transform the entire input and halt | Public variable-length suite; no proof of iteration or unseen-input generalization |

Transforms include identity, reverse, XOR 0x51, crazy-mask, binary rotate-left,
and nibble swap. Stream length and checksum emit one byte. The implementation
in [`challenge.rs`](../crates/harness/src/challenge.rs) defines exact behavior.

Only the native VM decides a pass. Required epochs are enforced by the verifier.
First-byte sweeps cover every first byte for each case; they do not exhaust
all multi-byte tuples or all possible suffixes. Finite maps and coverage are
seed-independent, so repeated epochs do not create new inputs.

## Interpretation of scores

Non-coverage rungs require exact output and halt on every required case.
Coverage rungs allow failures elsewhere and require a threshold of correct
cases. Attempt records aggregate all epochs for first-byte sweeps; for other
multi-epoch families they report the worst epoch. See the detailed native JSON
for per-case evidence.

## Contract revisions

Presentation changes preserve evaluator contracts. Prefer additive successor
IDs for changed limits or test distributions. Historical contracts have been
repaired; records carry `rung_digest` to distinguish contract drift from failure.
Any necessary repair must be explicit in repository history and affected
claims must be reverified. Do not silently grandfather a claim into a changed
test contract. Hash domain strings are protocol constants.

This revision adds only three XOR compression contracts, with source caps
2,048, 1,024, and 512 bytes. Existing contracts are unchanged. Intermediate
streaming tasks remain a pilot recommendation, not calibrated board entries.

## Generating tasks

`generate-rung` produces finite-map and coverage instances loadable by
`verify --rung-file`. See [ENVIRONMENT.md](../ENVIRONMENT.md) for reproducibility,
private instance handling, reward definitions, and the reporting protocol.
