# Profound XOR-256 solve

This directory contains the architecture, principal synthesis tools, and process
memory for the complete solve of `L2.R0d.xor-1-len4096`. The canonical winning
tape lives under `solutions/`, following the repository's admission convention.

## Result

```text
program: ../../solutions/xor-1-len4096/xor-256-gpt-5.6-sol.mal
length: 4096
sha256: fe2bea8bb173005f7d5a5f30589b20877dbef3cb9b1a5535e0f43f64df35e58f
native score: 256/256
steps: 604..616
outputs per run: exactly one byte
```

Verify with:

```sh
./target/release/malbolge-rungs verify \
  --rung L2.R0d.xor-1-len4096 \
  --program solutions/xor-1-len4096/xor-256-gpt-5.6-sol.mal \
  --epochs 256 --json
```

## Architecture

The rung name is historical: the required mask is `0x51`, and
`0x51 = 81 = 3^4`.  The solve exploits that exact radix coincidence.

An exact six-CRAZY ternary circuit computes

```text
q = 9*(b + 81).
```

The final jump enters `C=q+1`, so the 256 inputs receive disjoint nine-cell
blocks spanning source addresses 730..3033.  This eliminates every collision
between input blocks and the low-memory initializer.

The favorable low-memory phase enters each block with `D=42`.  A three-copy
echo using `K4=3276` leaves `m[41]=m[42]=q`, allowing the jump through cell 41
to preserve the useful `D=42` phase.  A final full rotation of the persistent
26248 register gives

```text
CRAZY(26248, 55) = 3303.
```

The epilogue stores that value in cell 120 and leaves `A=3303`.  This is the
decisive phase change: independent exact synthesis solves 251 blocks, including
the otherwise sealed input 216.  The five exceptions all have private exits:

```text
input 117 -> tail 3160
input 153 -> tail 3196
input 180 -> tail 3232
input 205 -> tail 3279
input 250 -> tail 3331
```

The tail intervals are disjoint.  Joint exact synthesis of each nine-cell
block and its 27-cell continuation therefore composes without cross-input
constraints.

## Principal tools

- `PROCESS.md`: reconstruction of the reasoning, pivots, dead ends, and durable
  lessons from the campaign.
- `build_shifted_dispatch.py`: raw-Malbolge micro-assembler and the six-gate
  `q=9*(b+81)` circuit.
- `retarget_old_dispatch.py`: K4 echo, `D=42` retargeting, and the 3303 phase.
- `shifted_block_solve.c`: exact independent-block synthesis and phase scans.
- `shifted_tail_solve.c`: exact two-island block/tail synthesis.
- `b217_suffix_scan.c`: boundary-compatibility diagnostic from the discarded
  255/256 phase.

All scores used during construction were finally checked by the canonical Rust
evaluator; the file above is the exact native-verified tape. These experimental
tools preserve the important construction stages but are not packaged as a
deterministic one-command rebuild. Unfiltered candidates, compiled search
binaries, and the oracle log belong to the private `malbolge-traces` corpus.
