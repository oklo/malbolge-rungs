#!/usr/bin/env python3
"""Shared model for the L2.FM2l.xor51-map12-low data-dispatch table architecture,
generalised to a NOP-spaced (non-consecutive) table walk.

Architecture (from docs/attempts/2026-08-10-claude-map12-low.md):

    IN                       A = b
    CRZ W1, CRZ W2           A = b + K0     (K0 a multiple of 81), parked
    MOVD                     D = b + K0 + 1
    NOP^s                    D = b + K0 + 1 + s          <-- NEW: free phase shift
    CRZ / NOP pattern P      lane b reads cells base + b + p_i, base = K0+1+s
    OUT, HALT                out = A mod 256

Two degrees of freedom the 2026-08-10 attempt did not use:

  * the phase shift `s`.  The candidate byte set at an address depends only on
    (address mod 94).  With s = 0 the residue of the table base is pinned to
    (K0 + 1) mod 94; K0 is a multiple of 81 so only 94/gcd choices existed, and
    they were coupled to the choice of H.  `s` decouples them completely.
  * the walk pattern P = (0 = p_1 < p_2 < ... < p_K).  With NOPs between the
    CRAZYs, lane b reads cells base+b+p_i.  Two lanes collide iff their input
    difference lies in P - P.  Choosing P so that (P-P) misses every pairwise
    input difference makes the twelve lanes *independent*, which is exactly the
    obstruction the prior exact DP reported ("window overlap, not lane
    liveness").

Trit algebra used throughout (all of it is in the prior record; restated here
because the code depends on it being exactly right):

  * every table operand is a source-valid program byte, so it is printable
    (33..126), so its trits 5..9 are 0 and CRAZY acts on those trits by
    g0 = (1,0,0).  Both g0 and g1 = (1,0,2) restrict to the swap 0<->1.
  * hence trits 5..9 of the accumulator after K crazies are a function of K0
    and the parity of K alone -> a frozen high part H = 243 * hi_final, where
    hi_final's trits are (min(t,1) + K) mod 2 for the corresponding trit t of
    floor(K0/243).  Reachable H = 243 * (any subset of {1,3,9,27,81}).
  * printable operands have trit4 in {0,1}, so if the accumulator's start trit4
    (= (K0/81) mod 3, since every rung input is < 81) is 0 or 1, the final trit4
    is deterministic: (start + K) mod 2.  Then trits 0..3 decouple entirely.
  * out = (H + 81*t4 + r) mod 256 with r in [0,80] the trit-0..3 part.
"""

INPUTS = [0x08, 0x37, 0x35, 0x1A, 0x2A, 0x32, 0x38, 0x2F, 0x0D, 0x18, 0x3B, 0x14]
MASK = 0x51
TARGETS = {b: b ^ MASK for b in INPUTS}

OPS = [4, 5, 23, 39, 40, 62, 68, 81]  # jmp out in rot movd crz nop halt

CR = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]  # CR[d][a]


def crazy(a, d):
    out, f = 0, 1
    for _ in range(10):
        out += CR[d % 3][a % 3] * f
        a //= 3
        d //= 3
        f *= 3
    return out


def legal_bytes(addr):
    """the eight source-valid bytes at `addr` (one per Malbolge op)."""
    out = []
    for op in OPS:
        b = (op - addr) % 94
        if b < 33:
            b += 94
        out.append(b)
    return out


def pairwise_diffs():
    s = sorted(INPUTS)
    return {y - x for i, x in enumerate(s) for y in s[i + 1:]}


DIFFS = pairwise_diffs()


def collision_free(P):
    for i in range(len(P)):
        for j in range(i + 1, len(P)):
            if P[j] - P[i] in DIFFS:
                return False
    return True


def reachable_H(K):
    """(hi_final, H) pairs realisable at walk depth K, and the K0 hi-parts that
    realise them.  hi_final trits are all in {0,1}."""
    out = []
    for mask in range(32):
        hi = sum(((mask >> j) & 1) * 3 ** j for j in range(5))
        out.append((hi, 243 * hi))
    return out


def hi_source(hi_final, K):
    """trits of floor(K0/243) that map to hi_final at depth K.  Returns the
    canonical smallest one (using only trits 0/1)."""
    v, f = 0, 1
    for j in range(5):
        want = (hi_final // 3 ** j) % 3
        # want = (min(t,1) + K) mod 2  ->  min(t,1) = (want - K) mod 2
        t = (want - K) % 2
        v += t * f
        f *= 3
    return v


def lane_requirements(H):
    """per-lane (t4, r) needed, or None if some lane's L* is out of range."""
    req = {}
    h = H % 256
    for b in INPUTS:
        Ls = (TARGETS[b] - h) % 256
        if Ls > 242:
            return None
        req[b] = (Ls // 81, Ls % 81)
    return req


def low_reach(start_r, addrs):
    """set of reachable trit-0..3 values (0..80) after walking `addrs`."""
    cur = {start_r}
    for a in addrs:
        vals = [v % 81 for v in legal_bytes(a)]
        nxt = set()
        for s in cur:
            for v in vals:
                # crazy restricted to trits 0..3
                o, f = 0, 1
                x, y = s, v
                for _ in range(4):
                    o += CR[y % 3][x % 3] * f
                    x //= 3
                    y //= 3
                    f *= 3
                nxt.add(o)
        cur = nxt
    return cur


def low_paths(start_r, addrs, want):
    """one concrete byte choice per address reaching `want`, or None."""
    K = len(addrs)
    # backward reachable sets
    back = [None] * (K + 1)
    back[K] = {want}
    for i in range(K - 1, -1, -1):
        vals = [v % 81 for v in legal_bytes(addrs[i])]
        s = set()
        for x in range(81):
            for v in vals:
                o, f = 0, 1
                a, y = x, v
                for _ in range(4):
                    o += CR[y % 3][a % 3] * f
                    a //= 3
                    y //= 3
                    f *= 3
                if o in back[i + 1]:
                    s.add(x)
                    break
        back[i] = s
    if start_r not in back[0]:
        return None
    cur, chosen = start_r, []
    for i in range(K):
        raw = legal_bytes(addrs[i])
        for v in raw:
            o, f = 0, 1
            a, y = cur, v % 81
            for _ in range(4):
                o += CR[y % 3][a % 3] * f
                a //= 3
                y //= 3
                f *= 3
            if o in back[i + 1]:
                chosen.append(v)
                cur = o
                break
        else:
            return None
    return chosen
