# Ladder methodology — September 2026 revision

The public board is one curriculum from reference programs to open research
challenges. `leaderboard/leaderboard.json` supplies stable display ranks;
`leaderboard/ladder.json` supplies names, six difficulty groups, and a rationale
for every placement. Existing rung IDs, evaluator semantics, and credited
programs are retained. Display labels are separate from hashed task contracts.

## Basis for this revision

The September 5 public corpus adds four GPT-6 Astra lookup solves and Fable 5
partial candidates for compact XOR (68/256) and rotation (62/256). Native
verification establishes these scores. The two partial results motivate keeping
the compact byte transforms adjacent; their six-case difference is not a
measurement of relative difficulty.

The accompanying campaign report says a multiple-byte attempt was interrupted
by a session limit. No completed new result for that attempt is inferred here.
The report's statement that multiple-byte tasks are mathematically out of reach
until a single-byte task falls is not established: unsuccessful searches are
not impossibility proofs, and caps and test domains differ. Claimed bounds
remain attributed to their reports and explicitly scoped construction families.
Budget figures differ between the supplied recap and submitted manifests;
this revision does not reconcile them by guessing or use them as controlled
model-comparison data.

## The single ordering

1. **Foundations.** Halt and fixed copying. Preserve canonical/tool baselines,
   duplicate conformance slots, and their actual provenance. These establish
   the floor without inventing earlier-model results.
2. **Input-dependent construction.** Finite maps, a native ternary transform,
   two-byte reversal, and public lookups. Routing difficulty, verified
   constructions, and space pressure inform placement. Different input sets
   and caps make the exact cross-task order provisional. Historical L4/L5 hash
   labels no longer imply a cryptographic capability.
3. **Coverage to full XOR.** Keep existing historical coverage milestones;
   mark programs that clear multiple rows as shared evidence. Threshold order
   is strict only at matching resource limits. The 2,048-byte and 8,192-byte
   variants trade coverage against space. Full XOR at 4,096 bytes is solved.
4. **Compact arithmetic.** Add XOR caps of 2,048, 1,024, and 512 bytes before
   the existing 256-byte task. All retain the same first-byte sweep and
   2,048-step budget; their relative constraint order is exact. They have no
   measured success-rate calibration yet. Keep rotation and 256-byte XOR
   adjacent, with their public native partial scores visible.
5. **Multiple-byte transforms.** Nibble swaps and multi-byte XOR. Width, caps,
   and arithmetic change together; the ordering remains provisional. A
   first-byte sweep does not enumerate all byte pairs or four-byte tuples.
6. **Variable-length programs.** Copy, length, checksum, reversal. This is a
   provisional capability progression, not a measured solve-cost progression.
   The current public tests neither prove iteration nor establish behavior on
   all lengths. Additional EOF and loop microtasks should be piloted before
   assigning them calibrated positions.

Solves do not automatically reorder rows. The ordering is a revisable
curriculum, not an equal-interval scale. A program passing several rows supplies
correlated evidence. No model wins are fabricated to create an apparent
chronological progression.

## Verification scope

- FiniteMap enumerates the complete declared finite input domain.
- CoverageTransform enumerates all 256 one-byte inputs, accepting a threshold.
- Transform's first-byte sweep covers all 256 first-byte values for each case;
  the rest of the input remains a public deterministic suffix. Even a
  one-output-byte rung does not test every possible suffix.
- HashPrefix realizes public input/target rows. The target includes a seed not
  supplied to the program. A hidden-seed version is not an appropriate
  general hash-computation benchmark without redesigning its input contract.
- Stream tests 81 fixed public strings of length 1–255. Empty input is not in
  the current contract. A proposed empty-input successor must change the
  generator deliberately; the current generator clamps the lower bound to 1.

Published attempt scores aggregate first-byte sweeps but use the worst epoch
for other multi-epoch families. Never interpret a worst-epoch score as an
aggregate success rate or compare percentages across unrelated task contracts.

## Next evidence to collect

Use repeated, budgeted trials with matched tasks, model/harness configuration,
prior-art access, and search resources. Record unsuccessful and interrupted
runs, exact token-counter definitions, evaluator calls, and search compute.
Report success versus budget with uncertainty; do not pool incomparable budget
estimates. A score without a candidate is a contributor claim, not a native
observation. Family-specific feasibility estimates are hypotheses about methods,
not universal task ratings.

Private finite-map synthesis instances are available through `generate-rung`.
Hold them out from training until the agent's run begins. This is distinct from
hidden runtime testing of a frozen program. Coverage tasks with matching
parameters enumerate the same domain and are not fresh examples merely because
a seed changed. See [the evaluation manifest](evaluation/run-manifest.template.json)
and [ENVIRONMENT.md](../ENVIRONMENT.md).

## Revision policy

Presentation-only edits change names/ranks/rationales without changing rung
contracts or old credits. Prefer additive successors for new test distributions,
EOF cases, or changed limits. If an existing contract must be repaired, record
its digest change and preserve the historical evidence, then reverify affected
claims under the explicit new contract. New placements stay provisional until
matched trials support stronger calibration.
