"""Replay the final 250/256 search from its retained 249-case CP witness."""
from pathlib import Path
import hashlib, json, subprocess, tempfile

r=Path(__file__).resolve().parent
c=json.loads((r/'config.json').read_text())
base=(r/'base.mal').read_bytes()
assert hashlib.sha256(base).hexdigest()==c['base_sha256']
def byte(op,address):
    return 33+(op-address-33)%94
baseline=base+bytes(byte(op,len(base)+j) for j,op in enumerate(c['padding_ops']))
assert hashlib.sha256(baseline).hexdigest()==c['baseline_sha256']
with tempfile.TemporaryDirectory(prefix='astra-xor1024-stateful-') as tmp:
    t=Path(tmp)
    subprocess.run(['cc','-O3','-I',str(r),str(r/'small_router_sls.c'),'-lm','-o',str(t/'router')],check=True)
    (t/'baseline.mal').write_bytes(baseline)
    output=r/'reproduced.mal'
    with (t/'search.jsonl').open('w') as f:
        subprocess.run([str(t/'router'),str(t/'baseline.mal'),str(r/'router-options.txt'),
                        str(c['rng_seed']),str(c['iterations_per_restart']),str(output),
                        str(r/'guard.txt'),str(c['lower_limit']),str(c['root']),str(c['depth'])],stdout=f,check=True)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    assert digest==c['program_sha256'],digest
    print(f'Reproduced {len(output.read_bytes())} bytes: {digest}')
