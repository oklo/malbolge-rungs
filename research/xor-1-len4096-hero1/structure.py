#!/usr/bin/env python3
"""What actually constrains the JMP-dispatch private-code-block architecture.

Everything here is a finite check, printed with its evidence.

  (a)-(d)  why the dispatch prologue cannot be shorter than 33 instructions:
           the double-CRAZY operand is forced to 121, 121 is loader-legal only
           at a few addresses, MOVD can never point d below 34, and the rotation
           cycle cannot be squeezed below 3 instructions.  So addresses 0..31
           are executed and enciphered, and the resume addresses of inputs
           b = 0,1,2,3 (1, 10, 19, 28) all land inside that range.

  (e)-(f)  why that does NOT kill them.  XLAT2 maps printable to printable and
           the VM NOPs any decoded value outside the eight codes, so an executed
           prologue is a NOP sled; and the dispatch JMP never enciphers itself,
           so those inputs slide to it and re-dispatch through a cell we choose.
           Prior art recorded b = 0,1,2,3 as structural walls -- they are not,
           and this attempt's candidate solves b = 2.

  (g)      why the block base cannot simply be moved past the prologue.

Run:  python3 structure.py
"""
from mal import XLAT2, byte_for, code_of, VALID_CODES, NAMES, crazy, trits

CT = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]      # CT[operand_trit][acc_trit]
Mt = {w: (lambda t, w=w: CT[w][t]) for w in (0, 1, 2)}


def hdr(s): print("\n=== " + s + " ===")


hdr("(a) the double-CRAZY operand is forced to 121")
bij = []
for w1 in range(3):
    for w2 in range(3):
        img = tuple(CT[w2][CT[w1][t]] for t in range(3))
        if sorted(img) == [0, 1, 2]:
            bij.append((w1, w2, img))
print("per-trit compositions M[w2] o M[w1] that are bijections on {0,1,2}:", bij)
print("  -> only w1 = w2 = 1, and it is the identity.  A byte whose trits 0..4")
print("     are all 1 is unique in 33..126:",
      [v for v in range(33, 127) if trits(v)[:5] == [1, 1, 1, 1, 1]])

hdr("(b) where 121 is loader-legal, and which adjacent pairs exist")
legal121 = [a for a in range(0, 300) if code_of(121, a) in VALID_CODES]
print("addresses < 300 where the byte 121 is source-valid:", legal121)
pairs = [a for a in legal121 if a + 1 in legal121]
print("adjacent pairs (X-1, X):", [(a, a + 1) for a in pairs])
print("  d is set only by MOVD, which reads a byte >= 33, so d >= 34 always:")
print("  usable pairs:", [(a, a + 1) for a in pairs if a >= 34])

hdr("(c) the rotation cycle cannot be shorter than 3 instructions")
print("a 2-instruction cycle needs ROT@X then MOVD@(X+1) with m[X+1] = X-1,")
print("i.e. the byte X-1 must be source-valid at X+1: (2X) mod 94 in VALID_CODES.")
for X in (13, 72, 107, 166, 201):
    print(f"  X={X:4d} (holds b): (2X) mod 94 = {(2 * X) % 94:3d}",
          "LEGAL" if (2 * X) % 94 in VALID_CODES else "illegal")
print("  -> no candidate X works; 8 rotations therefore cost 8 x 3 = 24 instructions.")

hdr("(d) minimum prologue")
print("  IN                                        1")
print("  MOVD x3   (d: 1 -> 40 -> 123 -> 71; two MOVDs cannot reach 71)  3")
print("  CRZ x2    (the forced 121,121 pair)       2")
print("  8 rotations x 3 instructions             24")
print("  MOVD x2   (bring d back to 72)            2")
print("  JMP                                       1")
print("  total                                    33  -> addresses 0..32")
print("  the JMP at 32 enciphers its TARGET, not itself, so 0..31 are enciphered.")

hdr("(e) an enciphered cell is ALWAYS still executable")
print("XLAT2 maps 33..126 onto 33..126, so a cell that has executed still holds a")
print("printable word.  The VM errors only on a NON-PRINTABLE word; a printable")
print("word that decodes outside the eight instruction codes is a runtime NOP --")
print("crates/classic_malbolge/src/lib.rs step():  `_ => {}`.")
tot = ok = 0
per = {}
for a in range(300):
    good = []
    for k in VALID_CODES:
        k2 = code_of(XLAT2[byte_for(k, a) - 33], a)
        tot += 1
        if k2 in VALID_CODES:
            ok += 1
            good.append((NAMES[k], NAMES[k2]))
    per[a] = good
print(f"\nover addresses 0..299, {ok}/{tot} = {ok/tot:.1%} of (address, first-pass code)")
print("pairs re-decode to one of the eight codes.  The other 92.5% are NOPs.")
print("So an executed prologue is a NOP SLED, not a minefield.")

hdr("(f) what b = 0,1,2,3 actually do -- they are not dead")
print("The dispatch JMP at the end of the prologue is never enciphered: the")
print("canonical cycle sets c = m[d] FIRST and then enciphers m[c], so the TARGET")
print("cell (9b) is enciphered and the JMP's own cell keeps its byte.  An input")
print("that lands inside the enciphered prologue therefore slides forward to that")
print("JMP and executes it a second time, now with")
print("    d = 73 + (prologue_last - entry)")
print("and lands on m[d] + 1 -- a SECOND, per-input dispatch off a cell we choose.")
print()
PRO = [23] + [40]*3 + [62]*2 + [40,40,39]*8 + [40,40,4]     # prior art's prologue
JMPADDR = len(PRO) - 1
sled = {}
for a in range(JMPADDR):
    sled[a] = code_of(XLAT2[byte_for(PRO[a], a) - 33], a)
for b in range(4):
    e = 9*b + 1
    real = [(a, NAMES[sled[a]]) for a in range(e, JMPADDR) if sled[a] in VALID_CODES]
    print(f"  b={b}: enters at {e:2d}, real instructions in the sled: "
          f"{real if real else 'NONE (clean sled)'};  reaches JMP@{JMPADDR} with d = "
          f"{73 + JMPADDR - e}, so it re-dispatches through m[{73 + JMPADDR - e}]")
print()
print("b=2 and b=3 have clean sleds.  b=1 hits nothing either.  Only b=0 is killed")
print("by the prologue itself: address 1 must hold the first MOVD, and a MOVD at")
print("address 1 enciphers into IN, which reads the SECOND byte of the 32-byte")
print("case input -- a seed-derived value.  See prologue2.py for the chain search")
print("that moves the first MOVD off address 1 (it costs one extra hop, and in")
print("the shifted layout address 10 then holds ROT, which enciphers into HLT and")
print("kills b=0 and b=1 instead).  The trade is real but it is a LAYOUT problem,")
print("not an arithmetic wall: this attempt's shipped candidate solves b=2.")
print()
print("So there is NO 252 ceiling.  The four low inputs are a second search")
print("problem -- choose the prologue phase so no enciphered cell in any sled is")
print("a real instruction, and tune the four re-dispatch cells -- and it was not")
print("solved here.")


hdr("(g) why the block base cannot be pushed past the prologue")
print("the base is m[72] rotated left 2 trits, and")
print("  rotl^2(V) = 9*(V mod 3^8) + (V div 3^8),")
print("so any offset K = t8 + 3*t9 is at most 8.  With BYTE operands the two")
print("crazies apply M0 twice to trits 8,9 of a value whose trits 8,9 are 0,")
print("which returns 0, so K = 0 exactly.  Even a runtime-built operand caps K")
print("at 8, and 9*3 + 1 = 28 is still inside the prologue.  Widening the stride")
print("to 27 (which would give private DATA as well as private code) needs")
print("27*255 + 27 = 6912 cells -- past this rung's 4096-byte cap, and the first")
print("thing in this rung's history for which the length cap actually binds.")
