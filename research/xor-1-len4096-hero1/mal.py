#!/usr/bin/env python3
"""Faithful classic-MAL-51-v0 simulator, mirroring crates/classic_malbolge/src/lib.rs.

Used to design and trace programs for L2.R0d.xor-1-len4096.  Cross-checked
against the native `execute` subcommand before any claim is made from it.
"""
XLAT2 = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
VALID_CODES = (4, 5, 23, 39, 40, 62, 68, 81)
NAMES = {4: "JMP", 5: "OUT", 23: "IN", 39: "ROT", 40: "MOVD", 62: "CRZ", 68: "NOP", 81: "HLT"}
M = 59049

# crazy_trit[operand][acc]  (operand is the d-trit, acc is the a-trit)
CT = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]


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


def crazy(a, d):
    ta, td = trits(a), trits(d)
    return from_trits([CT[td[i]][ta[i]] for i in range(10)])


def rotr(w):
    return w // 3 + (w % 3) * 19683


def code_of(word, addr):
    return (word + addr) % 94


def byte_for(code, addr):
    """The (unique, if any) printable byte at addr decoding to `code`."""
    v = (code - addr) % 94
    while v < 33:
        v += 94
    return v if v <= 126 else None


def legal_bytes(addr):
    """The 8 loader-legal bytes at addr, keyed by code."""
    return {c: byte_for(c, addr) for c in VALID_CODES if byte_for(c, addr) is not None}


def load(prog):
    """Validate as source and build initial memory."""
    ex = bytes(b for b in prog if not (33 <= b <= 126) or True)
    ex = bytes(b for b in prog if b not in b" \t\r\n")
    for a, b in enumerate(ex):
        if not (33 <= b <= 126):
            raise ValueError(f"non-printable byte {b} at {a}")
        if code_of(b, a) not in VALID_CODES:
            raise ValueError(f"byte {b} at {a} decodes to invalid code {code_of(b, a)}")
    mem = [0] * M
    for i, b in enumerate(ex):
        mem[i] = b
    for i in range(len(ex), M):
        mem[i] = crazy(mem[i - 1], mem[i - 2])
    return mem, len(ex)


def run(prog, inp, max_steps=2048, max_out=1, trace=None):
    """Returns (output_bytes, status, steps).  trace: list to append (step,c,d,a,code)."""
    mem, _ = load(prog)
    a, c, d, ii = 0, 0, 0, 0
    out = bytearray()
    for step in range(max_steps):
        w = mem[c]
        if not (33 <= w <= 126):
            return bytes(out), f"InvalidRuntimeInstruction@{c}={w}", step
        code = code_of(w, c)
        if trace is not None:
            trace.append((step, c, d, a, code, mem[d]))
        if code == 4:
            c = mem[d]
        elif code == 5:
            if len(out) >= max_out:
                return bytes(out), "OutputLimitExceeded", step
            out.append(a % 256)
        elif code == 23:
            if ii < len(inp):
                a = inp[ii]
                ii += 1
            else:
                a = 59048
        elif code == 39:
            mem[d] = rotr(mem[d])
            a = mem[d]
        elif code == 40:
            d = mem[d]
        elif code == 62:
            mem[d] = crazy(a, mem[d])
            a = mem[d]
        elif code == 81:
            return bytes(out), "Halted", step + 1
        wc = mem[c]
        if not (33 <= wc <= 126):
            return bytes(out), f"InvalidRuntimeInstruction@{c}={wc}", step
        mem[c] = XLAT2[wc - 33]
        c = (c + 1) % M
        d = (d + 1) % M
    return bytes(out), "StepLimitExceeded", max_steps


if __name__ == "__main__":
    import sys
    prog = open(sys.argv[1], "rb").read()
    inp = bytes([int(sys.argv[2], 16)]) if len(sys.argv) > 2 else b""
    tr = []
    out, st, steps = run(prog, inp, trace=tr)
    for (s, c, d, aa, code, md) in tr[: int(sys.argv[3]) if len(sys.argv) > 3 else 60]:
        print(f"{s:4d} c={c:5d} d={d:5d} A={aa:6d} m[d]={md:6d} {NAMES[code]}")
    print("out", out.hex(), st, steps)
