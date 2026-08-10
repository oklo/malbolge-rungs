#!/usr/bin/env python3
"""Build a candidate for L5.R0.future-transform (NibbleMap, 4 output bytes).

The rung wants, for each of 4 hash-derived cases, the nibble swap
((b<<4)|(b>>4)) & 0xFF of each of the first four input bytes -- 16 exact bytes
per epoch, and the inputs are re-derived from the seed on every epoch, so
nothing input-specific can be baked in.

This builder emits the strongest *straight-line* candidate: four independent
stages, each `IN; CRAZY v1; CRAZY v2; OUT`, where (v1, v2) is the pair of data
cell values whose composed trit maps agree with the nibble swap on as many of
the 256 byte values as possible.  CRAZY overwrites its own operand cell
(mem[d] = crazy(a, mem[d])), so each of the four stages must use its own pair
of cells, and the four pairs are chosen greedily and disjointly.

Why the operands are plain data-cell bytes and not manufactured constants:
a MOVD target must be a value already sitting in memory, and every value in a
fresh program's memory is a printable byte (<= 126), so D can only ever be
redirected into cells 34..127 -- 94 cells, each holding a distinct value under
the NOP-prefix layout below.  Manufacturing a wide operand the way
research/cov32/build.py does costs ~12 instructions and would have to be
repeated per stage, which does not fit the rung's 1024-byte program cap
alongside four dispatch stages.

Layout is the cov32 layout: every prefix cell holds the unique byte that
decodes to NOP at its own address, so after C walks the prefix, cell a holds
x(a) = encipher(nop_byte(a)).  That table does double duty -- x(q) is the
constant cell q offers, and a cell with x(a) = q-1 is a ready-made "MOVD to q".

    python3 research/future-transform/build.py > cand.mal
"""

import sys

ENC = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CODE_NOP, CODE_JMP, CODE_OUT, CODE_IN, CODE_ROT, CODE_MOVD, CODE_CRZ, CODE_HALT = 68, 4, 5, 23, 39, 40, 62, 81

CRAZY = ((1, 0, 0), (1, 0, 2), (2, 2, 1))  # CRAZY[mem_trit][a_trit]


def trits(w):
    out = []
    for _ in range(10):
        out.append(w % 3)
        w //= 3
    return out


def from_trits(t):
    v = 0
    for i in range(9, -1, -1):
        v = v * 3 + t[i]
    return v


def crazy(a, mem):
    """The machine's CRAZY: value = crazy_word(a, mem[d]); trit = op[mem][a]."""
    ta, tm = trits(a), trits(mem)
    return from_trits([CRAZY[tm[i]][ta[i]] for i in range(10)])


def codebyte(addr, code):
    b = (code - addr) % 94
    if b < 33:
        b += 94
    assert 33 <= b <= 126
    return b


def xval(addr):
    """Value of a prefix (NOP) cell at `addr` after C executed and enciphered it."""
    return ENC[codebyte(addr, CODE_NOP) - 33]


def nibble_swap(b):
    return ((b << 4) | (b >> 4)) & 0xFF


# ---------------------------------------------------------------- pair search

def search_pairs():
    """Score every (cell, cell) operand pair by agreement with the nibble swap."""
    cells = list(range(34, 128))
    vals = {q: xval(q) for q in cells}
    target = [nibble_swap(b) for b in range(256)]
    w1 = {q: [crazy(b, vals[q]) for b in range(256)] for q in cells}
    scored = []
    for q1 in cells:
        col = w1[q1]
        for q2 in cells:
            if q2 == q1:
                continue
            v2 = vals[q2]
            hits = 0
            for b in range(256):
                if crazy(col[b], v2) % 256 == target[b]:
                    hits += 1
            scored.append((hits, q1, q2))
    scored.sort(reverse=True)
    return scored


def pick_disjoint(scored, count=4):
    used, chosen = set(), []
    for hits, q1, q2 in scored:
        if q1 in used or q2 in used:
            continue
        used.update((q1, q2))
        chosen.append((hits, q1, q2))
        if len(chosen) == count:
            break
    return chosen


# ---------------------------------------------------------------- emitter

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


def build(pairs, prefix_end=288):
    data = [q for _, q1, q2 in pairs for q in (q1, q2)]
    b = Builder(prefix_end, data)
    for _, q1, q2 in pairs:
        b.emit(CODE_IN)          # A = next input byte
        b.movd(q1); b.emit(CODE_CRZ)   # A = crazy(A, x(q1))
        b.movd(q2); b.emit(CODE_CRZ)   # A = crazy(A, x(q2))
        b.emit(CODE_OUT)         # emit A mod 256
    b.emit(CODE_HALT)
    end = b.addr
    out = bytearray()
    for a in range(end):
        out.append(b.prog.get(a, codebyte(a, CODE_NOP)))
    return bytes(out)


def build_identity():
    """The ceiling-optimal straight-line program: IN;OUT four times, then HALT.

    straightline_ceiling.c shows the whole CRAZY/ROTATE family tops out at
    16/256 agreement with the nibble swap, attained at N=0 -- the identity.
    So the best straight-line candidate on this rung emits the input byte
    unchanged, which is right exactly on the 16 bytes whose nibbles are equal.
    """
    prog = bytearray()
    for _ in range(4):
        prog.append(codebyte(len(prog), CODE_IN))
        prog.append(codebyte(len(prog), CODE_OUT))
    prog.append(codebyte(len(prog), CODE_HALT))
    return bytes(prog)


if __name__ == "__main__":
    if "--identity" in sys.argv:
        prog = build_identity()
        print(f"# identity candidate, {len(prog)} bytes, 16/256 per byte",
              file=sys.stderr)
        sys.stdout.buffer.write(prog)
        raise SystemExit(0)
    scored = search_pairs()
    chosen = pick_disjoint(scored)
    for hits, q1, q2 in chosen:
        print(f"# stage: cells {q1},{q2} values {xval(q1)},{xval(q2)} "
              f"agreement {hits}/256", file=sys.stderr)
    prog = build(chosen)
    print(f"# program length {len(prog)} bytes", file=sys.stderr)
    sys.stdout.buffer.write(prog)
