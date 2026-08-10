#!/usr/bin/env python3
"""Build the L2.C0a.xor51-cov34 candidate: a straight-line two-CRAZY program.

cov34 asks for 34/256, which research/cov32/family_ceiling.py proved is the
exact ceiling of the whole branchless CRAZY/ROTATE family.  So this rung has no
slack at all: the program must realise the family optimum exactly.

research/cov34/argmax.c enumerates the N=2 family's argmax and finds the 34-point
is essentially unique -- 9 configurations that agree on every input below 243:

    trits 0..3 of both operands = 1          -> identity, out = b there
    (c1_4, c2_4) = (1, 0)                    -> g_4 = m0 o m1 = (0,1,0)
    high trits contributing the constant 81

cov32 shipped the 32-point (identity at 0..5, out = b + 0x51, right on the 32
bytes with b AND 0x51 == 0).  The two extra hits come from that (0,1,0) at trit
position 4, which fires on the bytes with trit_4 = 2 and b AND 0x51 == 0x51.

The obstruction cov32 did not have to solve: c2 needs a *zero* trit at position
4.  Every operand of the form rot^k(crazy(0, byte)) -- cov32's whole
manufacturing technique -- has all ten trits in {1,2}, because crazy(0, .) maps
every trit to 1 or 2 and rotation only permutes.  So the cov32 operand family
cannot express c2 at all, and a second CRAZY layer is structurally required.

research/cov34/search.c settles it by BFS over the 59,049-word space under the
two ops actually available (A <- crazy(A, seed byte) on a fresh cell, A <- rot(A)
on the cell A was just written to), and research/cov34/chain.c finds the cheapest
chain: 12 ops total, cut in the middle.  No accumulator reset is needed -- the
second operand is built *starting from* the first, which stays parked in its
cell.  Every CRAZY consumes its cell, and x() is injective on 34..127, so the
chain is additionally constrained to use each seed byte at most once.

    CRZ 34, CRZ 35, CRZ 91, ROT 91 x3     -> mem[91] = c1 = 5467
    CRZ 44, CRZ 68, ROT 68 x4             -> mem[68] = c2 = 43780
    IN, CRZ 91, CRZ 68, OUT, HALT         -> emits crazy(crazy(b,c1),c2) mod 256

Layout is cov32's: every prefix cell holds the unique byte decoding to NOP at its
own address, so after C walks the prefix, cell a holds x(a) = encipher(nop(a)),
and a cell with x(a) = q-1 is a ready-made "MOVD to q" pointer.
"""

ENC = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CODE_NOP, CODE_OUT, CODE_IN, CODE_ROT, CODE_MOVD, CODE_CRZ, CODE_HALT = 68, 5, 23, 39, 40, 62, 81


def codebyte(addr, code):
    b = (code - addr) % 94
    if b < 33:
        b += 94
    assert 33 <= b <= 126
    return b


def xval(addr):
    return ENC[codebyte(addr, CODE_NOP) - 33]


class Builder:
    """Emits instructions while tracking D, inserting NOPs until D lands on a pointer."""

    def __init__(self, prefix_end, reserved):
        self.prog, self.addr, self.d = {}, prefix_end, prefix_end
        self.first, self.reserved, self.prefix_end = True, set(reserved), prefix_end

    def emit(self, code):
        self.prog[self.addr] = codebyte(self.addr, code)
        self.addr += 1
        self.d += 1

    def movd(self, q):
        if self.first:
            # D still equals C, so the MOVD reads its own (not yet enciphered) byte.
            while ((q - 1) + self.addr) % 94 != CODE_MOVD:
                self.emit(CODE_NOP)
            self.prog[self.addr] = q - 1
            self.addr += 1
            self.d = q
            self.first = False
            return
        while xval(self.d) != q - 1 or self.d in self.reserved:
            self.emit(CODE_NOP)
            if self.d >= self.prefix_end:
                raise RuntimeError("D walked past the prefix")
        self.prog[self.addr] = codebyte(self.addr, CODE_MOVD)
        self.addr += 1
        self.d = q


# (op, cell) chain from research/cov34/chain.c; cells carry the seed bytes
#   x(34)=122  x(35)=53  x(91)=83  x(44)=107  x(68)=57
CHAIN = [("crz", 34), ("crz", 35), ("crz", 91), ("rot", 91), ("rot", 91), ("rot", 91),
         ("crz", 44), ("crz", 68), ("rot", 68), ("rot", 68), ("rot", 68), ("rot", 68)]
Q_C1, Q_C2 = 91, 68
DATA_CELLS = [34, 35, 91, 44, 68]


def build(prefix_end=512):
    b = Builder(prefix_end, DATA_CELLS)
    for op, q in CHAIN:
        b.movd(q)
        b.emit(CODE_CRZ if op == "crz" else CODE_ROT)
    b.emit(CODE_IN)                     # A = input byte
    b.movd(Q_C1); b.emit(CODE_CRZ)      # A = crazy(b, c1)
    b.movd(Q_C2); b.emit(CODE_CRZ)      # A = crazy(A, c2)
    b.emit(CODE_OUT); b.emit(CODE_HALT)
    src = bytearray(codebyte(a, CODE_NOP) for a in range(b.addr))
    for a, v in b.prog.items():
        src[a] = v
    return bytes(src)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "cov34-two-crazy.mal"
    for pe in (384, 512, 768, 1024, 1536, 2048):
        try:
            program = build(pe)
        except RuntimeError:
            continue
        break
    else:
        raise SystemExit("no prefix length worked")
    with open(out, "wb") as fh:
        fh.write(program)
    print(f"wrote {out} ({len(program)} bytes, prefix_end={pe})")
