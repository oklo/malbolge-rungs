"""Recompute the exact best table for the retained mask schedule and return graph.
This repeats the final finite optimization, not the evolutionary schedule search.
Run from the repository root after cargo build --release.
"""
from pathlib import Path
import hashlib, json, subprocess, tempfile

r = Path(__file__).resolve().parent
c = json.loads((r / 'config.json').read_text())
assert hashlib.sha256((r / 'base.mal').read_bytes()).hexdigest() == c['base_sha256']
with tempfile.TemporaryDirectory(prefix='astra-xor1024-compact-') as tmp:
    t = Path(tmp)
    subprocess.run(['cc', '-O3', str(r / 'biased243_model.c'), '-o', str(t / 'model')], check=True)
    result = json.loads(subprocess.check_output([
        str(t / 'model'), '0', '244', str(r / 'allowed.txt'),
        ','.join(map(str, c['masks'])), '-', str(r / 'base.mal'),
        str(t / 'candidate.mal'), str(r / 'model-config.txt')]))
    program = (t / 'candidate.mal').read_bytes()
    assert len(program) == c['source_bytes']
    assert hashlib.sha256(program).hexdigest() == c['program_sha256']
    assert result['single_read_score'] == c['correct_cases']
    native = subprocess.run([
        './target/release/malbolge-rungs', 'verify', '--rung',
        'L2.X1024.xor-1-len1024', '--program', str(t / 'candidate.mal'),
        '--json'], capture_output=True, text=True)
    report = json.loads(native.stdout)
    epochs = report['results'][0]['outcome']['epochs']
    assert sum(e['correct_cases'] for e in epochs) == c['correct_cases']
    assert sum(e['total_cases'] for e in epochs) == c['total_cases']
    assert [e['epoch'] for e in epochs if not e['passed']] == c['failed_inputs']
    print(json.dumps(dict(sha256=c['program_sha256'], bytes=len(program),
                          native_correct=c['correct_cases'], total=c['total_cases'])))
