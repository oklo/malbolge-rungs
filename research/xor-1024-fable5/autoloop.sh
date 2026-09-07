#!/bin/zsh
# continuous: new distinct 251/252 schedules -> assemble -> repair scan -> log
cd "$(dirname $0)/../.."
LOG=research/xor-1024-fable5/out/autoloop.jsonl
touch $LOG
while true; do
python3 - <<'PY'
import json, subprocess, os
hi='research/xor-1024-fable5/outb/hi.jsonl'
log='research/xor-1024-fable5/out/autoloop.jsonl'
done_keys=set()
for l in open(log):
    try: done_keys.add(tuple(json.loads(l)['masks']))
    except: pass
for l in open(hi):
    d=json.loads(l)
    if d['score']<251: continue
    k=tuple(d['masks'])
    if k in done_keys: continue
    done_keys.add(k)
    m=','.join(map(str,k))
    subprocess.run(['/tmp/b243','0','244','research/astra-xor1024-compact-2026-09-06/allowed.txt',m,'-','research/astra-xor1024-compact-2026-09-06/base.mal','/tmp/auto.mal','research/astra-xor1024-compact-2026-09-06/model-config.txt'],capture_output=True)
    sw=json.loads(subprocess.check_output(['research/xor-1024-fable5/escape2','sweep','/tmp/auto.mal']))
    fixes=[]
    for b in sw['fails']:
        r=subprocess.run(['research/xor-1024-fable5/repair','/tmp/auto.mal',str(b),'1'],capture_output=True,text=True)
        hit=[json.loads(x) for x in r.stdout.splitlines() if x.strip()]
        if hit: fixes.append(hit[0])
    rec={'masks':list(k),'model':sw['score'],'fails':sw['fails'],'repairable':[f['b'] for f in fixes],'fixes':fixes,'total':sw['score']+len(fixes)}
    with open(log,'a') as f: f.write(json.dumps(rec)+'\n')
    if rec['total']>=254:
        with open('research/xor-1024-fable5/out/ALERT.json','a') as f: f.write(json.dumps(rec)+'\n')
PY
sleep 120
done
