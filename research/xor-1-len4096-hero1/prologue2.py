#!/usr/bin/env python3
"""An alternate dispatch prologue that does not put a MOVD at address 1.

Why it matters.  Prior art's prologue is IN, MOVD x3, CRZ x2, 8 x (MOVD, MOVD,
ROT), MOVD, MOVD, JMP at addresses 0..32, and the dispatch JMP sends input b to
c = 9b, resuming at 9b+1.  For b = 0,1,2,3 that resume address (1, 10, 19, 28)
is inside the already-executed prologue.

Those inputs are NOT dead.  XLAT2 maps printable to printable, and the VM treats
any decoded value outside the eight instruction codes as a runtime NOP
(crates/classic_malbolge/src/lib.rs, `_ => {}`), so an enciphered prologue cell
is always still executable and is a NOP about 92% of the time.  b = 0..3 slide
through the enciphered prologue as a NOP sled and reach the dispatch JMP -- which the
dispatch JMP never enciphers, because the canonical cycle sets c = m[d] first
and enciphers the TARGET.  So they re-execute that JMP with
d = 73 + (32 - entry), and land on m[d] + 1: a second, per-input dispatch.

The one thing that breaks the sled is an enciphered cell that decodes to a REAL
instruction.  At address 1 the first-pass MOVD enciphers into IN, and IN reads
the second byte of the 32-byte case input, which is seed-derived.  So b = 0 is
the only one of the four killed by the prologue itself, and only because of the
MOVD at address 1.

This module builds a prologue with a NOP at address 1.  It works -- the sled at
address 1 becomes clean -- but shifting every later instruction by one puts ROT
at address 10, and a ROT at 10 enciphers into HLT, which kills b = 0 and b = 1
instead.  Net dispatch reach: 251/256 here versus 253/256 for prior art's
phase.  The four low inputs are a prologue-PHASE search, and this file is the
search tool for it, not a solution.

    python3 prologue2.py            # emit and check
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mal import byte_for, code_of, XLAT2, VALID_CODES, NAMES, run

JMP, OUT, IN, ROT, MOVD, CRZ, NOP, HLT = 4, 5, 23, 39, 40, 62, 68, 81

# code sequence, address by address
# A MOVD at address a executes with d == a (d has tracked c since reset), so it
# reads its OWN byte and lands on byte_for(MOVD,a)+1.  Putting the NOP at 1 makes
# the first MOVD sit at address 2, which starts the chain at 39 instead of 40 --
# and from 39 the shortest route to the forced CRZ pair (71,72) is three hops,
# 39 -> 43 -> 92 -> 71, one longer than prior art's 40 -> 123 -> 71.
SEQ = ([IN, NOP, MOVD, MOVD, MOVD, MOVD, CRZ, CRZ] +
       [MOVD, MOVD, ROT] * 8 +
       [MOVD, MOVD, JMP])
FORCED = {39: 42, 43: 91, 92: 70, 71: 121, 72: 121, 62: 71, 73: 61}
N = 2305


def build(filler=NOP):
    prog = bytearray(N)
    for a in range(N):
        prog[a] = byte_for(filler, a)
    for a, k in enumerate(SEQ):
        prog[a] = byte_for(k, a)
    for a, v in FORCED.items():
        prog[a] = v
    return prog, len(SEQ)


def check_source(prog):
    for a, b in enumerate(prog):
        assert 33 <= b <= 126, (a, b)
        assert code_of(b, a) in VALID_CODES, (a, b, code_of(b, a))


def main():
    prog, plen = build()
    check_source(prog)
    print(f"prologue is {plen} instructions, addresses 0..{plen-1}; "
          f"the JMP at {plen-1} is never enciphered")
    for a, v in sorted(FORCED.items()):
        print(f"  data m[{a}] = {v}  (decodes to {NAMES[code_of(v,a)]} at {a})")

    # what each executed prologue cell becomes on its second pass
    print("\nsecond-pass image of the prologue (what b = 0..3 actually run):")
    sled = {}
    for a in range(plen - 1):
        e = XLAT2[prog[a] - 33]
        k2 = code_of(e, a)
        sled[a] = NAMES.get(k2, "nop*")          # nop* = not one of the 8 codes
    for b in range(4):
        entry = 9 * b + 1
        path = [f"{a}:{sled[a]}" for a in range(entry, plen - 1) if sled[a] != "nop*"]
        print(f"  b={b} enters at {entry:2d}; real instructions before the JMP: "
              f"{path if path else 'none -- a clean NOP sled'}"
              f"   -> JMP at {plen-1} with d = {73 + (plen - 1 - entry)}")

    # dispatch smoke test: every block is [OUT, HALT]
    for b in range(256):
        for a, k in ((9 * b + 1, OUT), (9 * b + 2, HLT)):
            if a < plen or a in FORCED or a >= N:
                continue
            prog[a] = byte_for(k, a)
    check_source(prog)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dispatch2.mal")
    open(out_path, "wb").write(bytes(prog))
    ok = [b for b in range(256)
          if run(bytes(prog), bytes([b]))[:2] == (bytes([(9 * b) % 256]), "Halted")]
    print(f"\ndispatch reaches its own block for {len(ok)}/256 inputs -> {out_path}")
    print("inputs that do not:", [b for b in range(256) if b not in ok])


if __name__ == "__main__":
    main()
