"""Search direct two-CRAZY dispatchers under the actual 256-byte cap."""
import json
from pathlib import Path
import random
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.hell_lite.ops import *
HERE = Path(__file__).resolve().parent
RUNG = 'L4.R2.hash-prefix-length-pressure'
rows = [r for r in json.loads((ROOT/'research/astra-2026-09-05/cases.json').read_text()) if r['rung']==RUNG]
configs = []
for key in range(32):
    xs = [bytes.fromhex(r['input_hex'])[key] for r in rows]
    if len(set(xs)) < len(rows):
        continue
    for end in [9, 27, 38, 41]:
        for pos in range(key+2, end):
            for t in source_valid_bytes(40+pos):
                for u in source_valid_bytes(40+end):
                    js = [crazy_word(crazy_word(x,t),u) for x in xs]
                    vs = sorted(js)
                    if len(set(vs)) < len(rows) or vs[0] <= end+2 or vs[-1] > 242:
                        continue
                    gap = min(b-a for a,b in zip(vs,vs[1:]))
                    if gap < 5:
                        continue
                    configs.append((gap, key, pos, end, t, u, js))
configs.sort(key=lambda c: (-c[0], c[1], c[3], c[2], c[4], c[5]))
print('configurations', len(configs), flush=True)
best = -1
start = time.monotonic()
with (HERE/'search.jsonl').open('w', buffering=1) as log:
    for ci, (gap,key,pos,end,t,u,js) in enumerate(configs):
        if time.monotonic()-start > 900:
            break
        tape = bytearray(source_byte_for_op(NOP,c) for c in range(256))
        tape[0] = 40
        for c in range(1,key+2):
            tape[c] = source_byte_for_op(IN,c)
        for c in [pos,end]:
            tape[c] = source_byte_for_op(CRAZY,c)
        tape[end+1] = source_byte_for_op(MOVD,end+1)
        tape[end+2] = source_byte_for_op(JUMP,end+2)
        tape[40+pos],tape[40+end],tape[41+end] = t,u,39+end
        fixed = set(range(end+3)) | {40+pos,40+end,41+end}
        ordered = sorted((j+1,bytes.fromhex(r['input_hex'])[key],int(r['expected_hex'],16)) for j,r in zip(js,rows))
        lanes=[]
        for i,(lo,x,y) in enumerate(ordered):
            hi=min(lo+24,ordered[i+1][0] if i+1<len(ordered) else 256)
            for c in fixed:
                if lo <= c < hi:
                    hi=c
            lanes.append((x,y,lo,hi))
        if min(hi-lo for _,_,lo,hi in lanes) < 4:
            continue
        (HERE/'lanes.txt').write_text('10\n'+''.join('%d %d %d %d\n'%r for r in lanes))
        extras=[]
        if key==27 and pos==30 and end==38:
            extras=[(2,41,45),(2,147,169),(2,237,256)]
        (HERE/'extras.txt').write_text(''.join('%d %d %d\n'%r for r in extras))
        for _,_,lo,hi in lanes:
            fixed.update(range(lo,hi))
        for _,lo,hi in extras:
            fixed.update(range(lo,hi))
        for trial in range(500 if extras else 20):
            rng=random.Random(610000+20*ci+trial)
            p=bytearray(tape)
            for c in range(256):
                if c not in fixed:
                    p[c]=rng.choice(source_valid_bytes(c))
            (HERE/'base.mal').write_bytes(p)
            run=subprocess.run([sys.argv[1],str(HERE/'base.mal'),str(HERE/'lanes.txt'),str(HERE/'candidate.mal'),'300000',str(HERE/'extras.txt')],capture_output=True,text=True)
            score=run.stdout.count('found=1')
            event=dict(config=ci,gap=gap,key=key,pos=pos,end=end,operands=[t,u],landings=js,
                       seed=610000+20*ci+trial,diagnostic_correct=score,solver_stdout=run.stdout,
                       elapsed_seconds=round(time.monotonic()-start,3))
            log.write(json.dumps(event)+'\n')
            if score>best:
                best=score
                dest=HERE/f'best-{score}.mal'
                dest.write_bytes((HERE/'candidate.mal').read_bytes())
                (HERE/f'best-{score}-construction.json').write_text(json.dumps(event,indent=2)+'\n')
                native=subprocess.run([str(ROOT/'target/release/malbolge-rungs'),'verify','--rung',RUNG,'--program',str(dest),'--json'],capture_output=True,text=True)
                (HERE/f'best-{score}-verify.json').write_text(native.stdout)
                print(json.dumps(dict(config=ci,trial=trial,diagnostic_correct=score,native_exit=native.returncode)),flush=True)
                if native.returncode==0:
                    raise SystemExit(0)
        if ci % 10 == 0:
            print(json.dumps(dict(config=ci,best=best)),flush=True)
