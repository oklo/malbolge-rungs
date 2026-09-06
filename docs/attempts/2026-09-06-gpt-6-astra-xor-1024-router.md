# GPT-6 Astra: 228/256 XOR cases in 982 bytes

**L2.X1024.xor-1-len1024 remains unsolved.** This candidate passes 228 of the required 256 exhaustive native cases in 982 source bytes. Its SHA-256 is `5b68e629ce5d44a07f9c13b661663348eeeadcf6eb058e9394fb4c3cef6a5241`. A separate sweep using exactly one input byte reproduces the same score. The registry, fixtures, resource limits, and verifier are unchanged.

This is a continuation of GPT-6 Astra's exhaustive 2,028-byte XOR solution. Removing the 123-cell pointer advance between arithmetic passes reduces source size sharply: the window now begins at `1 + 3*b`. Inputs 41–255 use freely synthesized table data, but inputs 0–40 overlap the bootstrap, registers, and return-router bytes. The program uses twelve passes over five mutable cells, followed by two CRAZY operations, output, and halt. Return paths preserve the accumulator.

Exact dynamic programming with 4,096 boundary states synthesizes a shared table for the upper 215 inputs. All 215 pass. A second optimizer changes loader-legal low-memory bytes unused by setup. Each proposal was screened by a four-MOVD route guard targeting absorbing root 88. A subsequent audit found that this guard used stale setup values for boundary cells 124–127; it is a heuristic screen, not a proof that every proposed mutation preserves all upper cases. A native-semantics diagnostic VM scores the lower 41 cases. This finds another 13 successes; the unchanged native verifier confirms the aggregate 228/256. Some lower cases intentionally execute arithmetic through implicitly filled memory after their data pointer is displaced. The program reads only its first input byte; suffix bytes and epoch identities do not affect the result.

The arithmetic masks are:

```
27, 3, 20, 517, 18, 50, 24, 18, 16, 26, 5, 8
```

Bit `j` selects ROT for mutable cell `j`; bit `j+5` selects NOP; otherwise the operation is CRAZY. NOP takes precedence. The prefix enters shared code at address 819. The seven-cell source windows overlap in four cells, and the exact table optimizer enforces loader validity and return-pointer constraints jointly.

## Search outcome and limitations

**Guard audit, September 6:** a shifted-table candidate scored 222 in the combined diagnostic calculation but only 220 natively. Cells 124–127 had been treated as fixed setup data even though table assembly can replace them. The submitted 982-byte candidate is unaffected as a verified result: all 215 upper cases and 13 lower cases pass both the canonical native sweep and the separate one-byte sweep. Its historical search and reproducer are retained unchanged for provenance. Diagnostic seed/hybrid scores that were not checked natively are not certified VM scores, and neither their route guard nor the low-case search establishes a family-wide bound. New searches exclude table-overwritten boundary cells or check their actual per-case values. `guard-audit.json` records the evidence.

Native milestones in this compact layout were 214, 218, 223, 226, and 228 cases. A sweep over 100 diverse arithmetic seeds independently optimized their return routers. Eight subsequent rounds, totaling 480 mutations and associated table/router searches, did not exceed 228. These trials are correlated diagnostic searches, not independent model evaluations or a proof of impossibility. `search-counts.json` records the arithmetic search count at this submission snapshot; that separate controller may continue afterward.

Jointly optimizing arithmetic instructions using only the lower-case objective reached 14 lower successes, but rebuilding the upper table reduced the combined score to 192. Padding after the halt instruction changed implicit memory fill without improving the retained 228-case witness. Those outcomes favor preserving a joint objective over optimizing the low cases in isolation.

Additional protected-memory experiments place the address register at cell zero and the absorbing root at cell 59048. A new nine-operation two-register circuit constructs all-twos from printable seeds 80 and 72 without consuming input. Its assembled constant-output witness is 102 bytes and 35 native steps. This reduces protected-layout setup cost, but the resulting arithmetic family has not beaten the submitted candidate. An early router model incorrectly permitted paths through table-overwritten cells 124–127 and variable registers; that diagnostic discrepancy was identified by native verification and corrected. No pre-correction score is offered as a native result.

## Reproduce

From the repository root, with Python 3 and a C compiler:

```sh
python3 research/astra-xor1024-router-2026-09-06/reproduce.py
./target/release/malbolge-rungs verify \
  --rung L2.X1024.xor-1-len1024 \
  --program research/astra-xor1024-router-2026-09-06/reproduced.mal --json
```

The reproducer regenerates the table from the retained source template and constraints, reruns the deterministic router search, and checks both baseline and final SHA-256 values. The template is an explicit artifact; no private file or hidden search state is required. Compiler/library differences affecting simulated-annealing floating-point decisions may change an exact search replay; the frozen candidate and native evidence remain independently verifiable.

This attempt is credited to **GPT-6 Astra (OpenAI, Codex)**. It builds on the earlier Astra 2,048-byte solve and the corpus's 121/121 input-copy construction. Factual experiment logs, candidate groups, and native oracle calls are retained for a private training trace; they do not contain a reconstructed private reasoning transcript. The campaign's coarse weekly account meter rose from 5% at its start to 8% at this submission snapshot, within the user's authorization of up to one sixth of a weekly allocation. This is an interim negative submission while further research continues.
