"""Probe the single escape from the trit4 impossibility proof.

ceiling.py's proof assumes every tail operand is a printable byte (33..126),
which is true of every cell the two-stage family's tails actually read.  Two
kinds of cell hold NON-printable words at tail time and would supply the
missing trit4 = 2:
  (a) the dispatch operand cells 42..49, overwritten with intermediate
      accumulators;
  (b) memory at index >= len(program), filled by the classic Malbolge
      recurrence mem[i] = crazy(mem[i-1], mem[i-2]).
(a) is reachable: the trail can start at d0 = 49 (p = 47), and a MOVD off a
cell holding the byte 41 sets d = 42.  (b) is reachable from (a): an
intermediate after an odd number of dispatch CRAZYs has trits 6..9 all 1, so
it is ~29160, and MOVD off it throws d out past any program.

This checks whether either actually supplies trit4 = 2 operands.
"""
from __future__ import annotations
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools.hell_lite.ops import crazy_word  # noqa: E402
from research.map12hi import base  # noqa: E402

INPUTS = [0xA5, 0xE0, 0x90, 0x9C, 0x84, 0xA1, 0xBD, 0xC8, 0xBE, 0xF9, 0x86, 0xDD]
base.INPUTS = INPUTS
base.TGT = {x: x ^ 0x51 for x in INPUTS}

print("(a) dispatch intermediates as operands -- trit4 of mem[40+cp] per lane")
for cfg in (0, 7):
    cps, ts, J = base.enum_configs()[cfg]
    print(f"  cfg{cfg} cps={cps} ts={ts}")
    for x in (0x90, 0x9C, 0xF9):
        a, row = x, []
        for cp, t in zip(cps, ts):
            a = crazy_word(a, t)
            row.append(f"mem[{40+cp}]={a} trit4={(a//81)%3}")
        print(f"    {x:#04x}: " + "  ".join(row))

print("\n(b) far memory: classic recurrence mem[i]=crazy(mem[i-1],mem[i-2])")
# the recurrence past the program depends only on the last two program bytes
seen_cycles = {}
for u in (33, 60, 94, 126):
    for v in (33, 60, 94, 126):
        m = [u, v]
        for _ in range(400):
            m.append(crazy_word(m[-1], m[-2]))
        tail = tuple(m[-8:])
        seen_cycles.setdefault(tail, []).append((u, v))
for tail, seeds in seen_cycles.items():
    t4 = sorted({(w // 81) % 3 for w in tail})
    print(f"  limit cycle {tail[:4]}... trit4 values present={t4}  from seeds {seeds[:3]}")
