#!/bin/zsh
# harvest distinct >=SCORE schedules from a hi.jsonl, assemble, model-sweep, list failure sets
cd "$(dirname $0)/../.."
HI=$1; MIN=${2:-252}
python3 - "$HI" "$MIN" <<'PY'
import json, subprocess, sys, hashlib
hi, mn = sys.argv[1], int(sys.argv[2])
seen = set()
for line in open(hi):
    d = json.loads(line)
    if d['score'] < mn: continue
    key = tuple(d['masks'])
    if key in seen: continue
    seen.add(key)
    m = ','.join(map(str, key))
    out = subprocess.check_output(['/tmp/b243','0','244',
        'research/astra-xor1024-compact-2026-09-06/allowed.txt', m, '-',
        'research/astra-xor1024-compact-2026-09-06/base.mal','/tmp/h.mal',
        'research/astra-xor1024-compact-2026-09-06/model-config.txt'])
    js = json.loads(out)
    sw = json.loads(subprocess.check_output(['research/xor-1024-fable5/escape2','sweep','/tmp/h.mal']))
    print(json.dumps({'masks': list(key), 'dp': js['upper_score'], 'model': sw['score'], 'fails': sw['fails']}))
PY
