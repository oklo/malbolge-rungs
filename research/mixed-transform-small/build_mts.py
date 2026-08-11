#!/usr/bin/env python3
"""Builder for L3.R2.mixed-transform-small.

Rung: Transform family, transform = NibbleMap, output_bytes = 2, cases = 3,
max_program_len = 512, max_steps_per_case = 16384.

challenge.rs: input is a 32-byte seed-derived hash; expected output is
transform_bytes(input[..2]) with NibbleMap = (b<<4)|(b>>4) mod 256.  So the
program must emit  swap(b0), swap(b1)  where swap is a *value* function of the
byte -- i.e. this is the xor-1 dispatch wall, twice, with the second dispatch
needing a D reset in between.

Architecture here is the L3.R1.xor-4-length-cap one, cut to two outputs:
one real DP-designed dispatch on b0, then one "ride" chain for b1 on whatever
cells the first walk left D on.

  0        IN            A = b0
  1,2,3    MOVD x3       D: 1 -> 40 -> 123 -> 71
  4,5      CRZ x2        m[71]=m[72]=121 -> cell 72 holds b0 exactly
  6,7,8    MOVD x3       D -> m[72]+1 = b0+1
  9..      NOP x (K0-1)  free dispatch offset
  ..       CRZ x k       operands m[b0+K0 .. b0+K0+k-1]   <- DP-designed
  ..       OUT           out0 = swap(b0) for the covered b0
  ..       IN            A = b1
  ..       CRZ x m       operands ride the polluted D
  ..       OUT           out1
  ..       HALT

The DP is research/xor-1/dpk.c with the target changed from b^0x51 to
(b<<4)|(b>>4); see dpk_nib.c.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "reverse-2-multicase"))
from mal import OPSET, ENCIPHER, icode, bytes_for, crazy, rotr, VM, check_source  # noqa

OPS = OPSET
XLAT2 = list(ENCIPHER)
L = 512                       # max_program_len for THIS rung
DATA = {40: 122, 62: 71, 71: 121, 72: 121, 73: 61, 123: 70}
DPK = os.path.join(HERE, "dpk_nib")

def swap(b): return ((b << 4) | (b >> 4)) & 0xFF
def code_of(v, a): return icode(v, a)
def valid_bytes(a): return [v for v in range(33, 127) if icode(v, a) in OPS]
def byte_for_op(op, a):
    c = bytes_for(op, a)
    if not c: raise ValueError((op, a))
    return c[0]

def code_ops(k, k0, m):
    return ([23] + [40,40,40] + [62,62] + [40,40,40]
            + [68]*(k0-1) + [62]*k + [5]
            + [23] + [62]*m + [5] + [81])

def base_program(k, k0, m):
    ops = code_ops(k, k0, m)
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
        if a < P:          out.append(f"{a} X {XLAT2[prog[a]-33]}")
        elif a in (71,72): out.append(f"{a} X {DATA[a]}")
        elif a in DATA:    out.append(f"{a} F {DATA[a]}")
        else:              out.append(f"{a} E")
    return "\n".join(out)+"\n", prog, ops

def solve(k, k0, m, emit=False):
    spec, prog, ops = spec_lines(k, k0, m)
    sp = os.path.join(HERE, f"spec_k{k}_o{k0}_m{m}.txt")
    open(sp, "w").write(spec)
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
_CZ = {}
def czm(acc, v):
    key = (acc, v)
    r = _CZ.get(key)
    if r is None:
        r = crazy(acc, v); _CZ[key] = r
    return r

def fill_image(prog, top=700):
    mem = list(prog) + [0]*(top-len(prog))
    for i in range(len(prog), top): mem[i] = crazy(mem[i-1], mem[i-2])
    return mem

def run_fast(base, inp, max_steps=16384):
    wr = {}
    def rd(i):
        v = wr.get(i)
        return base[i] if v is None else v
    a=c=d=0; ii=0; out=[]
    for _ in range(max_steps):
        f = rd(c)
        if not (33 <= f <= 126): return out, f"bad-instr@{c}={f}"
        op = code_of(f, c)
        if op == 4: c = rd(d)
        elif op == 5:
            out.append(a % 256)
            if len(out) > 2: return out, "overout"
        elif op == 23:
            a = inp[ii] if ii < len(inp) else 59048
            if ii < len(inp): ii += 1
        elif op == 39: wr[d] = rotr(rd(d)); a = wr[d]
        elif op == 40: d = rd(d)
        elif op == 62: wr[d] = czm(a, rd(d)); a = wr[d]
        elif op == 81: return out, "halt"
        v = rd(c)
        if not (33 <= v <= 126): return out, f"encipher-fail@{c}"
        wr[c] = XLAT2[v-33]
        c = (c+1) % 59049; d = (d+1) % 59049
    return out, "steps"

def measure(progbytes, full=False):
    """out0 depends on b0 only; out1 depends on (b0,b1).  Score phase A over
    all 256 b0, then sweep b1 only under the b0 that phase A already gets
    right (a pair can only be good if out0 is right)."""
    base = fill_image(list(progbytes))
    okA = []
    for b0 in range(256):
        out, st = run_fast(base, [b0, 0])
        if len(out) >= 1 and out[0] == swap(b0): okA.append(b0)
    pairs = 0; good = []
    scan = range(256) if full else okA
    for b0 in scan:
        for b1 in range(256):
            out, st = run_fast(base, [b0, b1])
            if len(out) == 2 and out[0] == swap(b0) and out[1] == swap(b1):
                pairs += 1; good.append((b0, b1))
    return okA, pairs, good

if __name__ == "__main__":
    if not os.path.exists(DPK):
        subprocess.run(["cc","-O2","-o",DPK,os.path.join(HERE,"dpk_nib.c")], check=True)
    best = None
    for k in (3,5,7):
        for k0 in range(1, 20):
            for m in (1,2,3):
                if k0 + k + m + 12 > 40: continue
                try:
                    s,_,_,_ = solve(k,k0,m)
                except Exception as e:
                    continue
                if best is None or s > best[0]: best = (s,k,k0,m)
                print(f"k={k} K0={k0} m={m} -> {s}/256", flush=True)
    print("BEST", best)
    s,k,k0,m = best
    score, prog = assemble(k,k0,m)
    open(os.path.join(HERE,"cand-mts.mal"),"wb").write(prog)
    err = check_source(list(prog))
    print("source check:", err or "ok", "len", len(prog))
    okA, pairs, good = measure(prog)
    print(f"phase A: {len(okA)}/256   pairs: {pairs}/65536  = {pairs/65536:.6f}")
    print(f"epoch pass prob (3 cases): {(pairs/65536)**3:.3e}")
    open(os.path.join(HERE,"model-mts.txt"),"w").write(
        f"k={k} K0={k0} m={m} dpA={score} phaseA={len(okA)}/256 pairs={pairs}/65536\n"
        + "okA=" + repr(okA) + "\n")
