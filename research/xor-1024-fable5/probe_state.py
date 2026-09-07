"""Capture the true post-prefix low-memory state at the first return boundary,
then re-derive allowed_k empirically and cross-check against allowed.txt (k=7).
"""
import json
from pathlib import Path

AD = Path('research/astra-xor1024-compact-2026-09-06')
prog = AD.joinpath('candidate.mal').read_bytes()
layout = json.loads(AD.joinpath('layout.json').read_text())
ROOT, CORE = layout['root'], layout['core_start']
ENC = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CT = [[1,0,0],[1,0,2],[2,2,1]]

def cv(a, d):
    v, p = 0, 1
    for _ in range(10):
        v += CT[d % 3][a % 3] * p
        a //= 3; d //= 3; p *= 3
    return v

def rot(a):
    return a // 3 + a % 3 * 19683

def run_capture(b, capture_c):
    m = list(prog) + [0] * (59049 - len(prog))
    for i in range(len(prog), 59049):
        m[i] = cv(m[i - 1], m[i - 2])
    a = c = d = 0
    reads = 0
    for step in range(2048):
        if c == capture_c:
            return m[:], step, (a, c, d)
        w = m[c]
        if w < 33 or w > 126:
            return None, step, None
        op = (w + c) % 94
        if op == 81:
            return None, step, None
        if op == 4:
            c = m[d]
        elif op == 5:
            pass
        elif op == 23:
            a = b; reads += 1
        elif op == 39:
            a = m[d] = rot(m[d])
        elif op == 40:
            d = m[d]
        elif op == 62:
            a = m[d] = cv(a, m[d])
        if m[c] < 33 or m[c] > 126:
            return None, step, None
        m[c] = ord(ENC[m[c] - 33])
        c = (c + 1) % 59049
        d = (d + 1) % 59049
    return None, -1, None

# first return boundary: C at core + 5 (retops[0] of the pass-0 -> pass-1 gap)
CAP = CORE + 5
snap100, st100, regs100 = run_capture(100, CAP)
snap200, st200, regs200 = run_capture(200, CAP)
print('captured at step', st100, 'regs', regs100, '| step', st200, 'regs', regs200)

# cells whose values differ between inputs are input-dependent: exclude from routes
input_dep = {i for i in range(244) if snap100[i] != snap200[i]}
changed = {i for i in range(244) if snap100[i] != (prog[i] if i < len(prog) else 0)}
print('input-dependent low cells:', sorted(i for i in input_dep if i < 134))
print('changed-from-file low cells (<134):', sorted(i for i in changed if i < 134))

OPS = [4, 5, 23, 39, 40, 62, 68, 81]

def byte_at(op, addr):
    v = (op - addr) % 94
    while v < 33:
        v += 94
    return v

def absorb(v5, k, mem, dep_ok=frozenset()):
    d = v5 + 1
    for i in range(k + 1):
        if d == ROOT:
            return True
        if d >= 244 or (d in input_dep and d not in dep_ok):
            return False
        w = mem[d]
        if w < 33 or w > 126:
            return False
        d = w + 1
    return False

def allowed_mask(k, mem):
    out = []
    for res in range(94):
        mask = 0
        for j, op in enumerate(OPS):
            if absorb(byte_at(op, res), k, mem):
                mask |= 1 << j
        out.append(mask)
    return out

ref = [int(x) for x in AD.joinpath('allowed.txt').read_text().split()]
for k in (7,):
    mine = allowed_mask(k, snap100)
    diffs = [(i, ref[i], mine[i]) for i in range(94) if ref[i] != mine[i]]
    print(f'k={k}: matches reference: {not diffs} ({len(diffs)} diffs)')
    if diffs:
        print('sample diffs (residue, ref, mine):', diffs[:8])
