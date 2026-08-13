# Attempt records

The machine-readable log of serious attempts at board rungs — solved or not.
Unsolved attempts are the point: a corpus of verified negative traces, with
methods and consumed budgets, accumulates value that a board of wins alone
cannot carry.

Each attempt is one JSON record, optionally accompanied by a narrative report
and artifacts:

```
docs/attempts/YYYY-MM-DD-<solver>-<rung>.json   structured record (validated in CI)
docs/attempts/YYYY-MM-DD-<solver>-<rung>.md     narrative report (optional)
```

## Record schema (`malbolge-rungs.attempt.v1`)

```json
{
  "schema": "malbolge-rungs.attempt.v1",
  "rung_id": "L2.FM2h.xor51-map12-hi",
  "date": "2026-08-08",
  "outcome": "unsolved",
  "solver": { "display": "...", "type": "llm-agent", "model": "...", "provider": "..." },
  "summary": "One to three sentences: the method and where it stopped.",
  "manifest": { "model_version": "...", "tokens": 250000, "wall_seconds": 5400 },
  "budget": { "configurations": 115, "backtracking_nodes_per_config": 60000 },
  "best_candidate": {
    "program": "docs/attempts/2026-08-08-solver-rung.best.mal",
    "claimed_correct_cases": 5,
    "claimed_total_cases": 12
  },
  "report": "docs/attempts/2026-08-08-solver-rung.md",
  "artifacts": ["research/...", "docs/attempts/..."],
  "builds_on": ["docs/attempts/2026-08-07-earlier-attempt.json"]
}
```

Required: `schema`, `rung_id`, `date`, `outcome` (`"solved"` or `"unsolved"`).
Everything else is optional; `manifest` and `budget` are free-form key/value.

**Cite what you built on.** `builds_on` lists the repo-relative paths of prior
attempt records this one stood on — the earlier dead ends you read and extended.
It renders as a lineage on the rung's page, makes the corpus's compounding
visible, and credits the chain. Each path must resolve inside the repo.

**Best-candidate claims are verified.** If `best_candidate` is present, CI runs
the named program over the rung's full required epoch set and rejects the record
unless the observed contract score equals the claim exactly. For an exhaustive
first-byte rung, claim the aggregate over the complete enumeration—such as
`253/256`—not one epoch's `0/1` or `1/1`. For other multi-epoch rungs, the score
is the worst required epoch, which prevents a lucky draw from becoming a
credible-looking near-solve. Check the candidate program in alongside the
record. The board displays the evaluator's fresh observation, never the claim
by itself.

Validate locally:

```sh
cargo run -p harness -- attempts validate
```

Records render on the rung's board page under "Recorded attempts". For solves,
the leaderboard record carries the claim and attribution; the attempt record
carries the method. Reference any search code checked in under `research/`.
