#!/usr/bin/env python3
"""Exact ceiling for the multiply-by-9 dispatch on L2.R0d.xor-1-len4096.

gen.py samples 4000 random operand tuples per input and reports 114/256.  That
number is not the architecture's ceiling; this computes the ceiling exactly.

The structural fact that decides the rung:

  every program byte is in 33..126 < 243 = 3^5, so trits 5..9 of *any* operand
  are 0, and crazy's trit table with operand trit 0 is M0 = (0->1, 1->0, 2->0).

So the top five trits of the accumulator evolve under M0 with no choice at all:
after k >= 1 crazy steps they are a function of the input and of the *parity*
of k alone (M0^k(0)=k odd?1:0, M0^k(1)=k odd?0:1, M0^k(2)=k odd?0:1).

Write the final accumulator as A = 243*H + L with H forced and L in 0..242.
OUT emits A % 256, so L = (target - 243*H) mod 256 is *uniquely determined*,
and the input is unreachable outright whenever that residue lands in 243..255.
Only the low five trits are searchable, and they are searchable exactly:
243 states, k levels, 8 operand choices per level.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import OPS, XLAT2, code_of, byte_for_op, valid_bytes, trits, CT

MASK = 0x51

# ---- the code layout gen.py emits (address -> forced byte), so that block
# ---- cells overlapping the code are modelled with their true (enciphered) value
CODE = ([23] + [40, 40, 40] + [62, 62] + [40, 40, 39] * 8 + [40, 40, 40]
        + [62] * 7 + [68] + [5, 81])
DATA = {62: 71, 71: 121, 72: 121, 73: 61, 123: 70}


def prog_bytes(n):
    p = [None] * n
    for a, op in enumerate(CODE):
        p[a] = byte_for_op(op, a)
    for a, v in DATA.items():
        p[a] = v
    for a in range(n):
        if p[a] is None:
            p[a] = valid_bytes(a)[0]
    return p


def cell_options(addr, prog):
    """Byte values cell `addr` can hold when the chain reads it."""
    if addr < len(CODE):                       # executed already -> enciphered
        return [XLAT2[prog[addr] - 33]]
    if addr in DATA:                           # pinned pointer/constant
        return [DATA[addr]]
    return valid_bytes(addr)                   # free: exactly 8 legal bytes


def low5(v):
    return v % 243


def hi5(v):
    return v // 243


def m0k(t, k):
    """M0^k applied to trit t (k >= 1)."""
    if k == 0:
        return t
    odd = k % 2 == 1
    if t == 0:
        return 1 if odd else 0
    return 0 if odd else 1


def forced_high(b, k):
    """trits 5..9 of the accumulator after k crazy steps, starting from 9*b."""
    t = trits(9 * b)
    out = 0
    for i in range(9, 4, -1):
        out = out * 3 + m0k(t[i], k)
    return out


def low_trit_step(cur, w):
    """crazy on the low five trits only."""
    tc, tw = trits(cur), trits(w)
    r = 0
    for i in range(4, -1, -1):
        r = r * 3 + CT[(tw[i], tc[i])]
    return r


def analyse(kmax=12, n=2310):
    prog = prog_bytes(n)
    rows = []
    for k in range(1, kmax + 1):
        feasible, dead_residue, unreachable = [], [], []
        for b in range(256):
            tgt = b ^ MASK
            H = forced_high(b, k)
            L = (tgt - 243 * H) % 256
            if L > 242:
                dead_residue.append(b)
                continue
            # exact reachable set of the low five trits
            reach = {low5(9 * b): []}
            for j in range(1, k + 1):
                opts = cell_options(9 * b + j, prog)
                nxt = {}
                for s, path in reach.items():
                    for w in opts:
                        t = low_trit_step(s, w)
                        if t not in nxt:
                            nxt[t] = path + [w]
                reach = nxt
            if L in reach:
                feasible.append((b, reach[L]))
            else:
                unreachable.append(b)
        rows.append((k, len(feasible), len(dead_residue), len(unreachable)))
        print(f"k={k:2d}  solved={len(feasible):3d}/256   "
              f"dead-residue(L>242)={len(dead_residue):3d}   "
              f"low-trits-unreachable={len(unreachable):3d}")
    return rows


def parity_union(kodd, keven, n=2310):
    """If the chain length could be chosen per input (odd vs even tail), how
    many inputs are covered by the union?"""
    prog = prog_bytes(n)
    ok = set()
    detail = {}
    for k in (kodd, keven):
        for b in range(256):
            tgt = b ^ MASK
            H = forced_high(b, k)
            L = (tgt - 243 * H) % 256
            if L > 242:
                continue
            reach = {low5(9 * b)}
            for j in range(1, k + 1):
                opts = cell_options(9 * b + j, prog)
                reach = {low_trit_step(s, w) for s in reach for w in opts}
            if L in reach:
                ok.add(b)
                detail.setdefault(b, []).append(k)
    print(f"union of k={kodd} and k={keven}: {len(ok)}/256 "
          f"(missing {sorted(set(range(256)) - ok)})")
    return ok


if __name__ == "__main__":
    analyse()
    print()
    for pair in ((7, 8), (9, 8), (7, 10), (9, 10), (11, 12)):
        parity_union(*pair)
