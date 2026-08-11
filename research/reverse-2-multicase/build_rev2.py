"""Builder for L3.R0.reverse-2-multicase (byte-swap of the first two input bytes).

Architecture (no input-dependent dispatch anywhere -- see the report):

    0              IN                A = b0
    1 .. a1-1      NOP               D tracks C (D == C while nothing writes D)
    a1             MOVD              D = m[a1]+1 = D1   (reads its own instruction byte)
    a1+1           MOVD              D = m[D1]+1 = Q-1  (m[D1] = Q-2)
    a1+2           CRZ   D=Q-1       m[Q-1] = crazy(b0,121)
    a1+3           CRZ   D=Q         m[Q] = b0 exactly, A = b0, D -> Q+1
    9 x            MOVD  D=Q+1       D = m[Q+1]+1 = X   (m[Q+1] = X-1)
                   MOVD  D=X         D = m[X]+1  = Q    (m[X]   = Q-1)
                   ROT   D=Q         m[Q] = rotr(m[Q]); D -> Q+1
                                     after 9 rotations m[Q] = rotr^9(b0) = rotl(b0) = 3*b0
    a1+31          IN                A = b1,  D -> Q+2
    a1+32          OUT               emit b1  (first output byte)  D -> Q+3
    k x            NOP               walk D from Q+3 to Z
                   MOVD  D=Z         D = m[Z]+1  = X2   (m[Z]  = X2-1)
                   MOVD  D=X2        D = m[X2]+1 = Q    (m[X2] = Q-1)
                   ROT   D=Q         A = rotr(3*b0) = b0
                   OUT               emit b0  (second output byte)
                   HALT

The double CRZ against a pair of cells holding 121 = 11111_3 restores A exactly:
for trits 0..4 the memory trit is 1 and R_1 = swap01 is an involution; for trits
5..9 the memory trit is 0 and R_0 agrees with swap01 on {0,1}, which is all b0
occupies (b0 < 256 < 2*3^5).  So m[Q] = b0 with every trit right, which is what
the rotation arithmetic needs.

ROT is the only instruction that loads A from memory without mixing in the old A,
and it rotates; hence the 9+1 rotation split around the b1 output.
"""
import itertools
import sys

from mal import OPSET, MOVD, CRZ, ROT, IN, OUT, NOP, HALT, JMP, bytes_for, legal_byte, VM, check_source

PARK_PAIRS = [q for q in range(2, 128) if legal_byte(121, q - 1) and legal_byte(121, q)]


def build(q, a1, k, x, x2, d1):
    """Return (program bytes, code_len) or None if the layout is inconsistent."""
    code = []          # list of (addr, opcode)
    data = {}          # addr -> byte value

    def emit(op):
        code.append(op)

    emit(IN)
    for _ in range(1, a1):
        emit(NOP)
    emit(MOVD)         # at a1
    emit(MOVD)         # at a1+1
    emit(CRZ)
    emit(CRZ)
    for _ in range(9):
        emit(MOVD); emit(MOVD); emit(ROT)
    emit(IN)
    emit(OUT)
    for _ in range(k):
        emit(NOP)
    emit(MOVD); emit(MOVD); emit(ROT); emit(OUT); emit(HALT)
    code_len = len(code)

    # the first MOVD reads its own byte; that byte must be exactly d1-1
    v1 = d1 - 1
    if not legal_byte(v1, a1) or (v1 + a1) % 94 != MOVD:
        return None

    def put(addr, val):
        if addr < code_len or addr > 511:
            return False
        if addr in data and data[addr] != val:
            return False
        if not legal_byte(val, addr):
            return False
        data[addr] = val
        return True

    z = q + 3 + k
    if not put(d1, q - 2):
        return None
    if not put(q - 1, 121) or not put(q, 121):
        return None
    if not put(q + 1, x - 1) or not put(x, q - 1):
        return None
    if not put(z, x2 - 1) or not put(x2, q - 1):
        return None

    length = max(max(data), code_len) + 1
    prog = [None] * length
    for addr, op in enumerate(code):
        cands = bytes_for(op, addr)
        if not cands:
            return None
        if addr == a1:
            prog[addr] = v1
        else:
            prog[addr] = cands[0]
    for addr, val in data.items():
        prog[addr] = val
    for addr in range(length):
        if prog[addr] is None:
            fill = [v for v in range(33, 127) if legal_byte(v, addr)]
            if not fill:
                return None
            prog[addr] = fill[0]
    if check_source(prog):
        return None
    return bytes(prog), code_len


def score(prog, samples=None):
    """Exhaustive (or sampled) check that the program swaps the first two bytes."""
    if samples is None:
        samples = [(b0, b1) for b0 in range(256) for b1 in range(256)]
    bad = []
    for b0, b1 in samples:
        vm = VM(prog, bytes([b0, b1]) + b"\x00" * 30)
        status, steps = vm.run()
        if status != "Halted" or vm.out != [b1, b0]:
            bad.append((b0, b1, status, vm.out))
            if len(bad) > 4:
                break
    return bad


def search():
    """Filter the independent constraints directly instead of calling build() 10^7 times."""
    hits = []
    for q in PARK_PAIRS:
        for a1 in range(1, 120):
            for v1 in bytes_for(MOVD, a1):
                d1 = v1 + 1
                for k in range(0, 60):
                    code_len = a1 + k + 38
                    z = q + 3 + k
                    fixed = {d1: q - 2, q - 1: 121, q: 121}
                    ok = all(addr >= code_len and legal_byte(val, addr)
                             for addr, val in fixed.items())
                    if not ok or len(set(fixed)) != 3:
                        continue
                    xs = [x for x in range(34, 128)
                          if x >= code_len and x not in fixed and x != q + 1 and x != z
                          and legal_byte(q - 1, x) and legal_byte(x - 1, q + 1)
                          and q + 1 >= code_len and q + 1 not in fixed]
                    x2s = [x for x in range(34, 128)
                           if x >= code_len and x not in fixed and x != q + 1 and x != z
                           and legal_byte(q - 1, x) and legal_byte(x - 1, z)
                           and z >= code_len and z not in fixed]
                    for x in xs:
                        for x2 in x2s:
                            if x2 == x:
                                continue
                            r = build(q, a1, k, x, x2, d1)
                            if r:
                                hits.append((q, a1, k, x, x2, d1, len(r[0]), r[1]))
    return hits


if __name__ == "__main__":
    print("park pairs (Q):", PARK_PAIRS)
    hits = search()
    print(f"{len(hits)} candidate layouts")
    for h in hits[:10]:
        print("  q=%d a1=%d k=%d X=%d X2=%d D1=%d len=%d code_len=%d" % h)
    if not hits:
        sys.exit("no layout")
    # verify the shortest program in the model VM, exhaustively
    hits.sort(key=lambda h: h[6])
    q, a1, k, x, x2, d1 = hits[0][:6]
    prog, code_len = build(q, a1, k, x, x2, d1)
    print("chosen:", hits[0])
    quick = score(prog, [(0, 0), (1, 2), (0x41, 0x42), (255, 255), (242, 243), (0x12, 0xc7)])
    print("quick check bad:", quick[:3])
    open("cand.mal", "wb").write(prog)
    print("wrote cand.mal, %d bytes, code_len=%d" % (len(prog), code_len))
    vm = VM(prog, bytes([0x41, 0x42]) + b"\x00" * 30)
    print(vm.run(trace=("-t" in sys.argv)), vm.out)
