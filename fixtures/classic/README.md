# Classic Malbolge Fixtures

These fixtures are for the `Classic-Malbolge-51 v0` profile, not Malbolge
Unshackled.

## Normal Golden Fixtures

- `halt_no_output.mal`: source `QC`; expected to halt with no output.
- `nul_output.mal`: source `cP`; expected to emit `00` and halt.
- `echo_first_byte.mal`: source `ubO`; expected to read one byte, emit the same
  byte, and halt. This is the bootstrap native MAL-51 proof fixture.

## Larger Reference Fixture

- `cat_nonhalting_esolang_cc0.mal`: known classic Malbolge cat program from the
  Esolang Malbolge page, whose page content is marked CC0/public domain. It is
  expected to copy input bytes to output but not halt on EOF, so it is kept as a
  reference/oracle fixture rather than a normal unit-test fixture.

