# Process log: Fable 5 on L2.R0.xor-1, 2026-09-05

Chronological; every number was produced by the tool named on the line.

1. Calibration. Rebuilt research/xor-1/dpk; build2.py (L-parameterized port of
   build_x1.py, imports from xor-1-push/mal.py since this snapshot lacks
   xor-1-len4096/build.py) reproduces the 68/256 optimum byte-identically at
   k=5 K0=1 L=256. Native verify --epochs 256: 68/256 epochs pass. Model =
   native.
2. reach.c: per-input closure BFS over the 10-trit accumulator.
   CRZ-only: 193/256 reachable (worst min-depth 3); unreachable set includes
   96..159 and 243..255 whole. +rotr(acc): 256/256, worst depth 5.
   +crazy(v,acc): 256/256, worst depth 4. This is the "ROT in the walk" BFS
   the records asked for, answered: necessary and (in principle) sufficient.
3. L-sweep via build2.py + dpk: L=180 best 46 (k in {3,5}, K0 1..24; k=7
   partial), L=200: 53, L=232: 63, L=248: 68, L=256: 68 (k=5 K0 in {1,2,4},
   exact). Monotone; the fill is designless freedom and freedom is what
   binds. Closed.
4. Premix family: worked out a fully loader-legal layout that parks a copy of
   b at (106,107), rotates it j times at 3 instructions per rotation via
   pinned pointers {74:101, 85:71, 86:106, 108:85, 109:84} (all byte-legal at
   their addresses, verified), and re-dispatches D = b+1 off untouched m[72].
   dpk2.c (= dpk + acc0 = rotr^J(b)) swept j=1..7, k in {3,5}, K0<=16:
   best 54/256 at j=7 k=5. Shared rotation adds no per-input freedom.
5. jdp.c: the push record's code-tape DP target, restricted to the D-invariant
   alphabet {NOP,CRZ,ROT,OUT,HALT}. Ranked ALL 8^5 operand streams
   (m[73]=61 pinned) by the per-input independent bound: maximum 36/256.
   The full transfer-matrix DP is therefore pointless (<=36 < 68); the
   48-53 previously searched came from D-repointing, i.e. private data.
6. Post-fold family: funnel re-derived above the code zone (funnel114.json:
   26 pins, root 114, exit pin 121:71 -> D=72), then pattern ops at cell 72
   folding acc against m[72]=b. dpk3.c exact DP over 7 patterns x k in {3,5}
   x K0 in {1,2,4,6,8}: best 4/256. Cause: every walk-end cell in the source
   range drops from 8 legal bytes to ~2.4 (value+1 must land in the tree);
   the alphabet tax exceeds the fold gain. Measured, transfers to every
   funnel-based second dispatch at tight caps.
7. Shipped candidate: build2.py one 7 21 256 -> cand_k7_o21_L256.mal,
   dp=68 model=68, native verify --epochs 256: 68/256, sha256 bbc73cb8...
   Distinct bytes from the k=5 record program.

Conclusion for the next agent: the rung's remaining open mechanism is
data-dependent control flow (self-modifying JMP loops, per-input trip
counts). Everything else at this cap now has an exact number attached.
