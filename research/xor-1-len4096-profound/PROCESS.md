# Process memory: the XOR-256 solve

This note preserves the reasoning path behind the 2026-08-13 solution of
`L2.R0d.xor-1-len4096`. It is a reconstruction rather than a transcript. The
canonical result is
`solutions/xor-1-len4096/xor-256-gpt-5.6-sol.mal`, SHA-256
`fe2bea8bb173005f7d5a5f30589b20877dbef3cb9b1a5535e0f43f64df35e58f`.

## What changed the problem

The rung's historical name encouraged the wrong mental model. The required
operation is XOR with `0x51`, and

```text
0x51 = 81 = 3^4
b xor 81 = b + 81 - 2*(b & 81).
```

The Boolean mask therefore lands on a distinguished radix position in
Malbolge's native ternary arithmetic. This did not directly produce an XOR
circuit. Its real value was architectural: it suggested looking for an
injective ternary address map instead of another straight-line output formula.

Earlier exhaustive work had put the branchless CRAZY/ROT family at only 34
correct inputs. That was evidence that output algebra was not the missing
ingredient. Control and memory layout were.

## The decisive dispatcher

With input copies `x=9b` and `y=27b`, exact tritwise synthesis found four
constants

```text
K1 = 52496
K2 = 54683
K3 = 3645
K4 = 3276
```

and the six-CRAZY circuit

```text
a = CRAZY(x,K1)
r = CRAZY(y,K2)
c = CRAZY(r,K3)
d = CRAZY(a,c)
e = CRAZY(d,x)
q = CRAZY(e,K4) = 9*(b+81).
```

The constants select identity, increment, carry, or zero independently at the
relevant trits. The resulting map is injective on all 256 byte values. A jump
through `q` enters `C=q+1`, assigning input `b` the private nine-cell block
`q+1..q+9`. The 256 blocks occupy addresses 730..3033: they are mutually
disjoint and do not overlap the low-memory prologue.

This was the main conceptual breakthrough. It factored one globally coupled,
self-modifying program into 256 mostly independent finite synthesis problems.
Search became a constructor and checker for a mathematical decomposition,
rather than a blind walk over complete 4,096-byte tapes.

## Why the first good layout stopped at 255

The initial dispatcher entered blocks with `D=43`. Exact independent-block
synthesis solved about 245 inputs. A hypothetical `D=42` entry solved 250, with
exceptions 146, 147, 205, 216, 246, and 249.

Rebuilding the prologue directly to produce `D=42` made the result worse. This
showed that “phase” was not just the visible `(A,C,D)` triple: the overwritten
low-memory scratch geometry was part of the computational state.

The last dispatcher gate supplied a way to preserve that geometry. On the
circuit image, K4 acts as an involution:

```text
e --K4--> q --K4--> e --K4--> q.
```

Additional K4 copies in cells 41 and 68 left `q` in both cells 41 and 42.
Jumping through cell 41 then entered `C=q+1, D=42` without rebuilding the
favorable scratch state.

Five reachable exceptions could use short private continuations, giving a
native 255/256 tape. Input 216 was different: its nine-cell block was sealed.
It had neither a local solution nor a usable high-memory exit. An 18-cell
search could solve 216 only by borrowing input 217's first cell, moving the
failure to 217. Joint boundary and suffix searches confirmed that this was not
an ordinary tail-allocation problem. One especially attractive route had
already emitted the wrong byte before reaching high memory, so no continuation
could repair it.

The durable lesson was to treat a sealed local component as evidence against
the current global phase, not as a request for more brute force.

## The phase change that removed the wall

The next search scanned controllable low-memory values and accumulator phases.
The prologue already retained 26248 in cell 93 and 55 in cell 120, giving the
identity

```text
CRAZY(26248,55) = 3303.
```

A full ten-ROT cycle reloads 26248 without changing it. Applying CRAZY at cell
120 manufactures 3303 there and deliberately leaves `A=3303` at block entry,
while preserving `D=42` and the collision-free dispatcher.

This phase solved 251 blocks independently, including the previously sealed
input 216. Its five exceptions—117, 153, 180, 205, and 250—all had high-memory
exits. Exact joint block-and-tail synthesis assigned disjoint 27-cell tails:

```text
117 -> 3160
153 -> 3196
180 -> 3232
205 -> 3279
250 -> 3331
```

Because the blocks and tails were disjoint, the five witnesses composed with
the 251 local witnesses without cross-input constraints. The native evaluator
then passed all 256 first bytes, with exactly one output byte and 604..616
steps per case.

## How computation was used

The productive order was:

1. derive and exhaustively check the injective dispatcher;
2. preserve low-memory geometry while changing the entry data pointer;
3. scan a small, meaningful phase space;
4. synthesize independent nine-cell blocks in parallel;
5. classify only the exact residual exits;
6. assign disjoint continuations and verify the composed tape natively.

Optimized C searches ran as parallel CPU processes across the Apple M4. Metal
was considered but rejected for this search shape: one exact Malbolge memory
image is 59,049 16-bit words, or 118,098 bytes, exceeding the measured 32 KiB
threadgroup-memory budget, while recursive paths are highly divergent. The
useful acceleration came from state factorization, not the GPU.

## What was deep and what was contingent

The equality `81=3^4` was a fortunate property of this rung, but the solve was
not a lucky discovery of a universal XOR formula. Its deep role was to expose
a radix-resonant, collision-free address system. The final program is best
understood as a compiled lookup machine whose dispatch is mathematical and
whose private blocks realize the byte outputs.

The 3303 identity was more contingent. It supplied the state conjugacy needed
to move the one sealed input into a phase where every remaining exception had
an escape. The broader phenomenon—the dramatic dependence of local
expressivity on apparently incidental accumulator and scratch-memory phase—is
likely more important than the number 3303 itself.

## Rules worth carrying forward

- Verify the actual transform and rung digest before accepting the rung's name
  as a mathematical description.
- Preserve post-prologue scratch geometry. Two executions with the same
  visible registers can have very different local solvability.
- Scan meaningful phase variables before extending local brute force.
- A block with no solution and no exit is an architectural diagnostic.
- Before routing to a tail, check whether an incorrect output has already been
  emitted; a tail cannot undo output.
- Use disjoint blocks and tails whenever possible so independently found
  witnesses compose by construction.
- Re-run the native evaluator after every composition step. Diagnostic VMs and
  local solvers are not the judge.

## Artifact map

- `build_shifted_dispatch.py` constructs the six-gate safe dispatcher.
- `retarget_old_dispatch.py` implements the K4 echo, `D=42` entry, and 3303
  phase change.
- `shifted_block_solve.c` performs exact independent-block and phase searches.
- `shifted_tail_solve.c` performs joint block/private-tail synthesis.
- `b217_suffix_scan.c` records the boundary diagnostic from the discarded
  255/256 phase.
- `docs/attempts/2026-08-13-codex-profound-xor-256.md` is the concise public
  attempt report.

The tools are preserved as research code, not presented as a deterministic
one-command compiler for the exact final tape. The native-verified tape is the
durable proof object. Unfiltered intermediate candidates, binaries, working
tree residue, and the oracle log are retained in the private
`malbolge-traces` session archive.
