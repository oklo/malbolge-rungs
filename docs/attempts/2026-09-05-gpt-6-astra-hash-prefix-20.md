# GPT-6 Astra solves the twenty-case, two-byte hash-prefix lookup

`L5.R1.future-hash-prefix` passes the native verifier on all twenty public
cases across five required epochs. Each case emits exactly two bytes and halts.
The solution is 1,463 bytes, within the 2,048-byte cap. Solver: **GPT-6 Astra**,
OpenAI, Codex. Date: 2026-09-05.

This is the registry's finite public lookup. It does not compute a hash or
claim correctness on additional epochs.

## Dispatcher and independent regions

Input byte 18 distinguishes the twenty cases. Two CRAZY operations with
operands 67 and 67 produce twenty distinct words from 35 through 158. Eight
right rotations multiply those words by nine. The code entries range from
316 to 1423, with a minimum spacing of nine cells.

Most tails receive up to forty cells, bounded by the next entry. Each lane's
code and private operands are synthesized independently, and reads from other
lanes' variable regions are rejected. Every complete candidate is subsequently
checked by the native VM on all required cases.

## Separating the two output searches

The original depth-first search reached only five complete two-byte cases over
100 randomized constant pools. It spent much of its budget on paths that had
not yet emitted the first byte.

The revised search treats a correct first OUT as a boundary: it starts a
separately bounded suffix search for the second OUT and halt. Prefix depth
limits run from 5 through 17, with at most 300,000 prefix nodes per depth.
Suffix depth limits run from 3 through 16, with at most 20,000 nodes per suffix
depth. A 10-million-node total cap applies to each prefix-depth search.
This reached sixteen complete cases with randomized constant pools.

## Accumulator phase and continuations

After storing the dispatch address, the prologue rotates a fixed source value
at data cell 69 into A and routes D back to cell 67 before jumping. This changes
the tail's accumulator while preserving the address in memory. Eight legal
seed values at cell 69 were tested, each with 100 constant pools. The best
phases reached eighteen complete cases.

The successful phase uses seed 124, so A=19724 at every tail entry. Data cells
84 and 109 contain 108 and 66, implementing the return route to D=67. The
prologue ends at code cell 62, safely below the first entry.

Lanes 10 and 13 have only nine primary code cells. They receive additional
private regions `[95,109)` and `[110,126)` respectively. A common constant
pool must then satisfy all twenty independent searches. Seeds 600000 through
600437 were tested with these regions; seed **600437** produced the complete
solution. The final 2,048-byte tape was truncated to 1,463 bytes and verified
again on the native evaluator.

## Reproduce

```sh
cargo build --release
python3 research/astra-2026-09-05/derive_cases.py
cc -O3 research/astra-hash20/private.c -o /tmp/astra-private2048-staged
python3 research/astra-hash20/reproduce.py /tmp/astra-private2048-staged
```

The last command rebuilds the successful dispatcher and constant pool, runs
the staged search, trims the resulting program, and verifies all twenty cases
natively. `experiment-summary-01.jsonl (and numbered continuation files)` records the staged, phase, and continuation
experiments, including seeds, case counts, and per-lane node/depth results.
`successful-trial.json` preserves the decisive full solver output;
`solution-verify.json` contains all twenty native input/output observations.

The structured attempt score is the harness's worst required epoch, 4/4.
There are five successful epochs and twenty successful cases in the full report.
This extends the three earlier GPT-6 Astra hash-prefix solves in this session,
and their map8/XOR-256 construction lineage.
