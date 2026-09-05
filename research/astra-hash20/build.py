"""Ninefold-spaced public twenty-row/two-output-byte dispatcher."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.hell_lite.ops import *
HERE=Path(__file__).resolve().parent
phase=int(sys.argv[1]) if len(sys.argv)>1 else -1
if phase>=0:
    HERE=HERE/f'phase-{phase}'
    HERE.mkdir(exist_ok=True)
rows=[r for r in json.loads((ROOT/'research/astra-2026-09-05/cases.json').read_text()) if r['rung']=='L5.R1.future-hash-prefix']
key,pos,end,t,u=18,26,27,67,67
p=bytearray(source_byte_for_op(NOP,c) for c in range(2048));p[0]=40
for c in range(1,key+2):p[c]=source_byte_for_op(IN,c)
for c in [pos,end]:p[c]=source_byte_for_op(CRAZY,c)
p[40+pos],p[40+end],p[41+end]=t,u,39+end
for c in range(end+1,end+18,2):p[c]=source_byte_for_op(MOVD,c)
for c in range(end+2,end+17,2):p[c]=source_byte_for_op(ROT,c)
p[end+18]=source_byte_for_op(JUMP,end+18)
fixed=list(range(end+19))+[40+pos,40+end,41+end]
if phase>=0:
    seed=source_valid_bytes(69)[phase]
    for c in range(44,60):p[c]=source_byte_for_op(NOP,c)
    p[45]=source_byte_for_op(ROT,45)
    p[60]=source_byte_for_op(MOVD,60)
    p[61]=source_byte_for_op(MOVD,61)
    p[62]=source_byte_for_op(JUMP,62)
    p[69],p[84],p[109]=seed,108,66
    fixed=list(range(63))+[66,67,68,69,84,109]
    (HERE/'phase.json').write_text(json.dumps(dict(phase=phase,seed=seed,accumulator=rotate_right_word(seed)))+'\n')
ordered=sorted((9*crazy_word(crazy_word(bytes.fromhex(r['input_hex'])[key],t),u)+1,
                bytes.fromhex(r['input_hex'])[key],int.from_bytes(bytes.fromhex(r['expected_hex']),'little')) for r in rows)
lanes=[]
for i,(lo,x,y) in enumerate(ordered):
    hi=min(lo+40,ordered[i+1][0] if i+1<len(ordered) else 2048)
    lanes.append((x,y,lo,hi))
(HERE/'direct-base.mal').write_bytes(p)
(HERE/'direct-lanes.txt').write_text('20\n'+''.join('%d %d %d %d\n'%r for r in lanes))
(HERE/'fixed.json').write_text(json.dumps(fixed)+'\n')
