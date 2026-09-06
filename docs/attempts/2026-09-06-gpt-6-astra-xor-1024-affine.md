# GPT-6 Astra: 248/256 XOR cases in 1,023 bytes

**L2.X1024.xor-1-len1024 remains unsolved.** This candidate passes 248 of the required 256 canonical native epochs. A separate native sweep with exactly one input byte gives the same results. All 256 executions halt after 194 steps. The failing first bytes are `0, 2, 4, 9, 11, 14, 15, 191`. The source is 1,023 bytes, with SHA-256 `5934de2f4b5a19d00eb2af37ef82e8ce679c4a183e9aeec0978293f544f1e3bf`.

This improves the earlier published Astra result of 228/256 in 982 bytes. It follows the campaign's complete 2,028-byte XOR solution. No registry fixtures, resource limits, or verifier behavior were changed.

## Construction

The prefix computes `3*b+81` and begins each seven-cell data window at `82+3*b`. A ternary phase change in the address circuit makes its constants cheap to construct: five raw printable words, `55, 51, 101, 123, 109`, plus the all-ones word. If `C(a,d)` denotes the VM's CRAZY operation, `x=rot²(b)`, and `y=rot(b)`, the circuit is:

```
t = C(C(C(b,55),51),101)
r = C(y,t)
c = C(r,123)
a = C(x,109)
d = C(a,c)
e = C(d,x)
q = rot⁷(C(e,29524)) = 3*b+81
```

The actual instruction order preserves useful register values. A 27-byte bootstrap enters address 856; a 60-byte main prefix ends at address 916. Eight arithmetic passes operate on five mutable cells. Each intervening return uses a fixed pointer graph with root 59 and depth four, followed by the address-register reset. Two final CRAZY operations produce the output byte, followed by output and halt. The arithmetic masks are:

```
3, 16, 60, 146, 23, 272, 20, 7
```

Bit `j` selects ROT for cell `j`; bit `j+5` selects NOP; otherwise the operation is CRAZY. NOP takes precedence.

Exact dynamic programming chooses overlapping loader-legal table bytes for inputs 16–255, obtaining 239 of those 240 outputs. A deterministic stochastic search changes the low-memory return graph while preserving the upper table's used return leaves. It adds nine successful inputs among 0–15. The prefix registers and guarded pointer graph occupy addresses below 128; the independently synthesized upper table begins at 130. This separation avoids the stale boundary-word guard defect documented in the earlier 228-case attempt. Native verification, rather than either diagnostic model, establishes the reported score.

## Research findings and limits

The address calculation and return graph are the main improvements. The retained witness came from a 900-trial search over eight-pass arithmetic schedules and layouts. Subsequent searches explored earlier bootstrap operations, adjacent root/address registers, nine-pass schedules, different table/router boundaries, and a third final CRAZY operation. `search-counts.json` records completed trial counts at the submission snapshot; these are correlated computational searches, not independent model evaluations.

An exact CP-SAT formulation optimizes shared loader bytes and return routes. For the retained arithmetic schedule, omitting return constraints permits an arithmetic-only table satisfying all 256 outputs. That artifact is not an executable solution. The full model with safe return paths is infeasible for the fixed schedule and layout. Models allowing input-specific prefix registers, per-pass modified data cells, and implicit-memory return paths (excluding aliases through live arithmetic code) also found no all-sixteen-low-input solution for this schedule. Those are restricted construction results, not a proof that this rung is impossible.

A different arithmetic schedule achieves all sixteen low inputs in a native candidate, but only 167/256 overall; its unrestricted shared-table arithmetic reaches at most 243. This demonstrates why a low-only objective is insufficient. A dependency-tracked mutation search around the retained 248-case program made 524,765 proposals and 4,027,606 diagnostic case evaluations without improving its score.

Several rejected constructions clarified model boundaries. One prefix allocator initially allowed later route fields to overlap bootstrap instructions; its native mismatch invalidated those estimates and prompted a corrected allocator. A third-final-operation controller initially emitted a 1,025-byte program; native size rejection exposed the error, and the corrected controller enforces the 1,024-byte cap before scoring. An upper-table rebuild with no legal return at a required phase was rejected as having no DP path. None of those estimates is included in the reported score. Search scripts, factual logs, and scoped corrections are retained in the private research trace.

## Reproduce

From the repository root, with Python 3 and a C compiler:

```sh
python3 research/astra-xor1024-affine-2026-09-06/reproduce.py
./target/release/malbolge-rungs verify \
  --rung L2.X1024.xor-1-len1024 \
  --program research/astra-xor1024-affine-2026-09-06/reproduced.mal --json
```

The reproducer compiles the diagnostic table and router optimizers, rebuilds from the explicit source template and constraints, and checks both baseline and final SHA-256 values. An exact replay succeeded in the submitting environment. Floating-point annealing decisions can vary across compiler/library combinations; the frozen candidate remains directly verifiable by the native VM. The included canonical and one-byte native results cover every first-byte value.

Credit: **GPT-6 Astra (OpenAI, Codex)**. This is an interim negative submission within the user's authorization of up to one sixth of a weekly allocation. At this snapshot, the coarse account-wide meter had risen from 5% to 11%; it is not an exact Astra-only token quota. Training provenance consists of factual experiment logs, candidate groups, scores, corrections, and actual oracle calls; it does not reconstruct a private reasoning transcript.
