#!/usr/bin/env python3
"""Emit the L2.FM3.xor51-map16 candidate.

    sled           addresses 0..PREFIX-1, all NOP; C executes them, so every
                   prefix cell q afterwards holds xval(q) = ENC[codebyte(q,NOP)-33]
    chain          MOVD/CRZ/ROT ops that park W1 in cell P and W2 in cell Qb
    IN             A = b
    CRZ W1, CRZ W2 A = A0(b) = sum_i g_i(b_i) 3^i, parked in Qb
    MOVD on Qb     D = A0(b) + 1
    NOP^s          D = A0(b) + 1 + s
    CRZ/NOP walk   lane b consumes cells A0(b)+1+s+p_i
    OUT, HALT      out = A mod 256

usage: build.py OUT.mal [s] [P comma-list]
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from model import (INPUTS, TARGETS, crazy, trits, legal_bytes, codebyte, xval,
                   NOP, OUT, IN, ROT, MOVD, CRZ, HALT)  # noqa: E402
import spec as S  # noqa: E402

PREFIX = 256

# --- the configuration chainfind.py picked -----------------------------------
SPEC = ((0, 1, 2), (0, 1, 0), (0, 1, 2), (2, 2, 0), (2, 2, 0), (0, 1, 2))
CT = (2, 0, 0, 0)
W1, W2 = 30361, 29521
LEG1 = [("crz", 62)] + [("rot", None)] * 7
LEG2 = [("crz", 33), ("crz", 54)]


def cell_with(v):
    """the unique prefix cell in 34..127 whose post-sled content is v."""
    for q in range(34, 128):
        if xval(q) == v:
            return q
    raise KeyError(v)


def addr_of(b):
    bt = trits(b, 6)
    a = sum(SPEC[i][bt[i]] * 3 ** i for i in range(6))
    return a + sum(CT[i] * 3 ** (6 + i) for i in range(4))


ADDR = {b: addr_of(b) for b in INPUTS}
assert len(set(ADDR.values())) == 16


def requirements(K):
    """(L*, start trit4, live) per lane."""
    hbase = sum(((min(CT[i], 1) + K) % 2) * 3 ** (i + 1) for i in range(4))
    h = [(243 * (((min(u, 1) + K) % 2) + hbase)) % 256 for u in range(3)]
    out = {}
    for b in INPUTS:
        A = ADDR[b]
        Ls = (TARGETS[b] - h[(A % 729) // 243]) % 256
        st = (A // 81) % 3
        if Ls > 242:
            out[b] = (Ls, st, False)
            continue
        live = st == 2 or (Ls // 81) == (st + K) % 2
        out[b] = (Ls, st, live)
    return out


DIFFS = {abs(ADDR[x] - ADDR[y]) for x in INPUTS for y in INPUTS if x != y}


def collision_free(P):
    return all((P[j] - P[i]) not in DIFFS
               for i in range(len(P)) for j in range(i + 1, len(P)))


def cr5(a, v):
    o, f = 0, 1
    for _ in range(5):
        o += [[1, 0, 0], [1, 0, 2], [2, 2, 1]][v % 3][a % 3] * f
        a //= 3; v //= 3; f *= 3
    return o


def lane_bytes(b, P, s, want):
    """one legal byte per walk cell driving trits 0..4 to `want`."""
    addrs = [ADDR[b] + 1 + s + p for p in P]
    start = ADDR[b] % 243
    K = len(P)
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
                chosen.append(v); cur = cr5(cur, v); break
        else:
            return None
    return dict(zip(addrs, chosen))


class Builder:
    def __init__(self, reserved):
        self.prog, self.addr, self.d = {}, PREFIX, PREFIX
        self.first, self.reserved = True, set(reserved)

    def emit(self, code):
        self.prog[self.addr] = codebyte(self.addr, code)
        self.addr += 1
        self.d += 1

    def raw(self, byte):
        self.prog[self.addr] = byte
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
            if self.d >= PREFIX:
                raise RuntimeError("D walked past the sled at %d" % self.d)
        self.prog[self.addr] = codebyte(self.addr, MOVD)
        self.addr += 1
        self.d = q


def build(P, s):
    K = len(P)
    req = requirements(K)
    cells = {}
    P_cell = cell_with(LEG1[0][1])
    leg2_cells = [cell_with(v) for _, v in LEG2]
    reserved = [P_cell] + leg2_cells
    assert len(set(reserved)) == len(reserved), "chain cells collide"

    bd = Builder(reserved)
    # leg 1: CRZ into P_cell, then ROTs on the same cell
    bd.movd(P_cell); bd.emit(CRZ)
    for op, _ in LEG1[1:]:
        bd.movd(P_cell); bd.emit(ROT)
    # leg 2: CRAZY into fresh cells (this is what keeps W1 alive)
    for q in leg2_cells:
        bd.movd(q); bd.emit(CRZ)
    Q_W2 = leg2_cells[-1]

    bd.emit(IN)
    bd.movd(P_cell); bd.emit(CRZ)          # A = crazy(b, W1)
    bd.movd(Q_W2); bd.emit(CRZ)            # A = A0(b), parked in Q_W2
    bd.movd(Q_W2); bd.emit(MOVD)           # D = A0(b) + 1
    for _ in range(s):
        bd.emit(NOP)
    for i in range(P[-1] + 1):
        bd.emit(CRZ if i in P else NOP)
    bd.emit(OUT)
    bd.emit(HALT)
    code_end = bd.addr

    live = [b for b in INPUTS if req[b][2]]
    first_cell = min(ADDR[b] for b in live) + 1 + s + P[0]
    if code_end >= first_cell:
        raise RuntimeError("code %d runs into the table %d" % (code_end, first_cell))
    if code_end > 2040:
        raise RuntimeError("code_end %d busts the 2048-step budget" % code_end)

    tbl, miss = {}, []
    for b in INPUTS:
        Ls, st, ok = req[b]
        if not ok:
            miss.append(b); continue
        got = lane_bytes(b, P, s, Ls)
        if got is None:
            miss.append(b); continue
        for a, v in got.items():
            if a in tbl and tbl[a] != v:
                raise RuntimeError("table conflict at %d" % a)
        tbl.update(got)
    end = max(max(tbl) if tbl else 0, code_end) + 1
    src = bytearray(codebyte(a, NOP) for a in range(end))
    for a, v in bd.prog.items():
        src[a] = v
    for a, v in tbl.items():
        assert a >= code_end
        src[a] = v
    return bytes(src), dict(code_end=code_end, miss=miss, K=K, s=s, P=P,
                            first_cell=first_cell)


def patterns(K, cap, limit=400):
    """collision-free walk patterns of depth K with span < cap."""
    out = []

    def rec(P):
        if len(P) == K:
            out.append(list(P))
            return len(out) >= limit
        for x in range(P[-1] + 1, cap):
            if all((x - p) not in DIFFS for p in P):
                P.append(x)
                if rec(P):
                    P.pop(); return True
                P.pop()
        return False

    rec([0])
    return out


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "cand.mal"
    K = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    pats = patterns(K, cap)
    print("collision-free patterns at K=%d span<%d: %d" % (K, cap, len(pats)),
          flush=True)
    best = None
    for Pat in pats:
        for s in range(94):
            try:
                prog, info = build(Pat, s)
            except RuntimeError:
                continue
            n = 16 - len(info["miss"])
            if best is None or n > best[0]:
                best = (n, prog, info)
                print("  %2d/16  P=%s s=%d code_end=%d miss=%s"
                      % (n, Pat, s, info["code_end"],
                         [hex(x) for x in info["miss"]]), flush=True)
            if n >= 15:
                break
        if best and best[0] >= 15:
            break
    if best is None:
        raise SystemExit("no pattern built")
    n, prog, info = best
    open(out, "wb").write(prog)
    print("wrote %s  %d bytes  model-level %d/16  miss=%s"
          % (out, len(prog), n, [hex(x) for x in info["miss"]]))
    print("  P=%s s=%d code_end=%d first_cell=%d"
          % (info["P"], info["s"], info["code_end"], info["first_cell"]))
