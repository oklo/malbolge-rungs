#!/usr/bin/env python3
"""Emit the *exact-optimal* multiply-by-9 candidate for L2.R0d.xor-1-len4096.

Same layout as gen.py (43 bytes of straight-line code, 7 CRZs walking the
private block 9b+1..9b+7), but the per-input operand tuple is found by exact
reachability over the low five trits instead of 4000 random samples.  gen.py
reports 114/256; the exact search reaches 119/256 and no tuple exists for the
other 137 inputs -- that is the architecture's ceiling at depth 7, not a
search-effort number.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import XLAT2, byte_for_op, valid_bytes, trits, CT
from exact import (CODE, DATA, prog_bytes, cell_options, forced_high,
                   low_trit_step, low5, MASK)

N = 2310
K = 7


def main():
    prog = prog_bytes(N)
    solved, dead, unreach = [], [], []
    for b in range(256):
        tgt = b ^ MASK
        H = forced_high(b, K)
        L = (tgt - 243 * H) % 256
        if L > 242:
            dead.append(b)
            continue
        reach = {low5(9 * b): []}
        for j in range(1, K + 1):
            opts = cell_options(9 * b + j, prog)
            nxt = {}
            for s, path in reach.items():
                for w in opts:
                    t = low_trit_step(s, w)
                    if t not in nxt:
                        nxt[t] = path + [w]
            reach = nxt
        if L not in reach:
            unreach.append(b)
            continue
        solved.append(b)
        for j, w in enumerate(reach[L], start=1):
            addr = 9 * b + j
            if addr >= len(CODE) and addr not in DATA:
                prog[addr] = w
    print(f"exact depth-{K} coverage: {len(solved)}/256")
    print(f"  unreachable because L>242 (top trits forced): {len(dead)}")
    print(f"  unreachable in the low five trits:            {len(unreach)}")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cand.mal")
    open(out, "wb").write(bytes(prog))
    print("wrote", out, len(prog), "bytes")
    open(os.path.join(os.path.dirname(out), "covered.txt"), "w").write(
        " ".join(map(str, solved)) + "\n")


if __name__ == "__main__":
    main()
