#!/usr/bin/env python3
"""Why the dispatch stride is 9, and why the 4096-byte cap cannot buy a wider one.

The prologue reads b with IN, then applies eight ROTs.  rotr is a 10-trit rotate
right, so eight of them are a rotate LEFT by two trits, i.e. x9 for any b < 3^8.
The dispatch is c = m[72] = 9b, so input b owns exactly the nine cells
9b+1..9b+9.  Nine cells is the whole reason this rung is hard: every block also
has to serve as the operand tape every other input reads from d = 73.

The obvious use of a 4096-byte program (this rung is L2.R0.xor-1 with the length
cap raised from 256 to 4096, and nothing else) is a wider stride.  It is not
available:

  * Rotation is the only information-preserving primitive, and it only
    multiplies by powers of 3.  x27 puts input 255 at address 6885, past the cap.
  * CRZ cannot substitute.  crazy(a,d) is trit-wise with
    CT = [[1,0,0],[1,0,2],[2,2,1]]; CT[0] and CT[2] are 2-to-1 and only CT[1] is
    injective.  An operand that is a program byte is <= 126 < 3^5, so its trits
    5..9 are all 0 and CT[0] is applied there -- which collapses b's high trits.
    A = 9b has b's trits at positions 2..7, so trits 5,6,7 of A (= trits 3,4,5
    of b, i.e. b div 27) are destroyed by the very first CRZ.
  * Two CRZs do not recover it, and no (K1,K2) makes crazy(crazy(9b,K1),K2)
    injective at all -- checked exhaustively below.

So stride 9 is forced, and the extra 1791 bytes cannot be spent on wider blocks.
What they CAN be spent on is the tail: see the report.
"""
CT = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]


def trits(w):
    o = []
    for _ in range(10):
        o.append(w % 3)
        w //= 3
    return o


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


if __name__ == "__main__":
    # eight ROTs on b is exactly 9b for every input byte
    assert all(from_trits(trits(b)) == b for b in range(256))
    for b in range(256):
        v = b
        for _ in range(8):
            v = rotr(v)
        assert v == 9 * b, (b, v)
    print("eight ROTs == x9 for all 256 inputs: OK")

    # a single crazy against a byte operand is always >= 3^8 + 3^9
    lo = min(crazy(9 * b, k) for b in range(256) for k in range(33, 127))
    print("min crazy(9b, byte) =", lo, "(= 3^8+3^9 =", 3 ** 8 + 3 ** 9, ")")

    # no two-CRZ dispatch is injective, for any pair of byte operands
    inj = 0
    for k1 in range(33, 127):
        h1 = [crazy(9 * b, k1) for b in range(256)]
        for k2 in range(33, 127):
            if len(set(crazy(v, k2) for v in h1)) == 256:
                inj += 1
    print("injective (K1,K2) two-CRZ dispatch families out of 8836:", inj)

    # x27 does not fit
    print("stride 27 would put input 255 at", 27 * 255, "> 4096 cap")
