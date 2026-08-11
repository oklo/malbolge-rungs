"""Exhaustive model check of cand-rev2.mal over all 65536 (b0,b1) pairs.

The base memory image is built once; each run uses a copy-on-write dict overlay,
so 65536 runs are cheap.  Also records the set of (C,D) pairs visited, to show
the control flow is identical for every input (the program has no
input-dependent dispatch at all).
"""
from mal import ENCIPHER, crazy, rotr, icode, JMP, OUT, IN, ROT, MOVD, CRZ, HALT

MOD = 59049
prog = open("cand-rev2.mal", "rb").read()

BASE = [0] * MOD
for i, b in enumerate(prog):
    BASE[i] = b
for i in range(len(prog), MOD):
    BASE[i] = crazy(BASE[i - 1], BASE[i - 2])


def run(b0, b1, path=None):
    ov = {}
    def rd(i):
        return ov[i] if i in ov else BASE[i]
    a = c = d = 0
    inp = [b0, b1]
    ii = 0
    out = []
    for step in range(8192):
        if path is not None:
            path.append((c, d))
        f = rd(c)
        if not (33 <= f <= 126):
            return "InvalidRuntimeInstruction", out
        code = icode(f, c)
        if code == JMP:
            c = rd(d)
        elif code == OUT:
            if len(out) >= 2:
                return "OutputLimitExceeded", out
            out.append(a % 256)
        elif code == IN:
            a = inp[ii] if ii < len(inp) else 59048
            ii += 1
        elif code == ROT:
            v = rotr(rd(d)); ov[d] = v; a = v
        elif code == MOVD:
            d = rd(d)
        elif code == CRZ:
            v = crazy(a, rd(d)); ov[d] = v; a = v
        elif code == HALT:
            return "Halted", out
        w = rd(c)
        if not (33 <= w <= 126):
            return "InvalidRuntimeInstruction", out
        ov[c] = ENCIPHER[w - 33]
        c = (c + 1) % MOD
        d = (d + 1) % MOD
    return "StepLimitExceeded", out


if __name__ == "__main__":
    ref = []
    run(0, 0, ref)
    bad = 0
    paths_differ = 0
    for b0 in range(256):
        for b1 in range(256):
            p = [] if (b0 % 37 == 0 and b1 % 37 == 0) else None
            st, out = run(b0, b1, p)
            if st != "Halted" or out != [b1, b0]:
                bad += 1
                if bad < 6:
                    print("FAIL", hex(b0), hex(b1), st, out)
            if p is not None and p != ref:
                paths_differ += 1
    print("program length", len(prog), "steps", len(ref))
    print("failures over 65536 pairs:", bad)
    print("sampled control-flow paths differing from the b0=b1=0 path:", paths_differ)
