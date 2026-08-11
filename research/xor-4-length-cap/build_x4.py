#!/usr/bin/env python3
"""Builder for L3.R1.xor-4-length-cap  (out = in[0..3] ^ 0x51, cap 256 bytes,
2 cases per epoch, 8192 steps).

Phase A is the L2.R0.xor-1 dispatch verbatim (that rung's exact DP is reused
unchanged).  Bytes 1..3 ride the cells the first dispatch left D pointing at,
exactly as in L2.R3.xor-2-multicase -- see funnel.py for the result that says
this is NOT forced, and the report for why the fix did not fit the cap.

  0        IN            A = b0
  1,2,3    MOVD x3       D: 1 -> 40 -> 123 -> 71
  4,5      CRZ x2        m[71]=m[72]=121 -> cell 72 holds b0 exactly
  6,7,8    MOVD x3       D -> m[72]+1 = b0+1
  9..      NOP x (K0-1)  free dispatch offset
  ..       CRZ x k       operands m[b0+K0 .. b0+K0+k-1]   <- DP-designed
  ..       OUT           out0
  ( IN ; CRZ x m ; OUT ) x 3                              <- rides, D polluted
  ..       HALT
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "xor-1-len4096"))
from build import OPS, XLAT2, code_of, byte_for_op, valid_bytes, crazy, rotr  # noqa

MASK = 0x51
L = 256                       # max_program_len for THIS rung
DATA = {40: 122, 62: 71, 71: 121, 72: 121, 73: 61, 123: 70}
DPK = os.path.join(HERE, "..", "xor-1", "dpk")

def code_ops(k, k0, m):
    return ([23] + [40,40,40] + [62,62] + [40,40,40]
            + [68]*(k0-1) + [62]*k + [5]
            + ([23] + [62]*m + [5])*3 + [81])

def base_program(k, k0, m):
    ops = code_ops(k, k0, m)
    if len(ops) > L: raise ValueError("code longer than cap")
    prog = [None]*L
    for a, op in enumerate(ops): prog[a] = byte_for_op(op, a)
    for a, v in DATA.items():
        if a < len(ops): raise ValueError(f"data cell {a} collides with code P={len(ops)}")
        assert v in valid_bytes(a), (a, v)
        prog[a] = v
    return prog, ops

def spec_lines(k, k0, m):
    prog, ops = base_program(k, k0, m)
    P = len(ops); out = []
    for a in range(L):
        if a < P:      out.append(f"{a} X {XLAT2[prog[a]-33]}")
        elif a in (71,72): out.append(f"{a} X {DATA[a]}")
        elif a in DATA: out.append(f"{a} F {DATA[a]}")
        else:          out.append(f"{a} E")
    return "\n".join(out)+"\n", prog, ops

def solve(k, k0, m, emit=False):
    spec, prog, ops = spec_lines(k, k0, m)
    sp = os.path.join(HERE, f"spec_k{k}_o{k0}_m{m}.txt")
    open(sp,"w").write(spec)
    cmd = [DPK, sp, str(k), str(L), str(k0)] + (["emit"] if emit else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    score = int(r.stderr.strip().split("best=")[1].split("/")[0])
    return score, r.stdout, prog, ops

def assemble(k, k0, m):
    score, stdout, prog, ops = solve(k, k0, m, emit=True)
    chosen = {}
    for line in stdout.strip().splitlines():
        a, v = line.split(); chosen[int(a)] = int(v)
    P = len(ops)
    for a in range(L):
        if a < P or a in DATA: continue
        v = chosen.get(a)
        if v is None or v not in valid_bytes(a): v = valid_bytes(a)[0]
        prog[a] = v
    for a in range(L):
        if prog[a] is None: prog[a] = valid_bytes(a)[0]
        assert code_of(prog[a], a) in OPS, (a, prog[a])
    return score, bytes(prog)

# ------------------------------------------------------------------ fast VM --
def fill_image(prog):
    mem = list(prog) + [0]*(59049-len(prog))
    for i in range(len(prog), 59049): mem[i] = crazy(mem[i-1], mem[i-2])
    return mem

def run_fast(base, inp, max_steps=8192):
    wr = {}
    def rd(i):
        v = wr.get(i); return base[i] if v is None else v
    a=c=d=0; ii=0; out=[]
    for _ in range(max_steps):
        f = rd(c)
        if not (33 <= f <= 126): return out, f"bad-instr@{c}={f}"
        op = code_of(f, c)
        if op == 4: c = rd(d)
        elif op == 5: out.append(a % 256)
        elif op == 23:
            a = inp[ii] if ii < len(inp) else 59048
            if ii < len(inp): ii += 1
        elif op == 39: wr[d] = rotr(rd(d)); a = wr[d]
        elif op == 40: d = rd(d)
        elif op == 62: wr[d] = crazy(a, rd(d)); a = wr[d]
        elif op == 81: return out, "halt"
        v = rd(c)
        if not (33 <= v <= 126): return out, f"encipher-fail@{c}"
        wr[c] = XLAT2[v-33]
        c = (c+1) % 59049; d = (d+1) % 59049
    return out, "steps"

def measure(progbytes):
    """out_i depends only on (b0, b_i): the D-walk after phase A is a function
    of b0 alone and the three ride chains read disjoint cells.  Verified below.
    So feeding b1=b2=b3=x characterises all three rides at once."""
    base = fill_image(list(progbytes))
    okA = []; good = {}
    tuples = 0
    for b0 in range(256):
        g = [[], [], []]
        for x in range(256):
            out, st = run_fast(base, [b0, x, x, x])
            if st != "halt" or len(out) != 4: continue
            if x == 0 and out[0] == (b0 ^ MASK): okA.append(b0)
            for i in range(3):
                if out[i+1] == (x ^ MASK): g[i].append(x)
        good[b0] = g
        if b0 in okA: tuples += len(g[0])*len(g[1])*len(g[2])
    return okA, good, tuples

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    if cmd == "sweep":
        m = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        best = None
        for k in (3,5,7):
            for k0 in range(1, 60):
                try: sc,_,_,ops = solve(k,k0,m)
                except Exception: continue
                if best is None or sc > best[0]:
                    best = (sc,k,k0); print(f"  k={k} K0={k0} P={len(ops)} -> {sc}", flush=True)
        print("BEST", best)
    elif cmd == "emit":
        k,k0,m = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        sc, prog = assemble(k,k0,m)
        path = os.path.join(HERE, f"cand-k{k}-o{k0}-m{m}.mal")
        open(path,"wb").write(prog)
        print("dp score (phase A):", sc, "->", path)
        okA, good, tuples = measure(prog)
        print("model phase-A set:", len(okA))
        print("good 4-tuples    :", tuples, "/ 4294967296", f"= {tuples/2**32:.3e}")
        with open(os.path.join(HERE, f"model-k{k}-o{k0}-m{m}.txt"),"w") as fh:
            fh.write(f"phaseA {len(okA)}\n{sorted(okA)}\ntuples {tuples}\n")
            for b in sorted(good):
                if any(good[b]): fh.write(f"{b}: "+ " | ".join(str(s) for s in good[b]) + "\n")
