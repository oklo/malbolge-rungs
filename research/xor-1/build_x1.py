#!/usr/bin/env python3
"""Builder for L2.R0.xor-1 (out = in ^ 0x51, program cap 256 bytes).

The 256-byte cap rules out the stride-9 private-block layout that
L2.R0d.xor-1-len4096 used (that needed 2310 bytes).  Stride is forced to 1, so
adjacent inputs share operand cells and the operand table has to live INSIDE the
program.  research/xor-1/dpk.c resolves that sharing exactly (transfer-matrix DP
over the 8 loader-legal bytes of each free cell); this script emits the layout
spec it consumes, assembles the winning byte assignment, and simulates all 256
inputs on a faithful model of the native VM.

Layout, code addresses 0 .. P-1 (P = 15 + (K0-1) + k):
  0        IN            A = b
  1,2,3    MOVD x3       D: 1 -> 40 -> 123 -> 71
  4,5      CRZ x2        m[71] = m[72] = 121 = 11111_3, so
                         crazy(crazy(b,121),121) = b  -> cell 72 holds b
  6,7,8    MOVD x3       D: 73 -> 62 -> 72 -> m[72]+1 = b+1
  9..      NOP x (K0-1)  every instruction post-increments D: free dispatch offset
  ..       CRZ x k       operands m[b+K0 .. b+K0+k-1]
  P-2      OUT           out = A mod 256
  P-1      HALT
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "xor-1-len4096"))
from build import OPS, XLAT2, code_of, byte_for_op, valid_bytes, crazy, rotr, run  # noqa

MASK = 0x51
L = 256                       # max_program_len for this rung
DATA = {40: 122, 62: 71, 71: 121, 72: 121, 73: 61, 123: 70}


def code_ops(k, k0):
    return ([23] + [40, 40, 40] + [62, 62] + [40, 40, 40]
            + [68] * (k0 - 1) + [62] * k + [5, 81])


def base_program(k, k0):
    """Program with code + pointer constants placed; free cells left as None."""
    ops = code_ops(k, k0)
    prog = [None] * L
    for a, op in enumerate(ops):
        prog[a] = byte_for_op(op, a)
    for a, v in DATA.items():
        if a < len(ops):
            raise ValueError(f"data cell {a} collides with code (P={len(ops)})")
        assert v in valid_bytes(a), (a, v)
        prog[a] = v
    return prog, ops


def spec_lines(k, k0):
    """Per-address state of every cell at the moment the CRZ chain reads it."""
    prog, ops = base_program(k, k0)
    P = len(ops)
    out = []
    for a in range(L):
        if a < P:
            # executed code: value is the enciphered byte.  Mark X (unscoreable)
            # because the chain also WRITES these cells, which corrupts any
            # instruction not yet executed, and cells 71/72 hold input-derived
            # values.  Being conservative here costs only the low inputs.
            out.append(f"{a} X {XLAT2[prog[a] - 33]}")
        elif a in (71, 72):
            out.append(f"{a} X {DATA[a]}")          # 71 = crazy(b,121), 72 = b
        elif a in DATA:
            out.append(f"{a} F {DATA[a]}")          # pointer constant, untouched
        else:
            out.append(f"{a} E")
    return "\n".join(out) + "\n", prog, ops


def solve(k, k0, emit=False):
    spec, prog, ops = spec_lines(k, k0)
    sp = os.path.join(HERE, f"spec_k{k}_o{k0}.txt")
    with open(sp, "w") as fh:
        fh.write(spec)
    cmd = [os.path.join(HERE, "dpk"), sp, str(k), str(L), str(k0)] + (["emit"] if emit else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    score = int(r.stderr.strip().split("best=")[1].split("/")[0])
    return score, r.stdout, prog, ops


def assemble(k, k0):
    score, stdout, prog, ops = solve(k, k0, emit=True)
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
        assert code_of(prog[a], a) in OPS, (a, prog[a])
    return score, bytes(prog)


def measure(progbytes):
    """Run every input byte through the model VM; return the passing set."""
    ok = []
    for b in range(256):
        out, st = run(list(progbytes), [b])
        if st == "halt" and out == [b ^ MASK]:
            ok.append(b)
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        best = None
        for k in (3, 5, 7):
            for k0 in range(1, 25):
                try:
                    s, _, _, _ = solve(k, k0)
                except ValueError:
                    continue
                print(f"k={k} K0={k0:2d} -> {s}/256", flush=True)
                if best is None or s > best[0]:
                    best = (s, k, k0)
        print("BEST", best)
    else:
        k = int(sys.argv[1]); k0 = int(sys.argv[2])
        score, pb = assemble(k, k0)
        path = os.path.join(HERE, "cand.mal")
        open(path, "wb").write(pb)
        ok = measure(pb)
        print(f"k={k} K0={k0} dp={score}/256  model-verified={len(ok)}/256 -> {path}")
        open(os.path.join(HERE, "covered.txt"), "w").write(repr(ok) + "\n")
