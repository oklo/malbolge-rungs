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
  "artifacts": ["research/...", "docs/attempts/..."]
}
```

Required: `schema`, `rung_id`, `date`, `outcome` (`"solved"` or `"unsolved"`).
Everything else is optional; `manifest` and `budget` are free-form key/value.

**Best-candidate claims are verified.** If `best_candidate` is present, CI runs
the named program on the rung's native evaluator and rejects the record unless
the observed per-case score equals the claim exactly. Check the candidate
program file in alongside the record. A verified 5/12 is a real datum; an
unverified one is an anecdote.

Validate locally:

```sh
cargo run -p harness -- attempts validate
```

Records render on the rung's board page under "Recorded attempts". For solves,
the leaderboard record carries the claim and attribution; the attempt record
carries the method. Reference any search code checked in under `research/`.
