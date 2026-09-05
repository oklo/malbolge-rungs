"""Reproducible random constant pools plus bounded independent native-style DFS.

cc -O3 research/astra-2026-09-05/private.c -o /tmp/astra-private
python3 research/astra-2026-09-05/direct_search.py /tmp/astra-private
"""
import json
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.hell_lite.ops import source_valid_bytes

HERE = Path(__file__).resolve().parent
solver = sys.argv[1]
if len(sys.argv) > 2:
    HERE = Path(sys.argv[2]).resolve()
RUNG = sys.argv[3] if len(sys.argv) > 3 else 'L4.R1.hash-prefix-1-multicase'
base = (HERE / 'direct-base.mal').read_bytes()
lanes = HERE / 'direct-lanes.txt'
fixed = set(range(12)) | {44, 49, 50}
if (HERE / 'fixed.json').exists():
    fixed = set(json.loads((HERE / 'fixed.json').read_text()))
blocks = [tuple(map(int, line.split())) for line in lanes.read_text().splitlines()[1:]]
for _, _, lo, hi in blocks:
    fixed.update(range(lo, hi))
best = -1
start = time.monotonic()
with (HERE / 'direct-search.jsonl').open('w', buffering=1) as log:
    for trial in range(1000):
        rng = random.Random(600000 + trial)
        tape = bytearray(base)
        for c in range(12, len(tape)):
            if c not in fixed:
                tape[c] = rng.choice(source_valid_bytes(c))
        (HERE / 'direct-trial.mal').write_bytes(tape)
        run = subprocess.run([solver, str(HERE/'direct-trial.mal'), str(lanes),
                              str(HERE/'direct-result.mal'), '300000'], capture_output=True, text=True)
        score = run.stdout.count('found=1')
        event = dict(trial=trial, seed=600000+trial, diagnostic_correct=score,
                     elapsed_seconds=round(time.monotonic()-start,3), exit_code=run.returncode,
                     solver_stdout=run.stdout)
        log.write(json.dumps(event)+'\n')
        if score > best:
            best = score
            dest = HERE / f'direct-best-{score}.mal'
            dest.write_bytes((HERE/'direct-result.mal').read_bytes())
            native = subprocess.run([str(ROOT/'target/release/malbolge-rungs'), 'verify',
                                     '--rung', RUNG, '--program', str(dest), '--json'],
                                    capture_output=True, text=True)
            (HERE/f'direct-best-{score}-verify.json').write_text(native.stdout)
            print(json.dumps(dict(trial=trial, diagnostic_correct=score, native_exit=native.returncode)), flush=True)
            if native.returncode == 0:
                break
        if trial % 100 == 0:
            print(json.dumps(dict(trial=trial, best=best)), flush=True)
