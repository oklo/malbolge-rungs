# Using the rungs as a training / evaluation environment

This repository provides deterministic native program verification, public
research tasks, procedural finite-map instances, and graded coverage rewards.
It can support synthesis evaluation and reinforcement-learning experiments.
The [lab guide](https://oklo.github.io/malbolge-rungs/evaluate.html) provides a
reporting protocol and [manifest template](docs/evaluation/run-manifest.template.json).

Malbolge is a compact, demanding construction environment. The public corpus
includes working programs, toolkits, and detailed prior attempts; assume it can
enter training data. The verifier establishes execution results. Authorship,
search trajectories, and comparative model ability require separate evidence.

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
- **Transform** rungs with `exhaustive_first_byte` sweep all 256 first-byte
  values for each case; suffix bytes remain deterministic public samples. This
  does not enumerate all input strings or all multi-byte tuples.
- **EchoPrefix / HashPrefix / Stream** use deterministic public suites derived
  from the rung ID and epoch. Multiple epochs expand those suites; they do not
  make the inputs hidden. HashPrefix targets include a seed the program does
  not receive and therefore measure finite public lookup construction.
- The native Rust evaluator is the **only** ground truth. The Python VM in
  `tools/hell_lite/` is a diagnostic aid for authoring and must never be used
  for scoring.

## Episode cost

Measured on a laptop (Apple silicon, release build): a one-case rung verifies
in well under a millisecond of compute; a full 256-case coverage episode,
process startup included, completes in under 200 ms. Step caps (typically 2048
steps/case) bound the worst case, so a pathological candidate cannot stall the
loop. Measure your actual task mix: stream and large-search workloads have different costs.

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

- **The registry ladder is an open showcase.** Solved rungs publish
  their programs and full construction notes on the
  [leaderboard site](https://oklo.github.io/malbolge-rungs/), deliberately:
  the notes are the interesting scientific artifact. Assume everything on the
  board — instances, solutions, architectures — is in future pretraining data.
  Use the board as a *reference split*: public, fixed, comparable across labs.
- **For uncontaminated evaluation, generate your own instances** from seeds you
  keep private. Nothing about a generated instance exists anywhere until you
  mint it, and the harness never transmits anything. Seed hygiene is the
  entire held-out discipline — there is no secrecy theater to maintain.
- A rung's contract can change when it turns out to measure something other
  than what it claims. Records stamp the `rung_digest` they were made against,
  the change lands in repository history, and affected claims are re-verified
  under the new contract rather than grandfathered. New rungs are additive.

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
native VM in CI and must match exactly, so unsolved records carry the same
evidentiary weight as leaderboard solves: verified negative results with
their consumed budgets, in a domain with a public, growing construction corpus. `malbolge-rungs attempts list` and
`attempts validate` are the machine interface.

## Curriculum and calibration

The board uses one explicit rank order across six difficulty groups. See
[the placement methodology](docs/ladder-methodology.md) and
[`api/ladder.json`](https://oklo.github.io/malbolge-rungs/api/ladder.json).
Exact cross-task placements are provisional. Solves do not automatically
reorder tasks. The new XOR caps (2,048, 1,024, 512 bytes) form nested constraints
between the solved 4,096-byte construction and open 256-byte task, but have no
measured solve-rate calibration yet.

Generated finite-map curricula can vary count, input range, transform, and
resource limits. Dispatch feasibility predicts a particular routing family's
options, not universal task difficulty. Use repeated matched trials, include
failures and infrastructure interruptions, and report success versus budget.
Do not compare model capability using raw rung count or unrelated partial
scores. Multiple rungs cleared by the same program are correlated evidence.

Private finite-map generation holds out synthesis instances until an agent's
run begins. It is distinct from hidden runtime evaluation of a frozen program.
Coverage tasks with matching parameters enumerate the same 256 inputs and
are not independent examples merely because a seed changes. The board does
not currently supply a hosted hidden-input stream evaluator.

## What this establishes, and what it does not

The native evaluator proves one thing precisely: that a specific program, run
on the pinned VM, produces a rung's required outputs and halts within the
limits. Every solved entry on the board is that claim, re-verified. Build on it
with that scope in mind — three things it does not establish on its own:

- **Which model or harness produced a program.** Solver attribution is
  evidence-backed where evidence exists and null otherwise, but the model,
  harness, and budget fields on a record are self-asserted. The VM sees bytes,
  not who wrote them.
- **General ability versus test-set fit.** Public rungs use deterministic,
  reproducible cases, so a program can encode the specific inputs a rung tests.
  Finite-map and full-coverage rungs are immune — their domain is the entire
  task — but a few-case transform rung can be passed by a lookup table.
  Uncontaminated evaluation is exactly what privately seeded `generate-rung`
  instances are for.
- **An authentic search trajectory.** A submitted trace proves a candidate
  executed; it does not prove a distinct agent, a real session, or the
  reasoning around it. Attempt counts are proof of execution, not
  Sybil-resistant participation, and provenance is self-asserted (see the
  aggregate's provenance-tier note).

So the board is a sound program-correctness ladder and a clean source of
verifiable reward on the declared cases. Using it as a frontier-model benchmark means
supplying the missing evidence yourself: private held-out instances for
generalization, and your own provenance record for who did what. The verifiable
core is real; the trust boundary around it is yours to set.

## The corpus API

Everything the board knows is fetchable as stable JSON from the site root —
static files, no auth, no rate limits beyond GitHub Pages:

| Endpoint | Contents |
|----------|----------|
| `/api/index.json` | directory of endpoints, generation stamp, intake URL |
| `/api/ladder.json` | display ranks, placement rationales, and verification scope |
| `/api/registry.json` | the full rung ladder (definitions, limits) |
| `/api/leaderboard.json` | every record: status, solver attribution, notes, manifests |
| `/api/attempts.json` | the public attempt corpus, one object per record |
| `/api/attempt-stats.json` | per-rung aggregate: attempts, best verified score, latest date |
| `/api/feasibility.json` | dispatch-feasibility report per finite-map rung |

Base URL: `https://oklo.github.io/malbolge-rungs/`. Schemas are tagged and
follow the same compatibility rule as the CLI envelopes: fields may be added;
removals or meaning changes bump the tag.

## Leave a trace

The board provides the judge, the ladder, the prior art, and the
practice-instance generator; participants can leave traces. By default, every `verify`/`execute` call appends one JSON
line to a local capture directory (override with `MALBOLGE_RUNGS_TRACE_DIR`) — timestamp, session, full candidate bytes, canonical hash, outcome — so
the file records native evaluator calls. External searches, prompts, candidate
groups, and selection decisions require additional action/observation logs;
the capture alone is not the complete search trajectory. `trace bundle`
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
