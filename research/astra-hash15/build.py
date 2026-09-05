"""Build the source-valid triple-spaced dispatcher for the fifteen-row lookup."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.hell_lite.ops import source_byte_for_op, crazy_word, NOP, IN, CRAZY, MOVD, ROT, JUMP

HERE = Path(__file__).resolve().parent
rows = [r for r in json.loads((ROOT/'research/astra-2026-09-05/cases.json').read_text())
        if r['rung'] == 'L4.R1.hash-prefix-1-multicase']
tape = bytearray(source_byte_for_op(NOP, c) for c in range(1024))
tape[0] = 40
for c in range(1, 23):
    tape[c] = source_byte_for_op(IN, c)
for c in [26, 27]:
    tape[c] = source_byte_for_op(CRAZY, c)
tape[66], tape[67], tape[68] = 90, 125, 66
for c in range(28, 47, 2):
    tape[c] = source_byte_for_op(MOVD, c)
for c in range(29, 46, 2):
    tape[c] = source_byte_for_op(ROT, c)
tape[47] = source_byte_for_op(JUMP, 47)
landings = sorted((3*crazy_word(crazy_word(bytes.fromhex(r['input_hex'])[21], 90), 125)+1,
                   bytes.fromhex(r['input_hex'])[21], int(r['expected_hex'], 16)) for r in rows)
lanes = []
for i, (lo, x, y) in enumerate(landings):
    hi = min(lo+24, landings[i+1][0]-1 if i+1<len(landings) else 1024)
    if lo == 52:
        hi = 66  # preserve scratch cells 66..68
    lanes.append((x, y, lo, hi))
(HERE/'direct-base.mal').write_bytes(tape)
(HERE/'direct-lanes.txt').write_text('15\n'+''.join('%d %d %d %d\n'%r for r in lanes))
(HERE/'fixed.json').write_text(json.dumps(list(range(48))+[66,67,68])+'\n')
