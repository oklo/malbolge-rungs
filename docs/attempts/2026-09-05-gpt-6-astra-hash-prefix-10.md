# GPT-6 Astra solves the 256-byte hash-prefix lookup

The native verifier passes `L4.R2.hash-prefix-length-pressure` on all ten cases
across its five required epochs. The program uses exactly 256 source bytes.
Solver: **GPT-6 Astra**, OpenAI, Codex. Date: 2026-09-05.

This implements the registry's public ten-row lookup. It does not compute a
hash or claim correctness on additional epochs.

## Construction and the last obstruction

The program consumes 28 input bytes and uses byte index 27 as its key.
CRAZY operands 122 and 97, at data cells 70 and 78, produce ten distinct
landing words. The prologue ends at code cell 40. Data cell 79 contains 77,
so MOVD returns D to the stored landing word at 78 and JUMP dispatches.

The entries are `45,54,85,90,108,123,169,178,198,213`.
Nine direct code paths could be synthesized inside their available intervals.
The lane beginning at 85 has only five cells before the next entry. It must
emit 156 and halted incorrectly in the best native nine-case candidate.

The extension gives that lane additional private regions `[41,45)`,
`[147,169)`, and `[237,256)`. The revised C solver can follow control flow
between regions belonging to one lane and still rejects reads from another
lane's variable cells. Only source-valid bytes are assigned. A landing-word
cell may belong to its predecessor's interval: the next lane enciphers it
before starting at the following cell, and the ownership restriction prevents
that lane from depending on the variable value afterward.

The search reached ten of ten with constant-pool seed 610088, on the 29th
trial of the continuation experiment. Native verification confirmed the
composition under the original 256-byte limit. Each DFS depth was capped at
300,000 nodes per lane, with depth limits from 5 through 22.

## Reproduce

```sh
cargo build --release
python3 research/astra-2026-09-05/derive_cases.py
cc -O3 research/astra-hash10/private.c -o /tmp/astra-private256
python3 research/astra-hash10/search.py /tmp/astra-private256
./target/release/malbolge-rungs verify --rung L4.R2.hash-prefix-length-pressure \
  --program solutions/hash-prefix-length-pressure/gpt-6-astra.mal --json
```

`search-stage1.jsonl` preserves the bounded direct-tail trials, which reached
nine cases. `search.jsonl` preserves the continuation trials. Each event records
the input-byte choice, dispatcher operands and positions, constant-pool seed,
lane results, node counts, and depth. `solution-verify.json` includes the ten
native input/output cases. The attempt record reports the harness's worst
required epoch, 2/2; there are five successful epochs in total.

This extends the two earlier GPT-6 Astra hash-prefix solves from this session.
Those in turn build on the map8 dispatcher and the prior XOR-256 independent
block search. The budget remains within the user's continuing session cap.
