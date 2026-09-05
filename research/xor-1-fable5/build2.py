#!/usr/bin/env python3
"""L2.R0.xor-1 builder, Fable 5 run (2026-09-05).

research/xor-1/build_x1.py with two changes:
  * the program length L is a parameter (the L-sweep is the record's item 3 —
    cells >= L are crazy fill, exceed 242, and break trit-magnitude Barrier 1);
  * imports come from research/xor-1-push/mal.py (this clone does not carry
    research/xor-1-len4096/build.py, which build_x1.py expected).

Layout is unchanged from the 68/256 record:
  0        IN            A = b
  1,2,3    MOVD x3       D: 1 -> 40 -> 123 -> 71
  4,5      CRZ x2        m[71] = m[72] = 121, cell 72 holds b exactly
  6,7,8    MOVD x3       D: 73 -> 62 -> 72 -> m[72]+1 = b+1
  9..      NOP x (K0-1)  D = b + K0
  ..       CRZ x k       operands m[b+K0 .. b+K0+k-1]
  P-2,P-1  OUT, HALT
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "xor-1-push"))
import mal

MASK = 0x51
OPS = mal.VALID_CODES
DATA = {40: 122, 62: 71, 71: 121, 72: 121, 73: 61, 123: 70}


def valid_bytes(addr):
    return sorted(mal.legal_bytes(addr).values())


def code_ops(k, k0):
    return ([23] + [40, 40, 40] + [62, 62] + [40, 40, 40]
            + [68] * (k0 - 1) + [62] * k + [5, 81])


def base_program(k, k0, L):
    ops = code_ops(k, k0)
    if len(ops) > 40:
        raise ValueError("code collides with pointer cell 40")
    prog = [None] * L
    for a, op in enumerate(ops):
        b = mal.byte_for(op, a)
        assert b is not None
        prog[a] = b
    for a, v in DATA.items():
        assert a >= len(ops) and a < L and v in valid_bytes(a), (a, v)
        prog[a] = v
    return prog, ops


def spec_lines(k, k0, L):
    prog, ops = base_program(k, k0, L)
    P = len(ops)
    out = []
    for a in range(L):
        if a < P:
            out.append(f"{a} X {mal.XLAT2[prog[a] - 33]}")
        elif a in (71, 72):
            out.append(f"{a} X {DATA[a]}")
        elif a in DATA:
            out.append(f"{a} F {DATA[a]}")
        else:
            out.append(f"{a} E")
    return "\n".join(out) + "\n", prog, ops


def solve(k, k0, L, emit=False):
    spec, prog, ops = spec_lines(k, k0, L)
    sp = os.path.join(HERE, f"spec_k{k}_o{k0}_L{L}.txt")
    with open(sp, "w") as fh:
        fh.write(spec)
    cmd = [os.path.join(HERE, "..", "xor-1", "dpk"), sp, str(k), str(L), str(k0)] + (
        ["emit"] if emit else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    score = int(r.stderr.strip().split("best=")[1].split("/")[0])
    os.unlink(sp)
    return score, r.stdout, prog, ops


def assemble(k, k0, L):
    score, stdout, prog, ops = solve(k, k0, L, emit=True)
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
        assert mal.code_of(prog[a], a) in OPS, (a, prog[a])
    return score, bytes(prog)


def measure(progbytes):
    ok = []
    for b in range(256):
        out, st, _ = mal.run(list(progbytes), [b])
        if st == "Halted" and out == bytes([b ^ MASK]):
            ok.append(b)
    return ok


if __name__ == "__main__":
    if sys.argv[1] == "sweep":
        lo, hi, step = (int(x) for x in sys.argv[2:5])
        best = None
        for L in range(lo, hi + 1, step):
            for k in (3, 5, 7):
                for k0 in range(1, 25):
                    s, _, _, _ = solve(k, k0, L)
                    print(f"L={L} k={k} K0={k0:2d} -> {s}/256", flush=True)
                    if best is None or s > best[0]:
                        best = (s, L, k, k0)
        print("BEST", best)
    elif sys.argv[1] == "one":
        k, k0, L = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        score, pb = assemble(k, k0, L)
        path = os.path.join(HERE, f"cand_k{k}_o{k0}_L{L}.mal")
        open(path, "wb").write(pb)
        ok = measure(pb)
        print(f"k={k} K0={k0} L={L} dp={score}/256 model={len(ok)}/256 -> {path}")
        open(os.path.join(HERE, f"covered_k{k}_o{k0}_L{L}.txt"), "w").write(repr(ok) + "\n")
