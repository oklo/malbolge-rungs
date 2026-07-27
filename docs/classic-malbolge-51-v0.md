# Classic-Malbolge-51 v0

`Classic-Malbolge-51 v0` is the deterministic classic Malbolge execution
profile used by MAL-51. It is distinct from Malbolge Unshackled, and it is the
sole ground-truth VM for the rung harness in this repository, implemented in the
`classic_malbolge` crate.

The profile follows the public classic Malbolge descriptions from Esolang and
Lou Scheffer's Malbolge specification where they are clear, and pins
deterministic behavior where reference behavior is buggy or undefined.

## Memory And Words

- Memory contains exactly 59,049 cells.
- Each cell is a 10-trit word in `0..=59048`.
- Addresses wrap modulo 59,049.
- Registers `A`, `C`, and `D` are initialized to zero.

## Source Loading

- Source bytes must be ASCII.
- ASCII whitespace is ignored when loading executable source.
- Raw bytes are still preserved for program hashes and metadata.
- Executable bytes must be printable ASCII in `33..=126`.
- At executable address `i`, a byte is source-valid only when
  `(byte + i) % 94` is one of `4, 5, 23, 39, 40, 62, 68, 81`.
- Raw source and executable source must fit within the configured program length
  limit.
- Executable source length must be at least two instructions for MAL-51 public
  proofs.

The one-instruction edge case is rejected because classic descriptions fill
memory from the previous two cells and do not define how memory cell 1 should be
filled when only cell 0 exists. Public references note that this case is
undefined or buggy in reference behavior. MAL-51 therefore rejects it instead of
turning undefined host behavior into a valid proof.

## Memory Initialization

Executable source bytes are loaded at address zero. All remaining cells are
filled in increasing address order:

```text
memory[i] = crazy_word(memory[i - 1], memory[i - 2])
```

This pins the convention as "previous cell, then second previous cell." The
Esolang description states that memory is filled from the previous and second
previous word in that order. Lou Scheffer's wording says the remainder is filled
by applying `op` to the previous two cells; MAL-51 fixes the argument order
explicitly for reproducibility.

## Crazy Operation

`crazy_word(a, d)` applies this tritwise table to all ten trits, padding both
arguments to ten trits with leading zero trits:

```text
          a trit
          0  1  2
d = 0     1  0  0
d = 1     1  0  2
d = 2     2  2  1
```

Instruction `62` uses:

```text
A = memory[D] = crazy_word(A, memory[D])
```

The operation is not commutative. Tests lock both argument order and whole-word
10-trit padding.

## Instruction Dispatch

At each step:

1. Fetch `memory[C]`.
2. If it is not printable ASCII `33..=126`, stop with
   `InvalidRuntimeInstruction`.
3. Compute `code = (memory[C] + C) % 94`.
4. Execute:
   - `4`: `C = memory[D]`
   - `5`: output `(A % 256)` as one byte
   - `23`: read one input byte into `A`; if input is exhausted, use `59048`
   - `39`: `A = memory[D] = rotate_right(memory[D])`
   - `40`: `D = memory[D]`
   - `62`: `A = memory[D] = crazy_word(A, memory[D])`
   - `68`: no-op
   - `81`: halt immediately
   - any other printable runtime code: no-op
5. After every non-halt instruction, encipher `memory[C]` using the current value
   of `C`, then increment `C` and `D` modulo 59,049.

For jump/code-pointer update (`code 4`), this means `C` changes before the
post-instruction encipher step. MAL-51 intentionally preserves that classic
ordering and tests that the post-jump cell is enciphered.

## Enciphering

The encipher table is indexed by `word - 33` for printable words:

```text
5z]&gqtyfr$(we4{WP)H-Zn,[%\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G"i@
```

Pinned examples:

- `!` enciphers to `5`
- `"` enciphers to `z`
- `~` enciphers to `@`

Non-printable cells are rejected before dispatch. A non-printable value at the
post-encipher target is also rejected deterministically.

## I/O And Terminal Behavior

- Input and output are raw bytes.
- There is no newline translation.
- Output is exactly `A % 256`.
- EOF is the word value `59048`.
- Halt returns `Halted` and does not post-encipher or increment pointers.
- Step limit, output limit, program length limit, and memory limit failures are
  deterministic validation failures.
- Native classic public validation requires the full 59,049-cell memory model.

## Fixtures And Oracle Tests

Normal golden fixtures live in `fixtures/classic/`:

- `halt_no_output.mal`: `QC`, halts with no output.
- `nul_output.mal`: `cP`, emits `00` and halts.
- `echo_first_byte.mal`: `ubO`, echoes the first input byte and halts.

`cat_nonhalting_esolang_cc0.mal` is a larger CC0 reference fixture from the
Esolang Malbolge page. It is not used by normal unit tests because the published
program does not halt on EOF.

An optional external oracle test can compare the tiny fixtures against a local
reference interpreter:

```sh
MAL51_CLASSIC_ORACLE=/path/to/malbolge-interpreter cargo test -p classic_malbolge external_oracle
```

The oracle executable must accept the program path as its first argument, read
input bytes from stdin, write program output to stdout, and exit successfully for
the halting fixtures. This harness is non-consensus test tooling only; it is not
a MAL-51 backend. Do not vendor interpreter code with unclear licensing; when
using a local oracle, record the interpreter source and license in any test notes
or research report that depends on it.

## References

- Esolang classic Malbolge page:
  <https://esolangs.org/wiki/Malbolge>
- Lou Scheffer's Malbolge specification and notes:
  <https://www.lscheffer.com/malbolge_spec.html>
  and <https://www.lscheffer.com/malbolge.shtml>
