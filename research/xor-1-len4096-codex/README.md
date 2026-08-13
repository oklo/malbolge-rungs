# Codex continuation — `L2.R0d.xor-1-len4096`

This directory contains a native-verified **251/256** candidate and the search
programs that derived it from the inherited hero1/hero3 artifacts.

## Champion

`runs/hero1-joint150151-short-o0-0.mal`

- length: 2605 bytes
- SHA-256: `a77c8a32f6e15080a0b8a5496f26d5d814e32cdea6e39130337d485fbf46224e`
- native all-byte score: **251/256**
- failures: `0 1 3 8 9`

Verify it with the canonical evaluator:

```sh
./target/release/malbolge-rungs verify \
  --rung L2.R0d.xor-1-len4096 \
  --program research/xor-1-len4096-codex/runs/hero1-joint150151-short-o0-0.mal \
  --epochs 256 --json |
jq '{program:.results[0].program,
     program_len:.results[0].program_len,
     sha256:.results[0].program_sha256,
     correct:([.results[0].outcome.epochs[]|select(.passed)]|length),
     failures:[.results[0].outcome.epochs[]|select(.passed|not)|.epoch]}'
```

## Derivation

The inherited hero1 candidate scored 249/256 and failed
`0 1 3 8 9 151 255`. The inherited hero3 candidate also scored 249/256, but
failed `0 1 3 4 8 9 255`. Hero1 was therefore the useful crossover base: it
already solved byte 4.

1. `lengthscan_hero1.c` exhaustively scanned lengths 2305..4096 and all 64
   legal final-byte opcode pairs under hero1's original prologue semantics. It
   found phase-aligned lengths 2323, 2605, and 2887 that retain exactly the same
   249 successes. `runs/hero1-correct-s4.mal` is the length-2605 base.
2. `route_hero1.c` routed byte 255 through the newly writable extension. The
   compact order-6 witness changes 14 cells and trades failure 255 for 254:
   `runs/hero1-routed255-o6.mal`.
3. A byte-254 witness with the byte-255 trace frozen changes three further cells
   and reaches 250/256, failing only `0 1 3 8 9 151`:
   `runs/hero1-routed254-after255-o0.mal`.
4. Byte 151 shares its first instruction, address 1360, with solved byte 150.
   `joint150151_hero1.c` crosses the finite exact witness families instead of
   greedily repairing either input alone. With address 1360 made a JMP, first
   witness 1 for byte 150 and second witness 66 for byte 151 give the 251 tape.

The three milestone deltas are 14, 3, and 13 changed cells respectively.

## Reproduction

Build the three relevant tools:

```sh
cc -O3 -o research/xor-1-len4096-codex/lengthscan_hero1 \
  research/xor-1-len4096-codex/lengthscan_hero1.c
cc -O3 -o research/xor-1-len4096-codex/route_hero1 \
  research/xor-1-len4096-codex/route_hero1.c
cc -O3 -o research/xor-1-len4096-codex/joint150151_hero1 \
  research/xor-1-len4096-codex/joint150151_hero1.c
```

The exact productive commands were:

```sh
./research/xor-1-len4096-codex/lengthscan_hero1 \
  -s research/xor-1-len4096-hero1/cand.mal \
  -o research/xor-1-len4096-codex/runs/hero1-length-best.mal \
  -lo 2305 -hi 4096

./research/xor-1-len4096-codex/route_hero1 \
  -s research/xor-1-len4096-codex/runs/hero1-correct-s4.mal \
  -o research/xor-1-len4096-codex/runs/hero1-routed255-o6.mal \
  -N 2605 -target 255 -lo 2323 -hi 2377 -span 8 \
  -steps 220 -nodes 3000000000 -order 6

./research/xor-1-len4096-codex/route_hero1 \
  -s research/xor-1-len4096-codex/runs/hero1-routed255-o6.mal \
  -o research/xor-1-len4096-codex/runs/hero1-routed254-after255-o0.mal \
  -N 2605 -target 254 -protect 255 -lo 2323 -hi 2377 -span 36 \
  -steps 220 -nodes 3000000000 -order 0

./research/xor-1-len4096-codex/joint150151_hero1 \
  -s research/xor-1-len4096-codex/runs/hero1-routed254-after255-o0.mal \
  -o research/xor-1-len4096-codex/runs/hero1-joint150151-short-o0-0.mal \
  -N 2605 -order1 0 -order2 0 -span1 12 -span2 12 \
  -nodes1 3000000000 -nodes2 3000000000
```

The full length scan was originally sharded eight ways. The unsharded command
above is equivalent and deterministic.

## Other tools and negative evidence

- `lengthscan.c` and `beamsearch.c` produced the independent hero3 250/256
  candidate `runs/routed253-o6.mal` (failures `0 1 3 4 8 9`).
- `protect255.c`, `chain253254.c`, `compat3.c`, and `compatlow.c` test exact or
  capped compatibility among high-tail and low-window witnesses.
- `trace.c` can be compiled normally for hero3 or with `-DHERO1` for hero1.
- `tailpairs.c`, `pairsearch.c`, `protected_desc.c`, and the remaining small C
  programs are bounded diagnostics used to reject local repair hypotheses.
- Freezing all 250 solved traces in the hero1 250 tape leaves no byte-151
  witness; its conflict with byte 150 has to be solved jointly.
- On the 251 tape, freezing all solved traces leaves only one mutable cell for
  byte 9 and zero witnesses. Across eight DFS opcode-order rotations, short
  byte-9 witnesses scored at most 237/256 before repair. These are bounded
  search results, not impossibility proofs.

`runs/` is deliberately a scratch ledger as well as a result directory. The
four named hero1 milestones above and `routed253-o6.mal` are the important
files; the other candidates record capped searches and failed variants.

The narrative report is
[`docs/attempts/2026-08-12-codex-xor-1-len4096.md`](../../docs/attempts/2026-08-12-codex-xor-1-len4096.md).
