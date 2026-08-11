#!/usr/bin/env python3
"""Build the L2.FM2l.xor51-map12-low candidate with a NOP-SPACED table walk.

This is the 2026-08-10 data-dispatch table architecture with the two freedoms
that record's "what I would try next" named but did not spend budget on:

  * a phase shift `s` (NOPs between the MOVD and the first table CRAZY), which
    moves the table base to any residue mod 94 independently of K0, and
  * a non-consecutive walk pattern P, realised by NOPs between the CRAZYs.

Every walk gap is chosen so that no two of the twelve inputs ever share a table
cell (all pairwise input differences avoid P - P).  The lanes then decouple
completely, which dissolves the joint transfer-matrix UNSAT that capped the
prior attempt at 10/12.

  IN                      A = b
  CRZ W1, CRZ W2          A = b + K0, parked in cell Q_W2
  MOVD                    D = b + K0 + 1
  NOP^s                   D = base + b,  base = K0 + 1 + s
  CRZ/NOP pattern P       A = crazy^5(b+K0, mem[base+b+p_1 .. ])
  OUT, HALT               out = A mod 256

usage: build_spaced.py OUT.mal [K0] [R] [P comma-list]
"""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lowmodel import *

ENC = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
NOP, OUT, IN, ROT, MOVD, CRZ, HALT = 68, 5, 23, 39, 40, 62, 81

K0 = int(sys.argv[2]) if len(sys.argv) > 2 else 2106
R = int(sys.argv[3]) if len(sys.argv) > 3 else 0
P = [int(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else [0, 10, 20, 64, 74]
K = len(P)
SPAN = P[-1]

# Constant chains from research/map12-low/chain.c, transcribed with the cell each
# ROT acts on (chain.c prints "ROT" meaning "rotate the cell the last CRAZY wrote").
# W1 must survive leg 2, so leg 2's last cell has to differ from leg 1's -- chain.c
# does not enforce that, and its shortest chains for K0 = 1134 / 1620 / 1863 all
# end both legs on the same cell and are therefore unusable.
CHAINS = {
    2106: ([("crz", 45), ("crz", 36), ("crz", 44)] + [("rot", 44)] * 6, 45, 44),
    1377: ([("crz", 34)] + [("rot", 34)] * 4 + [("crz", 36), ("crz", 44)]
           + [("rot", 44)] * 6, 34, 44),
}
CHAIN, Q_W1, Q_W2 = CHAINS[K0]
DATA_CELLS = sorted({q for _, q in CHAIN})

assert collision_free(P), "pattern shares cells between lanes"


def codebyte(addr, code):
    b = (code - addr) % 94
    if b < 33:
        b += 94
    assert 33 <= b <= 126
    return b


def xval(addr):
    return ENC[codebyte(addr, NOP) - 33]


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
            while ((q - 1) + self.addr) % 94 != MOVD:
                self.emit(NOP)
            self.prog[self.addr] = q - 1
            self.addr += 1
            self.d = q
            self.first = False
            return
        while xval(self.d) != q - 1 or self.d in self.reserved:
            self.emit(NOP)
            if self.d >= self.prefix_end:
                raise RuntimeError("D walked past the prefix")
        self.prog[self.addr] = codebyte(self.addr, MOVD)
        self.addr += 1
        self.d = q


# ---- per-lane table bytes (lanes are independent because P is collision free)
def lane_bytes(base, b, want):
    """choose one legal byte per walk cell so that trits 0..4 of the
    accumulator end at `want`; start state is b + 81*2 (K0's trit4 is 2)."""
    addrs = [base + b + p for p in P]
    start = b + 81 * ((K0 // 81) % 3)

    def cr5(a, v):
        o, f = 0, 1
        for _ in range(5):
            o += CR[v % 3][a % 3] * f
            a //= 3
            v //= 3
            f *= 3
        return o

    back = [None] * (K + 1)
    back[K] = {want}
    for i in range(K - 1, -1, -1):
        vals = legal_bytes(addrs[i] % 94)
        back[i] = {a for a in range(243) if any(cr5(a, v) in back[i + 1] for v in vals)}
    if start not in back[0]:
        return None
    cur, chosen = start, []
    for i in range(K):
        for v in legal_bytes(addrs[i] % 94):
            if cr5(cur, v) in back[i + 1]:
                chosen.append(v)
                cur = cr5(cur, v)
                break
        else:
            return None
    assert cur == want
    return dict(zip(addrs, chosen))


def build(prefix_end):
    bd = Builder(prefix_end, DATA_CELLS)
    for op, q in CHAIN:
        bd.movd(q)
        bd.emit(CRZ if op == "crz" else ROT)
    bd.emit(IN)
    bd.movd(Q_W1); bd.emit(CRZ)
    bd.movd(Q_W2); bd.emit(CRZ)          # A = b + K0, parked in Q_W2
    bd.movd(Q_W2); bd.emit(MOVD)         # D = b + K0 + 1
    movd_end = bd.addr
    s = (R - (K0 + 1)) % 94
    base = K0 + 1 + s
    for _ in range(s):
        bd.emit(NOP)                     # D = base + b
    for i in range(SPAN + 1):
        bd.emit(CRZ if i in P else NOP)
    bd.emit(OUT)
    bd.emit(HALT)
    code_end = bd.addr
    if code_end > base + min(INPUTS):
        raise RuntimeError("code (%d) runs into the table (%d)" % (code_end, base + min(INPUTS)))

    # frozen high part H: trits 5..9 after K crazies with printable operands
    hi_src = K0 // 243
    hi_final = sum(((min((hi_src // 3 ** j) % 3, 1) + K) % 2) * 3 ** j for j in range(5))
    H = 243 * hi_final
    tbl, miss = {}, []
    for b in INPUTS:
        Ls = (TARGETS[b] - H % 256) % 256
        if Ls > 242:
            miss.append(b); continue
        got = lane_bytes(base, b, Ls)
        if got is None:
            miss.append(b); continue
        tbl.update(got)
    end = max(max(tbl), code_end) + 1
    src = bytearray(codebyte(a, NOP) for a in range(end))
    for a, v in bd.prog.items():
        src[a] = v
    for a, v in tbl.items():
        assert a >= code_end, "table cell %d inside code" % a
        src[a] = v
    return bytes(src), dict(base=base, s=s, H=H, movd_end=movd_end,
                            code_end=code_end, miss=miss, prefix_end=prefix_end)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "cand.mal"
    last = None
    for pe in (128, 160, 192, 224, 256, 288, 320, 384, 448, 512, 640):
        try:
            prog, info = build(pe)
        except RuntimeError as e:
            last = e
            continue
        break
    else:
        raise SystemExit("no prefix length worked: %s" % last)
    open(out, "wb").write(prog)
    print("wrote %s  %d bytes" % (out, len(prog)))
    print("  K0=%d K=%d P=%s span=%d R=%d" % (K0, K, P, SPAN, R))
    print("  prefix_end=%(prefix_end)d movd_end=%(movd_end)d s=%(s)d base=%(base)d "
          "code_end=%(code_end)d H=%(H)d" % info)
    print("  model-level misses: %s" % ([hex(x) for x in info["miss"]] or "none - 12/12"))
