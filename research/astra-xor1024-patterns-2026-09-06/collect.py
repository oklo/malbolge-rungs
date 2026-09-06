"""Regenerate the twelve diagnostic pattern captures from the retained 250-case base.
C search output is diagnostic; this controller natively verifies each retained candidate.
It does not overwrite the frozen archive distributed with this attempt.
"""
from pathlib import Path
import json,subprocess,tempfile,os
r=Path(__file__).resolve().parent;c=json.loads((r/'config.json').read_text());repo=r.parent.parent
root=r/'regenerated';root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='astra-pattern-') as tmp:
 binary=Path(tmp)/'router';subprocess.run(['cc','-O3','-I',str(r),str(r/'pattern_router_sls.c'),'-lm','-o',str(binary)],check=True)
 for i,b in enumerate(c['search']['targets']):
  out=root/f'trial-{i:02d}-input-{b}';out.mkdir(exist_ok=True);candidate=out/'best.mal'
  with (out/'search.jsonl').open('w') as f:
   subprocess.run([str(binary),str(r/'base.mal'),str(r/'router-options.txt'),str(c['search']['seed_start']+i),str(c['search']['iterations_per_restart']),str(candidate),str(r/'guard.txt'),'16',str(c['layout']['root']),str(c['layout']['depth']),str(b),str(out/'patterns.bin')],stdout=f,check=True)
  if not candidate.exists():candidate.write_bytes((r/'base.mal').read_bytes())
  env=dict(os.environ,MALBOLGE_RUNGS_TRACE_DIR=str(out/'native-trace'))
  v=subprocess.run([str(repo/'target/release/malbolge-rungs'),'verify','--rung','L2.X1024.xor-1-len1024','--program',str(candidate),'--json'],capture_output=True,text=True,env=env)
  (out/'native.json').write_text(v.stdout);epochs=json.loads(v.stdout)['results'][0]['outcome']['epochs'];assert all(e['passed'] for e in epochs[16:]);print(i,b,sum(e['passed'] for e in epochs),flush=True)
