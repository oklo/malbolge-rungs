# GPT-6 Astra solves the fifteen-case hash-prefix lookup

`L4.R1.hash-prefix-1-multicase` passes the native verifier on all fifteen cases
across its five required epochs. The submitted program is 778 bytes.
Solver: **GPT-6 Astra**, OpenAI, Codex. Date: 2026-09-05.

The program implements the registry's public finite lookup. It does not compute
a hash or claim correctness on additional epochs.

## The new dispatcher

Input byte 21 distinguishes all fifteen rows. Two CRAZY operations with
operands 90 and 125 map those byte values injectively to:

`17, 35, 44, 53, 98, 107, 116, 125, 134, 170, 179, 188, 197, 215, 251`.

The minimum gap is nine. Rotating the stored word right nine times multiplies
it by three on this bounded domain, increasing the minimum gap to 27.
The resulting entry addresses run from 52 to 754. A 48-instruction prologue
fits below the first entry, while the largest tail ends before address 778.

Cell 67 stores the dispatch word. Cell 68 holds 66, so alternating MOVD and
ROT repeatedly returns D to cell 67. The final MOVD/JUMP enters the selected
tail with D=68. The first tail ends at 66 to preserve scratch cells 66..68;
the other tails receive 24 cells each, leaving gaps available as constants.

The independent C tail solver from the five-row solve is reused unchanged.
It rejects reads from other lanes' variable intervals. A NOP constant pool
already synthesized fourteen tails. Random constant pools with seeds 600000
through 600003 yielded a complete solution on seed 600003. Native verification
then confirmed all fifteen cases, and confirmed the truncation from 1,024
to 778 source bytes.

## Reproduce

```sh
cargo build --release
python3 research/astra-2026-09-05/derive_cases.py
python3 research/astra-hash15/build.py
cc -O3 research/astra-2026-09-05/private.c -o /tmp/astra-private
python3 research/astra-hash15/search.py /tmp/astra-private
./target/release/malbolge-rungs verify --rung L4.R1.hash-prefix-1-multicase \
  --program solutions/hash-prefix-1-multicase/gpt-6-astra.mal --json
```

The search logs include seeds, node counts, depth limits, and each lane's
outcome. The native report includes every required input and output.
The structured record uses the harness's worst-epoch score, 3/3;
the full verification contains five epochs and fifteen successful cases.

This extends the same session's five-case solve and the earlier hash-prefix
attempt's public finite-map interpretation. The user authorized continued
search within one sixth of their weekly Astra allocation.
