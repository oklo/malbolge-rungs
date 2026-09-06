"""Rebuild GPT-6 Astra's 248/256, 1023-byte XOR candidate.

Run from any directory with Python 3 and a C compiler. The Rust VM is the judge.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile

r = Path(__file__).resolve().parent
c = json.loads((r / 'config.json').read_text())
with tempfile.TemporaryDirectory(prefix='astra-xor1024-affine-') as tmp:
    t = Path(tmp)
    for source, executable in [('affine_model.c', 'model'), ('small_router_sls.c', 'router')]:
        subprocess.run(['cc', '-O3', '-I', str(r), str(r / source), '-lm', '-o', str(t / executable)], check=True)
    baseline = t / 'baseline.mal'
    subprocess.run([str(t / 'model'), '0', '82', str(r / 'allowed.txt'),
                    ','.join(map(str, c['masks'])), '-', str(r / 'base.mal'),
                    str(baseline), str(r / 'model-config.txt')], check=True)
    assert hashlib.sha256(baseline.read_bytes()).hexdigest() == c['baseline_sha256']
    output = r / 'reproduced.mal'
    with (t / 'search.jsonl').open('w') as log:
        subprocess.run([str(t / 'router'), str(baseline), str(r / 'router-options.txt'),
                        str(c['rng_seed']), str(c['iterations_per_restart']), str(output),
                        str(r / 'guard.txt'), str(c['lower_limit']), str(c['root']),
                        str(c['depth'])], stdout=log, check=True)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    assert digest == c['program_sha256'], digest
    print(f'Reproduced {len(output.read_bytes())} bytes: {digest}')
