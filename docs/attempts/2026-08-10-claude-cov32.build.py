#!/usr/bin/env python3
"""Build the L2.C0.xor51-cov32 winner: a straight-line two-CRAZY program.

No search, no backtracking: the whole program is derived analytically from the
pinned Classic-Malbolge-51 v0 rules in docs/classic-malbolge-51-v0.md.

The idea
--------
Every reachable straight-line data path in classic Malbolge is, per trit,
position-wise: CRAZY with a constant applies one of three unary trit maps
m0/m1/m2 at each position, and ROTATE permutes positions cyclically.  After N
CRAZY ops the map at output trit position i is some composition of N generators,
chosen independently per position, so

    out = sum_i g_i(trit_{i+s}(b)) * 3^i        (output byte = out mod 256)

The companion ceiling script searches that whole family exhaustively.  Its optimum is
34/256; the cheapest point that clears the rung's threshold of 32 is

    N = 2, s = 0, g_i = identity for i = 0..5

which makes out = b + K where K is the constant contributed by trit positions
6..9 (input trits there are always 0 for a byte).  With K = 81 = 0x51 that is
b + 0x51, which equals b XOR 0x51 on exactly the 32 bytes with b AND 0x51 == 0.

Identity at a position needs m1 twice, i.e. both CRAZY operands must carry trit
1 there; positions 6..9 need a trit pattern whose h-values sum to K.  A byte
operand cannot do this: bytes are < 3^5, so their trits 5..9 are all 0 and the
resulting K can only be 0 or 232.  Nor can any crazy-fill cell — every cell in
the fill region inherits trits 5..9 from the last two source bytes, which are
all zero, so those five positions evolve identically.  Breaking that symmetry
requires a ROTATE, so the two operands are manufactured at run time:

    c = rot^5(crazy(0, x))     -- trits 0..5 all 1, trits 6..9 free in {1,2}

Layout
------
Every prefix cell is the unique byte that decodes to NOP (68) at its own
address, so after C walks over the prefix, cell a holds x(a) = encipher(nop(a)).
That single table does double duty: x(q) is the seed byte a manufacturing cell
offers, and a cell with x(a) = q-1 is a usable "MOVD -> q" pointer (MOVD sets
D = mem[D], then the post-instruction increment adds one).  Data cells therefore
live at addresses 34..127, since a pointer value must itself be a printable byte.

The tail: manufacture cA at qA (A is still 0), rotate it five times, zero A again
against a scratch cell, manufacture cB at qB, rotate five times, IN, CRAZY qB,
CRAZY qA, OUT, HALT.
"""

ENC = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CODE_NOP, CODE_JMP, CODE_OUT, CODE_IN, CODE_ROT, CODE_MOVD, CODE_CRZ, CODE_HALT = 68, 4, 5, 23, 39, 40, 62, 81


def codebyte(addr, code):
    """The unique printable byte that decodes to `code` at `addr`."""
    b = (code - addr) % 94
    if b < 33:
        b += 94
    assert 33 <= b <= 126
    return b


def xval(addr):
    """Value of a prefix (NOP) cell at `addr` after C has executed and enciphered it."""
    return ENC[codebyte(addr, CODE_NOP) - 33]


def qfor(x):
    """The data cell in 34..127 whose post-encipher value is the seed byte x."""
    for q in range(34, 128):
        if xval(q) == x:
            return q
    return None


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


def build(qA, qB, qs, order, rotations=5, prefix_end=384):
    b = Builder(prefix_end, (qA, qB, qs))
    b.movd(qA); b.emit(CODE_CRZ)                        # mem[qA] = crazy(0, x(qA))
    for _ in range(rotations):
        b.movd(qA); b.emit(CODE_ROT)                    # ... rot^5 -> cA, A = cA
    b.movd(qs); b.emit(CODE_CRZ)                        # A = crazy(cA, x(qs)) = 0
    b.movd(qB); b.emit(CODE_CRZ)                        # mem[qB] = crazy(0, x(qB))
    for _ in range(rotations):
        b.movd(qB); b.emit(CODE_ROT)                    # ... rot^5 -> cB
    b.emit(CODE_IN)                                     # A = input byte
    q1, q2 = (qA, qB) if order == "AB" else (qB, qA)
    b.movd(q1); b.emit(CODE_CRZ)                        # A = crazy(A, c1)
    b.movd(q2); b.emit(CODE_CRZ)                        # A = crazy(A, c2)
    b.emit(CODE_OUT); b.emit(CODE_HALT)
    src = bytearray(codebyte(a, CODE_NOP) for a in range(b.addr))
    for a, v in b.prog.items():
        src[a] = v
    return bytes(src)


# The shipped winner. Seeds 79 and 123 give the operand pair (39001, 30253):
# trits 0..5 all 1, high trits (2,2,2,1) and (2,1,1,1) -> K = 81.
WINNER = dict(qA=114, qB=86, qs=79, order="BA")

if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "cov32-two-crazy.mal"
    program = build(**WINNER)
    with open(out, "wb") as fh:
        fh.write(program)
    print(f"wrote {out} ({len(program)} bytes)")
