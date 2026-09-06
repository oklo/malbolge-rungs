# GPT-6 Astra: 250/256 XOR cases in 1,024 bytes

**L2.X1024.xor-1-len1024 remains unsolved.** This program passes 250 of 256 canonical native epochs. A separate native sweep using exactly one input byte agrees. All 256 executions halt after 205 steps. The six failing first bytes are `1, 3, 6, 8, 13, 15`. SHA-256: `b453afa3887061009105b54dd8cdf62e4383fa3e4fa6180fdee6275c059ec0e6`.

This continues the same GPT-6 Astra campaign as the complete 2,028-byte XOR solution and the 228- and 248-case partial results at the 1,024-byte limit. The score is an exhaustive first-byte coverage result, not a solved rung or a success probability on independent tasks. The registry, fixtures, limits, and verifier are unchanged.

## Construction and search

The address circuit again computes `3*b+81`, with data windows beginning at `82+3*b`. Moving some setup operations into the bootstrap and placing the address register immediately after the return root shortens each return. The retained layout uses root 41, address register 42, four pointer-graph steps, and a two-instruction exit. This fits nine arithmetic passes in 1,022 bytes. The masks are:

```
89, 3, 20, 184, 208, 209, 16, 20, 7
```

Bit `j` selects ROT for mutable cell `j`; bit `j+5` selects NOP; otherwise the operation is CRAZY. NOP takes precedence. Two final CRAZY operations, output, and halt finish the computation.

Exact overlapping-table synthesis satisfies all 240 inputs from 16 through 255. The preceding stochastic router search found seven of the sixteen low inputs, for 247/256. A CP-SAT model then varied low source bytes while retaining the upper table and its used return leaves. It tracked each input's actual prefix-register values, all five modified table words after every pass, and return pointers into fixed source and implicitly filled memory. It excluded aliases through live arithmetic code and required the prescribed return to the root after each intermediate pass. This model found and proved an optimum of nine modeled low successes for this fixed upper table, yielding a natively verified 249-case program in 1,022 bytes.

The two spare bytes affect the VM's implicit memory fill even though they follow the halt instruction. A bounded search tried all 73 legal padding choices of length zero, one, or two, with a router search for each. Padding opcode choices `ROT, MOVD`, followed by a deterministic router search, produced the retained 250-case witness. The instructions in the padding are never reached on these runs; their source-byte values affect implicit memory. The winning router search uses seed 600697 and 20 restarts of 15,000 proposals each.

The 250-case program also demonstrates a limitation of the CP model. Re-optimizing with its padding but the prescribed per-pass returns still gives an optimum of nine modeled low successes, whereas the native program has ten. Correct execution can leave that prescribed sequence of data windows. The scoped optimum is therefore not a bound on arbitrary Malbolge programs, or even every runtime behavior available to this source layout.

The campaign also constructed a four-CRAZY digit permutation that creates an unused gap in a different data table. Placing setup code in that gap permits fourteen arithmetic passes in 1,016 bytes, and an initial candidate passed 213 native cases. Subsequent bounded searches had not exceeded this submission's score at the snapshot. Other ongoing joint table/return optimizations likewise make no additional solve claim here. Factual logs distinguish native outcomes from diagnostic estimates and restricted solver bounds.

## Reproduce

```sh
python3 research/astra-xor1024-stateful-2026-09-06/reproduce.py
./target/release/malbolge-rungs verify \
  --rung L2.X1024.xor-1-len1024 \
  --program research/astra-xor1024-stateful-2026-09-06/reproduced.mal --json
```

The reproducer starts from the explicitly retained 249-case CP witness in `base.mal`, applies the two padding bytes, reruns the final stochastic search, and checks the intermediate and final hashes. It reproduces the final search, not the entire earlier CP-SAT optimization. The baseline witness, its model metadata and scoped optimization result, the complete 73-choice padding results, the C search source, and both native sweeps are included. Exact replay succeeded in the submitting environment; compiler/library differences affecting floating-point annealing can alter a search replay, while the frozen candidate remains independently verifiable.

Credit: **GPT-6 Astra (OpenAI, Codex)**. This is an interim negative submission under the user's authorization of up to one sixth of a weekly allocation. The campaign began at 5% on the coarse account-wide weekly meter; the latest inspected snapshot was 12%. That meter is not an exact Astra-only token quota. Actual oracle calls, factual experiment records, candidate groups, and scoped model corrections are retained for private training provenance, without reconstructing a private reasoning transcript.
