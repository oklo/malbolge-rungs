#!/usr/bin/env python3
"""Retarget the favorable safe dispatcher from D=43 to D=42.

The original safe-dispatch tape computes q=9*(b+81) in cell 42 and jumps
through it, entering the private block with D=43.  Exact block synthesis shows
that the same low-memory geometry is much more expressive when the block sees
D=42.  To obtain that state without disturbing cell 42, this patch makes two
additional copies of the K4 constant (3276), in cells 41 and 68.  At the end,
three applications of the K4 involution perform

    e --K4@42--> q --K4@68--> e --K4@41--> q,

so both cells 41 and 42 contain q.  Jumping through cell 41 then enters q+1
with D=42.

The extra K4 constants are made after the original one.  Starting with
A=3276, two self-CRAZY operations turn either old cell value 58 or 94 into
3276 and restore A=3276.  The remaining prologue opcode stream can therefore
be replayed unchanged at a later C phase.

The final epilogue also rotates the persistent 26248 constant through a full
cycle and applies it to cell 120.  Since CRAZY(26248,55)=3303, this installs a
private-tail pointer and deliberately leaves A=3303.  That accumulator phase
eliminates the otherwise sealed input 216 block; all residual exceptions have
high-memory exits.
"""
from pathlib import Path
import sys

M = 59049
OPS = {4, 5, 23, 39, 40, 62, 68, 81}
JMP, OUT, IN, ROT, MOVD, CRZ, NOP, HLT = 4, 5, 23, 39, 40, 62, 68, 81
X = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CT = ((1, 0, 0), (1, 0, 2), (2, 2, 1))


def crazy(a, d):
    r = 0
    p = 1
    for _ in range(10):
        r += CT[(d // p) % 3][(a // p) % 3] * p
        p *= 3
    return r


def rotr(w):
    return w // 3 + (w % 3) * 19683


def byte_for(op, addr):
    v = (op - addr) % 94
    while v < 33:
        v += 94
    assert v <= 126
    return v


def op_at(program, addr):
    op = (program[addr] + addr) % 94
    assert op in OPS, (addr, program[addr], op)
    return op


def route(text):
    return [NOP if ch == "N" else MOVD for ch in text]


def patch(source, destination):
    program = bytearray(Path(source).read_bytes())
    assert len(program) == 4096

    # The favorable tape's sequential main-code stream is C=127..633.  Keep
    # it through the first K4 manufacture at C=280.
    old = [op_at(program, a) for a in range(127, 634)]
    assert old[280 - 127] == CRZ
    assert old[281 - 127] == IN
    assert old[616 - 127] == MOVD
    assert old[617 - 127] == CRZ
    assert old[633 - 127] == JMP

    manufacture = []
    manufacture += route("NMMM")       # D 43 -> 41
    manufacture += [CRZ]                # 58 -> 26302
    manufacture += route("NNMMM")      # D 42 -> 41
    manufacture += [CRZ]                # 26302 -> K4
    manufacture += route("NNMNNNNNM")  # D 42 -> 68
    manufacture += [CRZ]                # 94 -> 26248
    manufacture += route("MNM")         # D 69 -> 68
    manufacture += [CRZ]                # 26248 -> K4
    manufacture += route("NNMMNN")      # D 69 -> 43
    assert len(manufacture) == 31

    # Replay through the original final q computation, then echo q into cell
    # 41.  Manufacture the 3303 pointer/accumulator phase before dispatch.
    tail = []
    tail += route("NMNNNNNM")           # D 43 -> 68
    tail += [CRZ]                        # q -> e
    tail += route("MNNNNNMNNNNNN")      # D 69 -> 41
    tail += [CRZ]                        # e -> q
    tail += route("NNMNNN")             # D 42 -> 93
    for i in range(10):
        tail += [ROT]                    # full cycle loads A=26248
        if i != 9:
            tail += route("MM")         # D 94 -> 100 -> 93
    tail += route("NNNNMNMNM")          # D 94 -> 120
    tail += [CRZ]                        # CRAZY(26248,55)=3303
    tail += route("NM")                  # D 121 -> 41
    tail += [JMP]

    stream = old[: 281 - 127] + manufacture + old[281 - 127 : 618 - 127] + tail
    assert 127 + len(stream) <= 729, len(stream)
    for i, op in enumerate(stream):
        program[127 + i] = byte_for(op, 127 + i)
    # Erase the no-longer-executed part of the old main stream.
    for a in range(127 + len(stream), 729):
        program[a] = byte_for(NOP, a)

    Path(destination).write_bytes(program)
    print(f"wrote {destination}: {len(program)} bytes, main C=127..{126+len(stream)}")


def dispatch_state(path, b):
    p = list(Path(path).read_bytes())
    mem = p + [0] * (M - len(p))
    for i in range(len(p), M):
        mem[i] = crazy(mem[i - 1], mem[i - 2])
    A = C = D = used = 0
    want = 9 * (b + 81) + 1
    for step in range(800):
        if C == want:
            return step, A, C, D, mem[41], mem[42], mem[68], mem[120]
        w = mem[C]
        if not 33 <= w <= 126:
            break
        op = (w + C) % 94
        if op == JMP:
            C = mem[D]
        elif op == OUT:
            pass
        elif op == IN:
            A = b if used == 0 else M - 1
            used += 1
        elif op == ROT:
            mem[D] = rotr(mem[D])
            A = mem[D]
        elif op == MOVD:
            D = mem[D]
        elif op == CRZ:
            mem[D] = crazy(A, mem[D])
            A = mem[D]
        elif op == HLT:
            break
        w = mem[C]
        if not 33 <= w <= 126:
            break
        mem[C] = ord(X[w - 33])
        C += 1
        D += 1
    raise RuntimeError(f"b={b}: no dispatch; step={step} A={A} C={C} D={D}")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mat-cand-42.mal"
    destination = sys.argv[2] if len(sys.argv) > 2 else "/tmp/retarget-d42.mal"
    patch(source, destination)
    for b in range(256):
        step, A, C, D, m41, m42, _, m120 = dispatch_state(destination, b)
        q = 9 * (b + 81)
        assert (A, C, D, m41, m42, m120) == (3303, q + 1, 42, q, q, 3303), (
            b, step, A, C, D, m41, m42, m120
        )
    print("verified exact dispatch for all 256 bytes: C=q+1 D=42, m41=m42=q, A=m120=3303")
