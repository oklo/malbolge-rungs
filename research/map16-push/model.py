#!/usr/bin/env python3
"""Shared model for L2.FM3.xor51-map16 under the data-dispatch table architecture.

Architecture (inherited from cov48 -> map12-low -> map16):

    IN                        A = b
    CRZ W1, CRZ W2            A = g(b) + K0, parked in cell Q_W2
    MOVD on Q_W2              D = g(b) + K0 + 1
    NOP^s                     D = base + g(b),  base = K0 + 1 + s
    CRZ/NOP pattern P         A = crazy^K(A, mem[base+g(b)+p_i])
    OUT, HALT                 out = A mod 256

`g` is applied trit-by-trit: g_i = M[w2_i] o M[w1_i], and W1/W2 are ordinary
memory words so each trit's pair may be chosen independently.

This file carries the algebra only; builder lives in build.py.
"""

INPUTS = [0x02, 0x06, 0x09, 0x30, 0x82, 0x6F, 0xA7, 0xC0,
          0xC5, 0xF6, 0x1C, 0x87, 0xF0, 0x2D, 0x4A, 0x85]
MASK = 0x51
TARGETS = {b: b ^ MASK for b in INPUTS}

OPS = [4, 5, 23, 39, 40, 62, 68, 81]          # jmp out in rot movd crz nop halt
NOP, OUT, IN, ROT, MOVD, CRZ, HALT, JMP = 68, 5, 23, 39, 40, 62, 81, 4

CR = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]        # CR[d][a], matches crazy_trit
ENC = (b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.T"
       b"Vac`uY*MK'X~xDl}REokN:#?G\"i@")


def crazy(a, d):
    out, f = 0, 1
    for _ in range(10):
        out += CR[d % 3][a % 3] * f
        a //= 3
        d //= 3
        f *= 3
    return out


def rot_r(w):
    return w // 3 + (w % 3) * 3 ** 9


def trits(w, n=10):
    return [(w // 3 ** i) % 3 for i in range(n)]


def from_trits(ts):
    return sum(t * 3 ** i for i, t in enumerate(ts))


def legal_bytes(addr):
    """the eight source-valid bytes at `addr`."""
    out = []
    for op in OPS:
        b = (op - addr) % 94
        if b < 33:
            b += 94
        out.append(b)
    return out


def codebyte(addr, code):
    b = (code - addr) % 94
    if b < 33:
        b += 94
    assert 33 <= b <= 126
    return b


def xval(addr):
    """value a cell holds after C executed it as a NOP (post-encryption)."""
    return ENC[codebyte(addr, NOP) - 33]


# ---------------------------------------------------------------- dispatch maps
M = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]         # M[w] = a -> CR[w][a]


def compose(w1, w2):
    """g = M[w2] o M[w1] as a triple."""
    return tuple(M[w2][M[w1][a]] for a in range(3))


PAIRS = {}                                     # g-triple -> list of (w1,w2)
for w1 in range(3):
    for w2 in range(3):
        PAIRS.setdefault(compose(w1, w2), []).append((w1, w2))


# --------------------------------------------------------- lane trit-4 grouping
RED = {b: b % 243 for b in INPUTS}              # reduced (trit 5 crushed)
T4 = {b: (RED[b] // 81) for b in INPUTS}        # trit 4 of the reduced input
REST = {b: RED[b] % 81 for b in INPUTS}


def addresses_distinct(g4):
    """with trit4 mapped by g4 and trits 0..3 identity, are the 16 addresses
    distinct?  (only pair sharing REST is 0x6f/0xc0, t4 = 1 vs 2)"""
    seen = set()
    for b in INPUTS:
        key = (g4[T4[b]], REST[b])
        if key in seen:
            return False
        seen.add(key)
    return True


# ------------------------------------------------------------- frozen high part
def hi_final(K0, K):
    hs = K0 // 243
    return sum(((min((hs // 3 ** j) % 3, 1) + K) % 2) * 3 ** j for j in range(5))


def H_of(K0, K):
    return 243 * hi_final(K0, K)


def lane_report(K0, K, g4):
    """per-lane (start_t4, L*, needed t4, ok?)"""
    h = H_of(K0, K) % 256
    rows = []
    for b in INPUTS:
        Ls = (TARGETS[b] - h) % 256
        st = g4[T4[b]]
        if Ls > 242:
            rows.append((b, st, Ls, None, False, "L*>242"))
            continue
        want = Ls // 81
        if st == 2:
            ok = True                      # 2 stays with all-t4=1 operands; 0/1 by drop step
            why = "free"
        else:
            ok = (want == (st + K) % 2)
            why = "pinned t4=%d" % ((st + K) % 2)
        rows.append((b, st, Ls, want, ok, why))
    return rows


def ceiling(K0, K, g4):
    return sum(1 for r in lane_report(K0, K, g4) if r[4])


if __name__ == "__main__":
    print("reduced inputs:", {hex(b): RED[b] for b in INPUTS})
    print("t4 groups: ", {v: [hex(b) for b in INPUTS if T4[b] == v] for v in (0, 1, 2)})
    print("g maps from 2 dispatch CRZs:", sorted(PAIRS))
    print("g4 keeping addresses distinct:",
          [g for g in sorted(PAIRS) if addresses_distinct(g)])
    best = []
    for hs in range(1, 16):
        K0 = 243 * hs
        for K in range(2, 13):
            for g4 in sorted(PAIRS):
                if not addresses_distinct(g4):
                    continue
                best.append((ceiling(K0, K, g4), K0, K, g4))
    best.sort(reverse=True)
    print("\ntop configurations (ceiling, K0, K, g4):")
    seen = set()
    for c, K0, K, g4 in best[:400]:
        key = (c, K0, K % 2, g4)
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > 14:
            break
        print("  %2d/16  K0=%4d K%%2=%d g4=%s  h=%3d  dead=%s"
              % (c, K0, K % 2, g4, H_of(K0, K) % 256,
                 [hex(r[0]) for r in lane_report(K0, K, g4) if not r[4]]))
