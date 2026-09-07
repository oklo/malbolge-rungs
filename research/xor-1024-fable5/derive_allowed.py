"""Derive allowed-v5 bitmasks for k-MOVD return walks to absorbing root 41.

Compact-family geometry: after each pass D sits at win+5; retops are
MOVD x k, NOP (D -> 42), MOVD (D = m[42]+1 = 3b+244 = window start).
A v5 byte is allowed at walk length k iff the D-chain from v5+1 reaches
the absorbing root 41 within k MOVDs while visiting only safe low cells.
Cross-check: k=7 must reproduce astra-xor1024-compact allowed.txt exactly.
"""
import sys, json
from pathlib import Path

AD = Path('research/astra-xor1024-compact-2026-09-06')
base = AD.joinpath('base.mal').read_bytes()
layout = json.loads(AD.joinpath('layout.json').read_text())
OPS = [4, 5, 23, 39, 40, 62, 68, 81]
ROOT = layout['root']            # 41
QREG = layout['q_register']      # 42
# input-dependent after prefix: q register and input copies
UNSAFE = {QREG, 71, 72, 73}

def byte_at(op, addr):
    v = (op - addr) % 94
    while v < 33:
        v += 94
    return v

def absorb_depth(v5, kmax):
    """steps of MOVD (D = m[D]+1) from D0 = v5+1 until D == ROOT; None if not by kmax
    or if the walk touches an unsafe/table/code-designed cell."""
    d = v5 + 1
    for k in range(kmax + 1):
        if d == ROOT:
            return k
        if d in UNSAFE or d >= 128:
            return None
        w = base[d]
        if w < 33 or w > 126:
            return None
        d = w + 1
    return None

def allowed_mask(k):
    out = []
    for res in range(94):
        m = 0
        # representative address with this residue in the table zone
        for j, op in enumerate(OPS):
            # byte value depends only on residue
            v = byte_at(op, res)
            dep = absorb_depth(v, k)
            if dep is not None:
                m |= 1 << j
        out.append(m)
    return out

ref = [int(x) for x in AD.joinpath('allowed.txt').read_text().split()]
mine7 = allowed_mask(7)
diff = [(i, ref[i], mine7[i]) for i in range(94) if ref[i] != mine7[i]]
print('k=7 matches reference:', not diff, f'({len(diff)} diffs)')
if diff:
    print('first diffs:', diff[:10])

for k in (3, 4, 5, 6, 7):
    mk = allowed_mask(k)
    nz = sum(bin(m).count('1') for m in mk)
    empty = sum(1 for m in mk if m == 0)
    Path(f'research/xor-1024-fable5/allowed_k{k}.txt').write_text('\n'.join(str(m) for m in mk) + '\n')
    print(f'k={k}: total choices {nz}/752, residues with zero options: {empty}')
