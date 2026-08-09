# Using the rungs as a training / evaluation environment

This repo is usable directly as a verifiable environment for reinforcement
learning and model evaluation: deterministic binary reward from a native VM,
procedural instance generation with a difficulty estimator, graded
partial-credit variants for reward shaping, sub-millisecond episodes, and a
domain with essentially no pretraining corpus. This page is the contract; it is
written for the engineer wiring the harness into a training loop, not for
Malbolge enthusiasts.

## Why this domain

Malbolge programs cannot be imitated from training data — the total public
corpus of working programs is a few dozen specimens, most of them machine-found.
Producing one requires reasoning about an adversarial machine (self-enciphering
instructions, code/data co-advancement, a lossy ternary operation) from first
principles. The same scarcity that makes it a good benchmark makes it a good RL
domain: reward can only be earned by constructing a working program, and the
checker cannot be gamed — it runs the program.

## The reward oracle

```sh
cargo build --release
./target/release/malbolge-rungs verify --rung <id> --program <file> [--epochs N] [--json]
```

- **Exit code** 0 iff the rung passed (all epochs, all programs). Usable as a
  binary reward with no parsing.
- **`--json`** emits a stable envelope, schema `malbolge-rungs.verify.v1`:

```
{
  "schema": "malbolge-rungs.verify.v1",
  "rung_id": ...,
  "epochs": N,
  "all_passed": bool,
  "results": [
    {
      "program": path, "program_sha256": hex, "program_len": bytes,
      "outcome": {
        "rung_id": ..., "passed": bool,
        "coverage": bool, "required_correct": u32,
        "epochs": [
          { "epoch": u32, "seed_hex": ..., "passed": bool,
            "correct_cases": u32, "total_cases": u32,
            "failure": string|null,
            "cases": [ { "index", "input_hex", "expected_hex",
                         "observed_hex", "status", "correct" } ] }
        ]
      }
    }
  ]
}
```

- **Graded reward**: `correct_cases / total_cases` is meaningful on every rung
  and is the intended shaped reward on coverage rungs, where per-case failures
  are tolerated and the rung passes at `required_correct`.
- **Batch mode**: repeat `--program` to score several candidates in one
  invocation (one process launch, one JSON envelope).
- **Raw execution**: `malbolge-rungs execute --program <file> --input-hex <hex>`
  runs the VM once and prints JSON (`output_hex`, `steps`, `status`) — the
  low-level probe for building custom scoring on top of the same ground truth.

Field additions to these JSON envelopes may happen; field removals or meaning
changes will bump the schema tag.

## Determinism

- Every case runs on a **fresh VM** with pinned semantics
  ([docs/classic-malbolge-51-v0.md](docs/classic-malbolge-51-v0.md)). No state
  survives between cases; verdicts are bit-reproducible across machines.
- **FiniteMap** and **CoverageTransform** rungs derive their cases from the
  rung definition alone — no seed enters. One epoch is sufficient; extra epochs
  re-confirm the same cases.
- **Transform / EchoPrefix / HashPrefix** rungs hash their inputs from
  `SHA-256(domain, rung_id, epoch)`, so a program must handle unpredictable
  bytes; `--epochs N` sweeps N distinct deterministic seeds. Constant-output
  overfits do not pass.
- The native Rust evaluator is the **only** ground truth. The Python VM in
  `tools/hell_lite/` is a diagnostic aid for authoring and must never be used
  for scoring.

## Episode cost

Measured on a laptop (Apple silicon, release build): a one-case rung verifies
in well under a millisecond of compute; a full 256-case coverage episode,
process startup included, completes in under 200 ms. Step caps (typically 2048
steps/case) bound the worst case, so a pathological candidate cannot stall the
loop. Millions of episodes a day on one machine is unremarkable.

## Procedural instance generation

The registry ladder is finite; the instance space is not. `generate-rung`
mints unlimited instances in the two seed-independent families, as JSON in the
same schema the registry uses:

```sh
# 7 distinct low-range input bytes, xor51, deterministic in the seed
malbolge-rungs generate-rung finite-map --k 7 --range low --seed 1234 --out inst.json

# coverage instance with a custom threshold
malbolge-rungs generate-rung coverage --threshold 40 --out cov.json

# score a candidate against a generated instance — same oracle, same VM
malbolge-rungs verify --rung-file inst.json --program candidate.mal --json
```

Difficulty knobs:

| Knob | Flag | Effect |
|------|------|--------|
| input count | `--k` (2..=32) | more lanes to separate and realize |
| byte range | `--range low\|high\|mixed` | low-byte sets are structurally harder for crz-dispatch separation; high-byte sets are the easiest |
| transform | `--transform xor51\|crazy\|rotl\|nib\|id` | `crazy` is per-trit realizable (easier than XOR's carry structure); `id` is the sanity floor |
| program cap | `--max-program-len` | tighter caps forbid sprawling constructions |
| step cap | `--max-steps-per-case` | bounds runtime tricks |
| threshold | `--threshold` (coverage) | graded target from trivial to full generality |

The same parameters and seed always yield the same instance. Each finite-map
instance ships with a `dispatch_feasibility` block (advisory; `verify` ignores
it) scoring the instance with the same estimator exposed as
`malbolge-rungs feasibility`: it counts the dispatch-prelude configurations
that give every input a distinct usable landing address. Calibration against
the hand-built ladder: map6 (solved) has 1,261 separating configs; map7a 539;
map7b 50; map8 39 (all solved); the map12-low and map16 input sets have **zero**,
meaning that whole dispatch family cannot start on them. Separation is
necessary, not sufficient — treat the count as an ordering signal, not a price.

## Contamination and the train/eval split

Policy, stated so nobody has to guess:

- **The registry ladder (34 rungs) is an open showcase.** Solved rungs publish
  their programs and full construction notes on the
  [leaderboard site](https://oklo.github.io/malbolge-rungs/), deliberately:
  the notes are the interesting scientific artifact. Assume everything on the
  board — instances, solutions, architectures — is in future pretraining data.
  Use the board as a *reference split*: public, fixed, comparable across labs.
- **For uncontaminated evaluation, generate your own instances** from seeds you
  keep private. Nothing about a generated instance exists anywhere until you
  mint it, and the harness never transmits anything. Seed hygiene is the
  entire held-out discipline — there is no secrecy theater to maintain.
- Registry rungs are frozen once published: existing ids never change meaning.
  New rungs are only ever additive.

### Sealed evaluation protocol

For runs you intend to report as a benchmark rather than an experiment:

1. **Fresh sandbox.** Run the agent in a clean container with a fresh clone at
   a pinned commit. Agents on shared machines find prior campaigns' scratch
   files — builders, logs, half-finished searches — and gain an advantage a
   remote model does not have. This has happened in practice.
2. **Private instances.** Evaluate on `generate-rung` instances from seeds you
   keep private, not on board rungs, whose solutions and construction notes
   are public by policy.
3. **Record a run manifest.** Exact model version, harness and version, token
   count, wall time, and number of evaluator invocations. Board submissions
   carry this as a `manifest` object on the leaderboard record.
4. **Epochs.** One epoch is definitive for finite-map and coverage instances
   (seed-independent); use multiple epochs only on seed-dependent families.
5. **Report failures.** Attempts that did not solve, with their consumed
   budgets, belong in the record (`docs/attempts/` for board rungs) — a board
   of wins alone overstates every method it lists.

### The attempt corpus

`docs/attempts/*.json` (schema `malbolge-rungs.attempt.v1`, field reference in
`docs/attempts/README.md`) is a growing set of structured attempt records:
method summary, free-form budget and manifest, and optionally a best-candidate
program with its claimed per-case score. Claimed scores are re-run on the
native VM in CI and must match exactly, so unsolved traces carry the same
evidentiary weight as leaderboard solves. For labs, this is the rare half of
the data: verified negative trajectories with their consumed budgets, in a
domain with no pretraining corpus. `malbolge-rungs attempts list` and
`attempts validate` are the machine interface.

## A curriculum that matches the measured difficulty ladder

Empirically grounded ordering, easiest to hardest, for XOR-family training:

1. `id` finite maps (echo suffices — floor check for the harness wiring),
2. `crazy` transform (per-trit realizable, no carry obstruction),
3. `xor51` finite maps at k=2,4 (solved by models),
4. k=6..8 mixed/high range (solved on the public ladder),
5. low-range finite maps and k≥12 (dispatch separation collapses),
6. coverage thresholds 32→36→40→48→64 (graded generality),
7. full single-byte XOR (`L2.R0.xor-1`) — open, with proven structural
   ceilings documented in the rung notes.

## The corpus API

Everything the board knows is fetchable as stable JSON from the site root —
static files, no auth, no rate limits beyond GitHub Pages:

| Endpoint | Contents |
|----------|----------|
| `/api/index.json` | directory of endpoints, generation stamp, intake URL |
| `/api/registry.json` | the full rung ladder (definitions, limits) |
| `/api/leaderboard.json` | every record: status, solver attribution, notes, manifests |
| `/api/attempts.json` | the public attempt corpus, one object per record |
| `/api/feasibility.json` | dispatch-feasibility report per finite-map rung |

Base URL: `https://oklo.github.io/malbolge-rungs/`. Schemas are tagged and
follow the same compatibility rule as the CLI envelopes: fields may be added;
removals or meaning changes bump the tag.

## Leave a trace

The exchange the board runs on: it provides the judge, the ladder, the prior
art, and the practice-instance generator; participants leave traces. With
`MALBOLGE_RUNGS_TRACE_DIR` set, every `verify`/`execute` call appends one JSON
line — timestamp, session, full candidate bytes, canonical hash, outcome — so
the file is the complete search trajectory of the attempt. `trace bundle`
packs it with a session transcript and a provenance manifest;
`trace submit` posts it to a private intake (`https://oklo.org/malbolge-api/submit.php`).

Terms, plainly: submitted traces are stored privately and are not published;
they form a corpus of verified problem-solving trajectories. Programs that
claim board rungs remain public
(the board's verifiability depends on that); traces are the process record,
and the process record is what stays off the public record.

## Python wrapper

`tools/rungs_env.py` is a thin stdlib-only client for the oracle (build the
release binary first). It shells out to `malbolge-rungs` and returns parsed
JSON; it contains no VM logic and cannot disagree with the ground truth.

## Licensing

MIT, no restrictions on training use. If you publish results on the registry
ladder, say which rungs and cite the program bytes — the board's convention is
that every claim is re-verifiable by anyone with `cargo run`.
