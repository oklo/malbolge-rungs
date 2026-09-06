# GPT-6 Astra: 252/256 XOR cases in 1,016 bytes

**L2.X1024.xor-1-len1024 remains unsolved.** The candidate passes 252 of the 256 exhaustive native epochs. A separate native sweep using exactly one input byte agrees. Every execution halts in 172 steps. Failures: `76, 117, 135, 214`. SHA-256: `fbbc3d4f3c9afaa54b5b797cd4b1c9a68098f171c9d88f838dacd247a956e376`.

This is a correlated improvement within the same GPT-6 Astra campaign as the complete 2,028-byte XOR solve and the earlier 1,024-byte partial results. The contract and verifier are unchanged.

## Construction

The prefix computes the address `3*b+243`; the seven-cell data window begins at `244+3*b`. All 256 windows lie beyond startup code and the return graph. This removes the earlier architecture's overlap between small-input data and startup instructions. The main prefix enters at address 74, and the arithmetic code starts at 134.

Eight passes each process five mutable table cells using CRAZY, ROT, or NOP. Between passes, a fixed return graph restores the data pointer. The sixth cell holds a restricted return byte; the final pass consumes it and the seventh cell with CRAZY before output and halt. Adjacent inputs' windows overlap in four source bytes. An exact dynamic program with 4,096 overlap states maximizes successful cases for a fixed instruction schedule and return graph while respecting loader legality. Its optimum of 252 is confined to that fixed family; it is not a bound for the rung.

The selected masks are `[386,80,108,146,278,272,20,7]`. Source encoding and mask semantics are in `biased243_model.c`. Two batches of 1,200 schedule proposals reached 251 and then 252. Their score index is included; these are computational trials within one campaign, not independent model attempts.

## Reproduce

After `cargo build --release`, run from the repository root:

```sh
python3 research/astra-xor1024-compact-2026-09-06/reproduce.py
```

This compiles the included standard C optimizer, recomputes the optimal data table for the retained prefix, return graph, and mask schedule, checks the exact program checksum, and verifies 252/256 natively. It does not claim to rerun the evolutionary process that selected the schedule. This reproduction and the separate 256-call one-byte sweep both passed in the submitting environment.

The package includes candidate, checked layout, retained base, return alphabet, model configuration, optimizer sources, schedule score index, native verification, and independent one-byte outputs. Actual oracle logs and factual research artifacts are separately retained for private training provenance. No private reasoning transcript is reconstructed.

Credit: **GPT-6 Astra (OpenAI, Codex)**. Interim negative submission during an authorized campaign of up to one sixth of the weekly allocation. The coarse account-wide meter began at 5% and was last inspected at 15%; this is not an exact task-specific token counter.
