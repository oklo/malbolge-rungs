"""Rebuild GPT-6 Astra's 228/256, 982-byte XOR candidate; native verifier is judge."""
from pathlib import Path
import tempfile,subprocess,json,hashlib
print('Replaying the historical search; see guard-audit.json. Native verification remains required.')
r=Path(__file__).resolve().parent;c=json.loads((r/'config.json').read_text())
with tempfile.TemporaryDirectory(prefix='astra-xor1024-') as tmp:
 t=Path(tmp)
 for source,exe in [('table_model.c','model'),('router_search.c','router')]:
  subprocess.run(['cc','-O3','-I',str(r),str(r/source),'-lm','-o',str(t/exe)],check=True)
 baseline=t/'baseline.mal'
 subprocess.run([str(t/'model'),'10','1',str(r/'allowed.txt'),','.join(map(str,c['masks'])),'-',str(r/'base.mal'),str(baseline)],check=True)
 assert hashlib.sha256(baseline.read_bytes()).hexdigest()==c['baseline_sha256']
 out=r/'reproduced.mal'
 with (t/'search.jsonl').open('w') as log:
  subprocess.run([str(t/'router'),str(baseline),str(r/'router-options.txt'),str(c['rng_seed']),str(c['iterations_per_restart']),str(out),str(r/'guard.txt')],stdout=log,check=True)
 digest=hashlib.sha256(out.read_bytes()).hexdigest();assert digest==c['program_sha256'],digest
 print(f'Reproduced {len(out.read_bytes())} bytes: {digest}')
