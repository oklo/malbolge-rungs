#!/usr/bin/env python3
"""Build the L4.R0.hash-prefix-1 candidate: one CRAZY, OUT, HALT.

search.py shows A = crazy(0, 47) = 29534, and 29534 % 256 == 94 == 0x5e,
which is the epoch-0 target byte for this rung.  So the whole program is

    MOVD q ; CRZ ; OUT ; HALT

with q the first data cell whose post-encipher value x(q) is 47.  Everything
before that is the NOP prefix that makes the MOVD pointer land.  Builder is
lifted from research/cov32/build.py (same prefix/pointer discipline).
"""
from search import ENC, codebyte, xval, crazy, operands  # noqa: F401

CODE_NOP, CODE_OUT, CODE_IN, CODE_ROT, CODE_MOVD, CODE_CRZ, CODE_HALT = 68, 5, 23, 39, 40, 62, 81


class Builder:
    def __init__(self, prefix_end, reserved=()):
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


def qfor(value):
    for q in range(34, 128):
        if xval(q) == value:
            return q
    raise RuntimeError(f"no data cell carries {value}")


def build(operand=47, prefix_end=200, read_input=False):
    q = qfor(operand)
    b = Builder(prefix_end, (q,))
    if read_input:
        b.emit(CODE_IN)          # consume one input byte into A (then overwritten)
    b.movd(q)
    b.emit(CODE_CRZ)             # A = crazy(A, x(q))
    b.emit(CODE_OUT)
    b.emit(CODE_HALT)
    src = bytearray(codebyte(a, CODE_NOP) for a in range(b.addr))
    for a, v in b.prog.items():
        src[a] = v
    return bytes(src)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "cand.mal"
    program = build()
    with open(out, "wb") as fh:
        fh.write(program)
    print(f"wrote {out} ({len(program)} bytes), operand cell q={qfor(47)}")
