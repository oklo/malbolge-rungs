# L6.S0.cat — the EOF branch, built and verified; the unroll, not finished

**Rung:** `L6.S0.cat` (Stream / Identity, 3 cases, input length drawn from the seed
in 1..16, min 5 epochs, ≤ 8192 bytes, ≤ 65536 steps/case)
**Outcome:** unsolved. `research/cat-push/cand.mal` returns the correct **first**
byte and status `Halted` on all 15 cases across the five required epochs.
**Model / harness:** claude-opus-5 / Claude Code CLI, autonomous, cap 800k tokens
or 120 min.

---

## 0. This VM is not classic Malbolge

The rung's `purpose` field points at the published looping Malbolge programs
(99-bottles, the Nagoya LISP interpreter) as proof that the thing is possible.
None of them run here. From `crates/classic_malbolge/src/lib.rs`:

| code | this VM | classic Malbolge |
|------|---------|------------------|
| 4  | `c = m[d]` (jump) | `j` : `d = m[d]` |
| 5  | output `a mod 256` | `i` : `c = m[d]` |
| 23 | input (`a = 59048` past the end) | `*` : rotate |
| 39 | rotate: `m[d] = rotr(m[d]); a = m[d]` | `p` : crazy |
| 40 | `d = m[d]` | `<` : input |
| 62 | crazy: `m[d] = crazy(a,m[d]); a = m[d]` | `/` : output |
| 68 | nop | nop |
| 81 | halt | halt |

Jump/movd are transposed against each other and so are input/output. A published
program fed to this VM decodes to different instructions at every position. Every
result below was derived from the Rust source, and checked in
`research/cat-push/vm.py`, a Python re-implementation that I first proved
byte-identical to the native backend before trusting any of its output.

## 1. No loop is required

The encipher table has **no fixed points**. Its cycle lengths are 2 (`F`,`J`),
4 (`*`,`i`,`r`,`}`), 5, 6, 9 and 68. A cell that executes twice comes back as the
next value in its cycle; for the 2-cycle the two values are 4 apart mod 94, and
no two valid opcodes in {4,5,23,39,40,62,68,81} differ by 4. So a cell can never
run the same instruction on two passes, and a loop body that survives up to 17
iterations would have to restore itself.

But `max_input_len` is 16. Sixteen **unrolled** blocks, each cell executed at most
once, sidesteps self-modification completely. That is the architecture here. It is
not a loop and I am not claiming it is one; it is the correct program for the rung
as specified.

## 2. The EOF branch, which is the actual problem

Reading past the end sets `a = 59048 = 0t2222222222`. Every input byte is
< 3^6 = 729, so **its trits 6..9 are 0**. That four-trit gap is the entire signal.

Turning it into control flow means making `m[d]` hold a jump target that is one
constant for all 256 bytes and a different constant for EOF. Three impossibility
results shape what that costs:

- **One CRAZY can never do it.** As a function of the accumulator trit, crazy's
  column maps are `M0=[1,0,0]`, `M1=[1,0,2]`, `M2=[2,2,1]`. None is constant, so
  a single CRAZY cannot make the junk trits input-independent, and the low trits
  of the target would follow the data byte. Two are needed.
- **The mask cannot live in the accumulator.** This would have been the cheap
  route, because rotations of legal bytes are free accumulators (ROT-load a cell).
  With the unknown on the `d` side the row maps are `[1,1,2]`, `[0,0,2]`,
  `[0,2,1]`; the only mergeable pair of rows is {0,1}, and no composition of any
  length collapses three trit values to one. The mask must be the memory cell.
- **The mask cannot be a program byte.** For the byte case to contribute 0 at trit
  position 9 (required: the target must be < 8192) the only admissible `(m1,m2)`
  pair is `(2,0)`, so **M1 needs a 2 in trit 9**, i.e. M1 ≥ 39366. Program bytes
  are 33..126 < 243, so every legal cell has trits 5..9 equal to 0 and trit 4 in
  {0,1}. And the crazy-filled memory above the program is no help either
  (§3). **M1 has to be manufactured at runtime.** That single requirement is the
  rung's real cost.

`research/cat-push/analyze2.py` enumerates the whole per-trit mask algebra:
**8396** achievable `(R_byte, R_eof)` pairs, **1044** distinct in-range byte
targets. The branch has plenty of address freedom. It is the constant, not the
branch, that is expensive.

## 3. The crazy-filled memory is a dead end for M1

`m[i] = crazy(m[i-1], m[i-2])` above the program is determined entirely by the
last two program bytes, and it goes periodic with period ≤ 6 within a couple of
cells. Over **all 94×94 tails** it produces exactly **297 distinct values**:
27..161 and 29403..29564. Every one of them has its top five trits either all 0 or
all 1. There is not a single 2 in the high trits anywhere in the fill. The fill is
a fine source of pointers and accumulators; it can never supply M1.
(`research/cat-push/fill2.py`.)

## 4. What is built and verified

`research/cat-push/build.py` is an assembler with a `d`-offset-tracking layout
engine. `d` increments in lockstep with `c`, so the offset is constant between
MOVDs; to retarget `d` it writes the pointer value into the data cell that `d`
will be pointing at, padding with NOPs until that value is legal at that address.
Address 0 is a JMP whose forced byte value is 98, so control leaves for address 99
and cells 1..98 become a data region that is never executed.

The shipped block:

```
prologue   S, N, C1 := all-1s          (CRAZY with a=0 on legal bytes whose
                                        base-3 digits are all 0/1 gives 29524)
           a := rotr^6(80) = 6480 ; CRAZY C1   -> C1 = e(6480)
           a := rotr^1(122) = 39406 ; CRAZY C1 -> C1 = M1 = 52407
block      IN                          -> a = x, or 59048 at EOF
           CRAZY S                     -> S = e(x), a = e(x)      (save)
           CRAZY C1  (mask M1 = 52407)
           CRAZY M2  (mask M2 = 80, a legal byte)  -> a = R
           MOVD back onto the M2 cell ; JMP        -> c = R
                                        byte: R = 6641 -> continuation at 6642
                                        EOF : R =   80 -> lands on HALT at 81
continue   ten ROTs on S               (rotate-right has order 10, so the cell is
                                        restored and a = e(x))
           CRAZY N                     (crazy(a, all-1s) = e(a), an involution)
                                        -> a = x
           OUT ; HALT
```

Natively verified:

- correct echo and clean halt for **all 256 single-byte inputs**;
- **empty input halts with empty output** — the EOF path works;
- on the rung itself, all 15 cases across epochs 0..4 return the correct **first**
  byte with status `Halted`;
- 323 steps per case, 6900 of 8192 bytes.

```
$ ./target/release/malbolge-rungs verify --rung L6.S0.cat \
      --program research/cat-push/cand.mal --epochs 5 --verbose
  case 0: in=7da24ec7dbfb04 exp=7da24ec7dbfb04 got=7d [Halted] MISS
  ...
RESULT: FAIL
```

## 5. Where it stopped, and why that is a budget line not a wall

`R_byte` is fixed by the mask pair, so each of the sixteen blocks needs its own
`(M1, M2)`. `M2` is free — there are 8 legal bytes with the right trit shape
(54, 56, 60, 62, 72, 74, 78, 80) — and each pairs with a discriminating trit in
{6,7,8}, giving 24 candidate masks. My constant builder found **2**.

That builder was deliberately narrow: exactly two CRAZY steps, with accumulators
drawn only from `{rotr^k(V) : V a legal byte}`. It is not a statement about what
is constructible; it is what I had time to write. The mask algebra offers 1044
in-range targets and the two M1 values it did reach (52407 and 52409) are the same
shape as the other twenty-two. Widening to three CRAZY steps, and letting the
accumulator come from any already-built cell rather than only from rotations of a
raw byte, is the one change that turns this into a solve. I would expect it to
take well under an hour.

Two other things worth knowing for whoever picks this up:

- Choose the discriminating trit at position **6**, not 8. `R_byte = M2 + 3^k`, so
  trit 8 puts the continuation at ~6640 and burns 6900 bytes on one block; trit 6
  puts it at ~810, which is what makes sixteen blocks fit inside 8192 at all.
  `masks2.py` already prints the M1 required for trit 6 (58239) — the builder
  simply could not reach it.
- If the builder resists, there is a second route to per-block continuations:
  after the conditional JMP, `d = M2_k + 1`, which is per-block state that
  survives the jump. A MOVD at a shared landing site can read a per-block pointer
  out of `m[M2_k+1]`. The catch is that a shared tail's cells encipher on each
  pass, so the tail has to re-disperse within about one instruction.

The same toolchain carries straight over to `L6.S1.length` and `L6.S2.checksum`
— the EOF test, the save/restore and the assembler are unchanged, and only the
per-block body differs. `L6.S3.reverse` additionally needs the input held before
any output, which the per-block save cells already do.

## 6. On the ranking

L6.S0.cat sits at board rank 38, below several L2 finite-map and coverage rungs.
On this evidence it is a different *kind* of problem rather than a harder instance
of the L2 one: it needs an assembler and a theory of runtime constant
construction, which is a lot of up-front work, but nothing about it is walled. The
coverage and single-byte-XOR rungs have ceilings that are provable arithmetic
facts about legal byte magnitudes; this one has a search I ran out of clock to
finish. I would rank it **high effort, low risk** — expensive, but it yields.
