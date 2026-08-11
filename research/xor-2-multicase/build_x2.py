#!/usr/bin/env python3
"""Builder for L2.R3.xor-2-multicase (out = in[0..1] ^ 0x51, cap 384 bytes,
2 cases per epoch).

Both output bytes need the same xor-0x51 map, so the program is two dispatches
back to back.  The first one is the L2.R0.xor-1 layout; the 384-byte cap (vs
256 there) is enough to push the operand table entirely CLEAR of the code, so
no input is lost to code-cell corruption:

  0        IN            A = b0
  1,2,3    MOVD x3       D: 1 -> 40 -> 123 -> 71
  4,5      CRZ x2        m[71]=m[72]=121 -> cell 72 holds b0
  6,7,8    MOVD x3       D -> m[72]+1 = b0+1
  9..      NOP x (K0-1)  free dispatch offset
  ..       CRZ x k       operands m[b0+K0 .. b0+K0+k-1]   <- DP-designed table
  P-4      OUT           out0 = A mod 256
  P-3      IN            A = b1                      (D is now b0+K0+k+1)
  P-2..    CRZ x m       operands m[b0+K0+k+2 ..]    <- SAME table, b0-shifted
  ..       OUT, HALT     out1 = A mod 256

The second dispatch cannot re-park b1: D is input-dependent from the moment the
first chain runs, and D can only be reset through MOVD, which reads m[D].  See
the report.  So the second byte rides whatever cells the first dispatch left D
pointing at.

usage:
  build_x2.py sweep            exact DP over (k, K0), phase A only
  build_x2.py emit k K0 m      assemble, model-score both bytes, write cand.mal
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "xor-1-len4096"))
from build import OPS, XLAT2, code_of, byte_for_op, valid_bytes, crazy, rotr  # noqa

MASK = 0x51
L = 384                       # max_program_len for this rung
DATA = {40: 122, 62: 71, 71: 121, 72: 121, 73: 61, 123: 70}
DPK = os.path.join(HERE, "..", "xor-1", "dpk")


def code_ops(k, k0, m):
    """Instruction stream, phase A then phase B."""
    return ([23] + [40, 40, 40] + [62, 62] + [40, 40, 40]
            + [68] * (k0 - 1) + [62] * k
            + [5] + [23] + [62] * m + [5, 81])


def base_program(k, k0, m):
    ops = code_ops(k, k0, m)
    prog = [None] * L
    for a, op in enumerate(ops):
        prog[a] = byte_for_op(op, a)
    for a, v in DATA.items():
        if a < len(ops):
            raise ValueError(f"data cell {a} collides with code (P={len(ops)})")
        assert v in valid_bytes(a), (a, v)
        prog[a] = v
    return prog, ops


def spec_lines(k, k0, m):
    prog, ops = base_program(k, k0, m)
    P = len(ops)
    out = []
    for a in range(L):
        if a < P:
            out.append(f"{a} X {XLAT2[prog[a] - 33]}")
        elif a in (71, 72):
            out.append(f"{a} X {DATA[a]}")
        elif a in DATA:
            out.append(f"{a} F {DATA[a]}")
        else:
            out.append(f"{a} E")
    return "\n".join(out) + "\n", prog, ops


def solve(k, k0, m, emit=False):
    spec, prog, ops = spec_lines(k, k0, m)
    sp = os.path.join(HERE, f"spec_k{k}_o{k0}.txt")
    with open(sp, "w") as fh:
        fh.write(spec)
    cmd = [DPK, sp, str(k), str(L), str(k0)] + (["emit"] if emit else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    score = int(r.stderr.strip().split("best=")[1].split("/")[0])
    return score, r.stdout, prog, ops


def assemble(k, k0, m):
    score, stdout, prog, ops = solve(k, k0, m, emit=True)
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


# ---------------------------------------------------------------- fast VM ----
def fill_image(prog):
    """Full 59049-cell image; the crazy fill is computed once and shared."""
    mem = list(prog) + [0] * (59049 - len(prog))
    for i in range(len(prog), 59049):
        mem[i] = crazy(mem[i - 1], mem[i - 2])
    return mem


def run_fast(base, inp, max_steps=4096):
    """Overlay VM: writes go to a dict, so the 59049-cell fill is built once."""
    wr = {}
    def rd(i):
        v = wr.get(i)
        return base[i] if v is None else v
    a = c = d = 0
    ii = 0
    out = []
    for _ in range(max_steps):
        f = rd(c)
        if not (33 <= f <= 126):
            return out, f"bad-instr@{c}={f}"
        op = code_of(f, c)
        if op == 4:
            c = rd(d)
        elif op == 5:
            out.append(a % 256)
        elif op == 23:
            a = inp[ii] if ii < len(inp) else 59048
            if ii < len(inp):
                ii += 1
        elif op == 39:
            wr[d] = rotr(rd(d)); a = wr[d]
        elif op == 40:
            d = rd(d)
        elif op == 62:
            wr[d] = crazy(a, rd(d)); a = wr[d]
        elif op == 81:
            return out, "halt"
        v = rd(c)
        if not (33 <= v <= 126):
            return out, f"encipher-fail@{c}"
        wr[c] = XLAT2[v - 33]
        c = (c + 1) % 59049
        d = (d + 1) % 59049
    return out, "steps"


def measure(progbytes, sample1=None):
    """Return (setA, per-b0 set of good b1, pair count)."""
    base = fill_image(list(progbytes))
    b1s = range(256) if sample1 is None else sample1
    okA, good1, pairs = [], {}, 0
    for b0 in range(256):
        g = []
        for b1 in b1s:
            out, st = run_fast(base, [b0, b1])
            if st != "halt" or len(out) != 2:
                continue
            if out[0] == (b0 ^ MASK):
                if b1 == next(iter(b1s)):
                    pass
            if out[0] == (b0 ^ MASK) and out[1] == (b1 ^ MASK):
                g.append(b1)
        # phase-A correctness is independent of b1; probe once
        out, st = run_fast(base, [b0, 0])
        if st == "halt" and out and out[0] == (b0 ^ MASK):
            okA.append(b0)
        good1[b0] = g
        pairs += len(g)
    return okA, good1, pairs


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    if cmd == "sweep":
        m = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        best = None
        for k in (3, 5, 7):
            P0 = len(code_ops(k, 1, m))
            for k0 in range(1, 125):
                try:
                    sc, _, _, ops = solve(k, k0, m)
                except Exception as e:
                    continue
                if best is None or sc > best[0]:
                    best = (sc, k, k0)
                    print(f"  k={k} K0={k0} P={len(ops)} -> {sc}", flush=True)
        print("BEST", best)
    elif cmd == "emit":
        k, k0, m = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        sc, prog = assemble(k, k0, m)
        path = os.path.join(HERE, f"cand-k{k}-o{k0}-m{m}.mal")
        with open(path, "wb") as fh:
            fh.write(prog)
        print("dp score (phase A):", sc, "->", path)
        okA, good1, pairs = measure(prog)
        print("model phase-A set:", len(okA))
        print("model pair count :", pairs, "/ 65536")
        nz = [b for b in good1 if good1[b]]
        print("b0 with any good b1:", len(nz))
        with open(os.path.join(HERE, f"model-k{k}-o{k0}-m{m}.txt"), "w") as fh:
            fh.write(f"phaseA {len(okA)}\n{sorted(okA)}\npairs {pairs}\n")
            for b in sorted(good1):
                if good1[b]:
                    fh.write(f"{b}: {good1[b]}\n")
