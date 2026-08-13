#!/usr/bin/env python3
"""Build the first exact safe-dispatch prototype for XOR-256.

The prologue maps a byte b to q = 9*(b+81), then jumps to q.  Consequently
the 256 private blocks q+1..q+9 occupy addresses 730..3033 and never alias the
low-memory initializer.  The map is a six-CRAZY ternary circuit with one
rotated copy carrying the trit-6 overflow into trit 7.

This file deliberately contains a tiny raw-Malbolge micro-assembler.  The C
tape starts at 127 after a four-instruction bootstrap; scratch data stays in
33..125.  MOVD routes are synthesized over loader-legal printable cells.
"""
from collections import deque
from pathlib import Path

OPS = (4, 5, 23, 39, 40, 62, 68, 81)
JMP, OUT, IN, ROT, MOVD, CRZ, NOP, HLT = OPS
N = 4096
CODE0 = 127


def byte_for(op, addr):
    v = (op - addr) % 94
    while v < 33:
        v += 94
    assert v <= 126
    return v


def legal(v, addr):
    return 33 <= v <= 126 and (v + addr) % 94 in OPS


initial = {}
fixed_reason = {}
modified = set()
code = []


def set_initial(addr, value, reason):
    assert 33 <= addr <= 125, (addr, reason)
    assert legal(value, addr), (addr, value, reason, (addr + value) % 94)
    if addr in initial and initial[addr] != value:
        raise ValueError(f"cell {addr}: {initial[addr]} vs {value} ({reason})")
    initial[addr] = value
    fixed_reason.setdefault(addr, reason)


# Constant manufacture and input-copy seeds.
seeds = {
    35: (121, "K2 accumulator seed; rotate 8 -> 1089"),
    76: (80, "K1; rotate 2 -> 52496"),
    82: (80, "K1 copy; then crazy into K2=54683"),
    88: (45, "K3; rotate 6 -> 3645"),
    93: (40, "K4 accumulator seed; rotate 2 -> 26248"),
    41: (40, "K4 destination; crazy -> 3276; final q lives here"),
    54: (121, "input copy pair 1a"),
    72: (121, "input copy Y"),
    71: (121, "input copy pair 2a"),
    90: (121, "input copy X0"),
    106: (121, "input copy pair 3a"),
    107: (121, "input copy X1"),
}
for a, (v, why) in seeds.items():
    set_initial(a, v, why)
reserved = set(seeds)
exit_used = set()
loop_nodes = {36, 73, 77, 83, 89, 91, 94, 108}


def emit(op):
    code.append(op)


def choices(addr, route_start):
    """MOVD successors available from an as-yet-static data cell."""
    if not (33 <= addr <= 125):
        return []
    if (addr in modified or addr in reserved or
            (addr in exit_used and addr != route_start) or
            (addr in loop_nodes and addr != route_start)):
        return []
    if addr in initial:
        return [(initial[addr] + 1, initial[addr])]
    return [(v + 1, v) for v in range(33, 127) if legal(v, addr)]


def route(start, target):
    """Emit MOVDs and assign a legal pointer path start -> target."""
    def find_path(source):
        if source == target:
            return []
        q = deque([source])
        prev = {source: None}
        edge_value = {}
        while q:
            a = q.popleft()
            for nxt, value in choices(a, source):
                if not (33 <= nxt <= 126) or nxt in prev:
                    continue
                prev[nxt] = a
                edge_value[nxt] = value
                if nxt == target:
                    q.clear()
                    break
                q.append(nxt)
        if target not in prev:
            return None
        path = []
        z = target
        while z != source:
            a = prev[z]
            path.append((a, edge_value[z], z))
            z = a
        return path[::-1]

    if isinstance(start, tuple):
        base = start[1]
        if target >= base:
            for _ in range(target - base):
                emit(NOP)
            return target
        # A phase exit is not committed until its destination is known.  Pick
        # a forward cell whose loader-legal byte points directly to target;
        # this turns nearly every inter-register route into one MOVD.
        for s in range(base, 126):
            if (s not in initial and s not in reserved and s not in modified and
                    s not in exit_used and s not in loop_nodes and legal(target - 1, s)):
                for _ in range(s - base):
                    emit(NOP)
                set_initial(s, target - 1, f"direct phase route {base}->{target}")
                exit_used.add(s)
                emit(MOVD)
                return target
        best = None
        for s in range(base, 126):
            if s in initial or s in reserved or s in modified or s in exit_used or s in loop_nodes:
                continue
            p = find_path(s)
            if p is not None and (best is None or (s - base) + len(p) < best[0]):
                best = ((s - base) + len(p), s, p)
        if best is None:
            print("phase route failure assignments:", sorted(initial.items()))
            print("modified:", sorted(modified), "exits:", sorted(exit_used))
            raise RuntimeError(f"no phase route {base}->{target}")
        _, s, path = best
        for _ in range(s - base):
            emit(NOP)
        exit_used.add(s)
        for a, value, _ in path:
            set_initial(a, value, f"pointer on phase route {base}->{target}")
            emit(MOVD)
        return target
    if start == target:
        return target
    path = find_path(start)
    if path is None:
        print("route failure assignments:", sorted(initial.items()))
        print("modified:", sorted(modified))
        raise RuntimeError(f"no static MOVD route {start}->{target}")
    for a, value, _ in path:
        set_initial(a, value, f"pointer on route {start}->{target}")
        emit(MOVD)
    return target


def phase_exit(addr):
    """Defer a NOP phase exit until the next route target is known."""
    return ("phase", addr + 1)


def advance_fresh(d):
    """Defer a NOP phase exit after an instruction that did not read D."""
    return ("phase", d)


def rotate_register(d, addr, count):
    d = route(d, addr)
    for i in range(count):
        emit(ROT)
        modified.add(addr)
        d = addr + 1
        if i + 1 < count:
            d = route(d, addr)
    # Skip the loop pointer on the final iteration.  Repeated uses of the same
    # register get different exit cells, avoiding an impossible fixed-pointer
    # phase conflict.
    return phase_exit(addr)


def crazy_register(d, addr):
    d = route(d, addr)
    emit(CRZ)
    modified.add(addr)
    return phase_exit(addr)


# Five-instruction bootstrap: C=127 without executing scratch cells 33..125.
# A leading NOP and MOVD leave D=40.  Two more MOVDs follow 40->78->85,
# then JMP reads m[85]=126.  The dispatch
# target is enciphered and incremented, so the main code begins at 127.
bootstrap_ops = [NOP, MOVD, MOVD, MOVD, JMP]
for a, v, nxt in [(40,77,78),(78,84,85),(85,126,127)]:
    set_initial(a, v, f"bootstrap pointer {a}->{nxt}")

# The bootstrap leaves D=86.
d = 86

# Manufacture K1, K2, K3, K4.
d = rotate_register(d, 76, 2)
d = rotate_register(d, 82, 2)
d = rotate_register(d, 35, 8)
d = crazy_register(d, 82)       # crazy(1089, 52496) = 54683
d = rotate_register(d, 88, 6)
d = rotate_register(d, 93, 2)
d = crazy_register(d, 41)       # crazy(26248, 40) = 3276

# Read and make three persistent copies.  Each two-CRAZY 121 pair is identity
# on byte inputs; the second operand becomes the copy and A returns to b.
emit(IN)
if isinstance(d, tuple):
    d = ("phase", d[1] + 1)
else:
    d += 1
d = advance_fresh(d[1] if isinstance(d, tuple) else d)
d = crazy_register(d, 54)
d = crazy_register(d, 72)       # Y copy
d = crazy_register(d, 71)
d = crazy_register(d, 90)       # X0 copy
d = crazy_register(d, 106)
d = crazy_register(d, 107)      # X1 copy

# y = 27*b (left three ternary places), x = 9*b (left two places).
d = rotate_register(d, 72, 7)
d = rotate_register(d, 90, 8)
d = rotate_register(d, 107, 8)  # leaves A=x

# Six-gate circuit:
#   a=C(x,K1); b=C(y,K2); c=C(b,K3); d=C(a,c); e=C(d,x); q=C(e,K4)
# Constants choose identity, increment, carry, or zero independently by trit.
d = crazy_register(d, 76)       # a, stored at 76
d = rotate_register(d, 72, 10) # load y without changing it
d = crazy_register(d, 82)       # b
d = crazy_register(d, 88)       # c
d = rotate_register(d, 76, 10) # load a
d = crazy_register(d, 88)       # d
d = crazy_register(d, 90)       # e
d = crazy_register(d, 41)       # q = 9*(b+81), stored at 41
d = route(d, 41)
emit(JMP)


def build(path):
    prog = bytearray(byte_for(NOP, a) for a in range(N))
    for a, op in enumerate(bootstrap_ops):
        prog[a] = byte_for(op, a)
    for a, value in initial.items():
        prog[a] = value
    if CODE0 + len(code) >= 729:
        raise ValueError(f"microcode reaches {CODE0 + len(code)}")
    for i, op in enumerate(code):
        prog[CODE0 + i] = byte_for(op, CODE0 + i)
    # q itself is enciphered by the dispatch JMP.  q+1..q+9 initially NOP;
    # the block synthesizer replaces them in the next stage.
    for a, v in enumerate(prog):
        assert 33 <= v <= 126 and (v + a) % 94 in OPS, (a, v)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(prog)
    print(f"wrote {path}: length={len(prog)} main_code={len(code)} C={CODE0}..{CODE0+len(code)-1} final_D={d}")
    print("initial data:")
    for a in sorted(initial):
        print(f"  {a:3d}={initial[a]:3d}  {fixed_reason[a]}")


if __name__ == "__main__":
    build("research/xor-1-len4096-profound/runs-shifted-dispatch-nop.mal")
