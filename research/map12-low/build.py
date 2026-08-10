#!/usr/bin/env python3
"""Build the L2.FM2l.xor51-map12-low candidate: cov48's data-dispatch table,
re-aimed at twelve inputs with a generalised offset K0 = 1134 (a multiple of 81,
not of 729 -- see research/map12-low/chain.c) and a table chosen by the
max-count DP in research/map12-low/maxtable.c.

Architecture (see docs/attempts/2026-08-10-claude-cov48.md):

    prefix of NOPs          C walks 0..prefix_end-1, enciphering each cell to x(a),
                            so cell a is a ready-made "MOVD to x(a)+1" pointer
    chain (research/cov48/chain2.c)
        CRZ 41, ROT 41 x4               -> mem[41] = W1 = 32440
        CRZ 43, CRZ 63, ROT 63 x4       -> mem[63] = W2 = 6196
    IN                      A = b
    CRZ 41, CRZ 63          A = crazy(crazy(b, W1), W2) = b + 2916  exactly,
                            because M1 o M1 = id on trits 0..5 and the high trits
                            of the pair contribute 4*729 = 2916.  A is parked in
                            cell 63 by the second CRAZY's write-back.
    MOVD on cell 63         D = mem[63] + 1 = b + 2917   <-- the input IS the index
    CRZ x6                  A = crazy^6(b+2916, mem[b+2917 .. b+2922])
    OUT, HALT               out = A mod 256

The six table bytes per input are chosen by the exact DP in
research/cov48/table_solve.c: each table address admits exactly eight
loader-valid bytes, consecutive inputs share five of their six cells, so the
optimum over the whole 261-cell table is a transfer-matrix DP on 8^5 states.
It reports 71/256 for K0 = 2916, k = 6 -- the rung needs 48.
"""
import subprocess, sys

ENC = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CODE_NOP, CODE_OUT, CODE_IN, CODE_ROT, CODE_MOVD, CODE_CRZ, CODE_HALT = 68, 5, 23, 39, 40, 62, 81

K0, K = 2106, 5
# research/map12-low/chain.c: W1 = 29524 in cell 45, W2 = 28390 in cell 44
CHAIN = [("crz", 45),
         ("crz", 36), ("crz", 44),
         ("rot", 44), ("rot", 44), ("rot", 44), ("rot", 44), ("rot", 44), ("rot", 44)]
Q_W1, Q_W2 = 45, 44
DATA_CELLS = [36, 44, 45]


def codebyte(addr, code):
    b = (code - addr) % 94
    if b < 33:
        b += 94
    assert 33 <= b <= 126
    return b


def xval(addr):
    return ENC[codebyte(addr, CODE_NOP) - 33]


class Builder:
    def __init__(self, prefix_end, reserved):
        self.prog, self.addr, self.d = {}, prefix_end, prefix_end
        self.first, self.reserved, self.prefix_end = True, set(reserved), prefix_end

    def emit(self, code):
        self.prog[self.addr] = codebyte(self.addr, code)
        self.addr += 1
        self.d += 1

    def movd(self, q):
        if self.first:
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


def table():
    out = subprocess.run([sys.argv[2] if len(sys.argv) > 2 else "/tmp/mt",
                          str(K0), str(K), "emit"], capture_output=True, check=True)
    cells = {}
    for line in out.stdout.decode().split("\n"):
        if line.strip():
            a, v = line.split()
            cells[int(a)] = int(v)
    return cells


def build(prefix_end, tbl):
    b = Builder(prefix_end, DATA_CELLS)
    for op, q in CHAIN:
        b.movd(q)
        b.emit(CODE_CRZ if op == "crz" else CODE_ROT)
    b.emit(CODE_IN)
    b.movd(Q_W1); b.emit(CODE_CRZ)          # A = crazy(b, W1)
    b.movd(Q_W2); b.emit(CODE_CRZ)          # A = b + K0, parked in cell Q_W2
    b.movd(Q_W2); b.emit(CODE_MOVD)         # D = mem[Q_W2] + 1 = b + K0 + 1
    for _ in range(K):
        b.emit(CODE_CRZ)                    # walk the six table cells
    b.emit(CODE_OUT); b.emit(CODE_HALT)
    if b.addr > K0:
        raise RuntimeError("code collided with the table")
    end = max(tbl) + 1
    src = bytearray(codebyte(a, CODE_NOP) for a in range(end))
    for a, v in b.prog.items():
        src[a] = v
    for a, v in tbl.items():
        src[a] = v
    return bytes(src), b.addr


if __name__ == "__main__":
    tbl = table()
    out = sys.argv[1] if len(sys.argv) > 1 else "cand.mal"
    for pe in (128, 160, 192, 224, 256, 320, 384, 512):
        try:
            program, code_end = build(pe, tbl)
        except RuntimeError:
            continue
        break
    else:
        raise SystemExit("no prefix length worked")
    with open(out, "wb") as fh:
        fh.write(program)
    print(f"wrote {out} ({len(program)} bytes, prefix_end={pe}, code ends at {code_end})")
