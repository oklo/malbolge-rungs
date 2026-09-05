#!/usr/bin/env python3
"""Premix layout for L2.R2.rotate-1: acc0 = rotr^j(b), dispatch still D = b+1.

New result feeding this: the closure BFS (reach.c) shows a pure-CRZ walk can
reach the target for only 193/256 inputs no matter how the table is chosen,
while CRZ+ROT reaches 256/256 at depth <= 5.  The missing mechanism is a ROT
acting on an input-derived value.  This layout realizes exactly that with
shared straight-line code and zero per-input cost:

  C=0        IN               A = b
  C=1..3     MOVD x3          D: 1 -> 40 -> 123 -> 71   (pins 40:122, 123:70)
  C=4,5      CRZ x2           park1: m[72] = b          (pins 71:121, 72:121)
  C=6        NOP              D -> 74
  C=7        MOVD             D = m[74] = 101 -> 102    (pin 74:101)
  C=8..11    NOP x4           D -> 106
  C=12,13    CRZ x2           park2: m[107] = b         (pins 106:121, 107:121)
  C=14,15    MOVD x2          D: m[108]=85 -> 86, m[86]=106 -> 107
                              (pins 108:85, 86:106)
  C=16..     ROT [MOVD MOVD ROT]x(j-1)
                              m[107] = rotr^j(b), A = rotr^j(b), D = 108
  ..         NOP              D -> 109
  ..         MOVD x3          D: m[109]=84 -> 85, m[85]=71 -> 72,
                              m[72]=b -> b+1             (pins 109:84, 85:71)
  ..         NOP x (K0-1)     D = b + K0
  ..         CRZ x k          operands m[b+K0 .. b+K0+k-1], acc0 = rotr^j(b)
  P-2,P-1    OUT, HALT        P = 19 + 3j + K0 + k

All pin bytes verified loader-legal at their addresses.  Cell 40 holds 122,
which decodes to NOP at address 40, so code may run through it; configs where
C=40 would land on a non-NOP op are skipped.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "xor-1-push"))
import mal

ROTL = lambda b: ((b << 1) | (b >> 7)) & 0xFF
DATA = {40: 122, 123: 70, 71: 121, 72: 121, 74: 101,
        106: 121, 107: 121, 108: 85, 86: 106, 109: 84, 85: 71}
XCELLS = (71, 72, 106, 107)     # input-dependent at walk time


def valid_bytes(addr):
    return sorted(mal.legal_bytes(addr).values())


def code_ops(j, k, k0):
    ops = [23, 40, 40, 40, 62, 62, 68, 40, 68, 68, 68, 68, 62, 62, 40, 40]
    ops += [39] + [40, 40, 39] * (j - 1)
    ops += [68, 40, 40, 40]
    ops += [68] * (k0 - 1) + [62] * k + [5, 81]
    return ops


def layout_valid(j, k, k0):
    ops = code_ops(j, k, k0)
    P = len(ops)
    if P > 85:
        return False
    if P > 40 and ops[40] != 68:
        return False
    return True


def base_program(j, k, k0, L):
    ops = code_ops(j, k, k0)
    prog = [None] * L
    for a, op in enumerate(ops):
        if a in DATA:
            assert mal.code_of(DATA[a], a) == op, (a, op)
            prog[a] = DATA[a]
        else:
            b = mal.byte_for(op, a)
            assert b is not None, (a, op)
            prog[a] = b
    for a, v in DATA.items():
        if a >= len(ops):
            assert v in valid_bytes(a), (a, v)
            prog[a] = v
    return prog, ops


def spec_lines(j, k, k0, L):
    prog, ops = base_program(j, k, k0, L)
    P = len(ops)
    out = []
    for a in range(L):
        if a < P:
            out.append(f"{a} X {mal.XLAT2[prog[a] - 33]}")
        elif a in XCELLS:
            out.append(f"{a} X {DATA[a]}")
        elif a in DATA:
            out.append(f"{a} F {DATA[a]}")
        else:
            out.append(f"{a} E")
    return "\n".join(out) + "\n", prog, ops


def solve(j, k, k0, L, emit=False):
    spec, prog, ops = spec_lines(j, k, k0, L)
    sp = os.path.join(HERE, f".spec3_{os.getpid()}.txt")
    with open(sp, "w") as fh:
        fh.write(spec)
    cmd = [os.path.join(HERE, "dpk_rot"), sp, str(k), str(L), str(k0), str(j)] + (
        ["emit"] if emit else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(sp)
    score = int(r.stderr.strip().split("best=")[1].split("/")[0])
    return score, r.stdout, prog, ops


def assemble(j, k, k0, L):
    score, stdout, prog, ops = solve(j, k, k0, L, emit=True)
    chosen = {}
    for line in stdout.strip().splitlines():
        a, v = line.split()
        chosen[int(a)] = int(v)
    P = len(ops)
    for a in range(L):
        if a < P or a in DATA:
            continue
        v = chosen.get(a)
        if v is None or v not in valid_bytes(a):
            v = valid_bytes(a)[0]
        prog[a] = v
    for a in range(L):
        if prog[a] is None:
            prog[a] = valid_bytes(a)[0]
        assert mal.code_of(prog[a], a) in mal.VALID_CODES, (a, prog[a])
    return score, bytes(prog)


def measure(progbytes):
    ok = []
    for b in range(256):
        out, st, _ = mal.run(list(progbytes), [b])
        if st == "Halted" and out == bytes([ROTL(b)]):
            ok.append(b)
    return ok


if __name__ == "__main__":
    if sys.argv[1] == "sweep":
        L = int(sys.argv[2]) if len(sys.argv) > 2 else 256
        ks = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [3, 5, 7]
        best = None
        for j in range(1, 10):
            for k in ks:
                for k0 in range(1, 17):
                    if not layout_valid(j, k, k0):
                        continue
                    s, _, _, _ = solve(j, k, k0, L)
                    print(f"j={j} k={k} K0={k0:2d} L={L} -> {s}/256", flush=True)
                    if best is None or s > best[0]:
                        best = (s, j, k, k0, L)
        print("BEST", best)
    elif sys.argv[1] == "one":
        j, k, k0, L = (int(x) for x in sys.argv[2:6])
        score, pb = assemble(j, k, k0, L)
        path = os.path.join(HERE, f"cand3_j{j}_k{k}_o{k0}_L{L}.mal")
        open(path, "wb").write(pb)
        ok = measure(pb)
        print(f"j={j} k={k} K0={k0} L={L} dp={score}/256 model={len(ok)}/256 -> {path}")
        print("covered:", ok)
