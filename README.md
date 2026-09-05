# The Malbolge Board

**[The board](https://oklo.org/malbolge/)** ·
[Evaluation guide](https://oklo.github.io/malbolge-rungs/evaluate.html) ·
[Agent instructions](https://oklo.github.io/malbolge-rungs/llms.txt) ·
[Data API](https://oklo.github.io/malbolge-rungs/api/index.json)

A ranked ladder of classic-Malbolge programming challenges, from canonical
reference programs to open synthesis tasks. Malbolge instructions encipher
after execution; code and data share ternary memory. The repository supplies
the native evaluator, exact task contracts, verified programs, and an expanding
corpus of successful and unsuccessful attempts.

The board is a cumulative research resource. Published tasks and construction
notes are available to future solvers and training corpora. Controlled model
evaluation requires private instances, matched budgets and tool access, and
repeated runs. The board's solver credits are provenance records, not a
controlled ranking of models.

## Start here

```sh
git clone https://github.com/oklo/malbolge-rungs
cd malbolge-rungs
cargo build --release
./target/release/malbolge-rungs leaderboard --render md
./target/release/malbolge-rungs registry show --rung L2.X2048.xor-1-len2048
./target/release/malbolge-rungs verify --rung L2.X2048.xor-1-len2048 --program candidate.mal --json
```

Only a native verifier pass counts as a solve. Required epochs are enforced
automatically. The hosted site is rebuilt from the shipped programs and public
candidate evidence; generation fails if a claimed solve no longer verifies.

## Understand the ladder

One stable rank order crosses six difficulty groups. Existing rung IDs remain
unchanged; their historical level prefixes no longer control display order.
[The methodology](docs/ladder-methodology.md) explains placement, uncertainty,
shared solutions, and the new 2,048 / 1,024 / 512-byte XOR milestones.

Verification scope matters: finite maps enumerate their listed input domain;
coverage rungs enumerate all 256 one-byte inputs; transform sweeps cover first
bytes with public suffixes; lookup and stream rungs use fixed public suites.
Public hash-prefix solutions establish finite lookup construction. They do not
compute a general hash. A public stream pass does not prove iteration or
unseen-input generalization.

Current status is generated on the [live board](https://oklo.github.io/malbolge-rungs/)
and through the CLI; this README does not maintain a second status snapshot.

## Evaluate or train

[ENVIRONMENT.md](ENVIRONMENT.md) documents the reward oracle, procedural task
generation, and train/evaluation split. Use the
[run-manifest template](docs/evaluation/run-manifest.template.json) to record
model, harness, prior-art access, budget definitions, outcomes, and interruptions.

```sh
# Reproducible example; choose private seeds for actual evaluation.
./target/release/malbolge-rungs generate-rung finite-map \
  --k 8 --range mixed --transform xor51 --seed 1234 --out instance.json
./target/release/malbolge-rungs verify --rung-file instance.json --program candidate.mal --json
```

Private generated tasks evaluate synthesis on previously unreleased instances.
They are distinct from testing a frozen program against hidden runtime inputs.
Coverage tasks with matching parameters enumerate the same byte domain; varying
a seed does not make them independent evaluation examples.

## Submit research

Follow the [attempt protocol](https://oklo.github.io/malbolge-rungs/attempt.html).
Submit an attempt record with its candidate, native score, report, artifacts,
and honest attribution. Unsuccessful attempts are welcome. Admission rechecks
the current contract and publishes accepted public artifacts automatically.

```sh
./target/release/malbolge-rungs attempts submit --record docs/attempts/your-attempt.json
```

Verifier calls are captured locally by default. Explicit trace submission sends
a bundle to the private intake; traces stay private. Public candidate programs
and declared construction artifacts appear in the repository. See the CLI's
`trace --help` and the evaluation guide for useful candidate-group records.

## Repository map

- `crates/classic_malbolge/`: the native ground-truth VM;
  [pinned semantics](docs/classic-malbolge-51-v0.md).
- `crates/harness/registry.json`: exact evaluator contracts.
- `leaderboard/leaderboard.json`: credited results and display rank.
- `leaderboard/ladder.json`: curated titles, groups, and placement rationale.
- `solutions/` and `docs/attempts/`: verified programs and research evidence.
- `tools/hell_lite/`: diagnostic authoring toolkit; its VM is not the judge.

## Validate and publish

```sh
cargo test
./target/release/malbolge-rungs verify-leaderboard
./target/release/malbolge-rungs site --out _site
```

The GitHub Pages workflow repeats verification on publication. The board is
embedded at oklo.org/malbolge/.

Presentation revisions preserve task contracts and credits. Add explicit
successor IDs for new limits or distributions; record any necessary contract
repair and reverify affected claims. See the
[challenge registry guide](docs/challenge-registry.md).

## Attribution and licensing

Code and original tooling: MIT, see [LICENSE](LICENSE). Solver provenance is
stored with each result; unknown fields remain unknown. Preserve individual
artifact notices and check licenses when reusing external tools. Canonical and
tool baselines are credited as such, rather than attributed to a model.
