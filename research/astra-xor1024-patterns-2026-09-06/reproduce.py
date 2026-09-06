"""Reconstruct the retained 251-case witness, or rerun finite-archive CP-SAT search.
Default needs only Python's standard library. --search additionally needs OR-Tools.
The search may produce different source bytes; the native verifier checks coverage.
"""
from pathlib import Path
import argparse,base64,hashlib,json,os,subprocess,zlib
r=Path(__file__).resolve().parent;c=json.loads((r/'config.json').read_text())
ap=argparse.ArgumentParser();ap.add_argument('--search',action='store_true');args=ap.parse_args()
p=bytearray((r/'base.mal').read_bytes());assert hashlib.sha256(p).hexdigest()==c['base_sha256']
for a,v in c['source_patch']:p[a]=v
assert hashlib.sha256(p).hexdigest()==c['program_sha256']
rows=[list(map(int,l.split())) for l in (r/'router-input.txt').read_text().splitlines()];free={a for a,(_,_,f) in enumerate(rows) if f}
assert all(a in free for a,v in c['source_patch'])
raw=zlib.decompress(base64.b64decode((r/'patterns.zlib.b64').read_bytes()));assert hashlib.sha256(raw).hexdigest()==c['archive_sha256']
groups=[set() for _ in range(16)];i=0
while i<len(raw):
 b,n=raw[i:i+2];i+=2;data=raw[i:i+2*n];i+=2*n;groups[b].add(tuple(zip(data[::2],data[1::2])))
for b,pattern in c['selected_sufficient_patterns'].items():
 assert tuple(map(tuple,pattern)) in groups[int(b)] and all(p[a]==v for a,v in pattern)
ops=[4,5,23,39,40,62,68,81]
def byte(op,a):return 33+(op-a-33)%94
if args.search:
 from ortools.sat.python import cp_model
 model=cp_model.CpModel();choices={a:model.new_int_var(0,7,f'choice_{a}') for a in free};values={};eq={}
 for a in free:
  values[a]=model.new_int_var(33,126,f'byte_{a}');model.add_element(choices[a],[byte(op,a) for op in ops],values[a]);model.add_hint(choices[a],ops.index((p[a]+a)%94));model.add_hint(values[a],p[a])
  for j,op in enumerate(ops):
   e=model.new_bool_var(f'eq_{a}_{j}');model.add(choices[a]==j).only_enforce_if(e);model.add(choices[a]!=j).only_enforce_if(e.Not());eq[a,byte(op,a)]=e
 post=[values[a]+1 if a in free else rows[a][1]+1 for a in range(128)]
 for leaf in sorted({p[87+3*b]+1 for b in range(16,256)}):
  a=model.new_int_var(0,127,f'route_{leaf}_0');model.add(a==leaf)
  for k in range(c['layout']['depth']):
   nxt=model.new_int_var(0,127,f'route_{leaf}_{k+1}');model.add_element(a,post,nxt);a=nxt
  model.add(a==c['layout']['root'])
 correct=[]
 for b,group in enumerate(groups):
  ok=model.new_bool_var(f'correct_{b}');correct.append(ok);takes=[];sets=[]
  for pattern in sorted(group,key=lambda x:(len(x),x)):
   st=frozenset(pattern)
   if any(prev.issubset(st) for prev in sets):continue
   sets.append(st);take=model.new_bool_var(f'pattern_{b}_{len(takes)}');takes.append(take);model.add_bool_and([eq[a,v] for a,v in pattern]).only_enforce_if(take);model.add_implication(take,ok)
  model.add_bool_or(takes).only_enforce_if(ok);model.add_hint(ok,int(str(b) in c['selected_sufficient_patterns']))
 model.maximize(sum(correct));solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=180;solver.parameters.num_search_workers=1;solver.parameters.random_seed=600672
 status=solver.solve(model);print(solver.status_name(status),solver.objective_value,flush=True)
 assert status in [cp_model.FEASIBLE,cp_model.OPTIMAL] and solver.objective_value>=11
 for a,v in choices.items():p[a]=byte(ops[solver.value(v)],a)
path=r/('searched.mal' if args.search else 'reproduced.mal');path.write_bytes(p)
print('Reconstructed',len(p),'bytes',hashlib.sha256(p).hexdigest(),flush=True)
repo=r.parent.parent;env=dict(os.environ,MALBOLGE_RUNGS_TRACE_DIR=str(r/'reproduction-trace'))
v=subprocess.run([str(repo/'target/release/malbolge-rungs'),'verify','--rung','L2.X1024.xor-1-len1024','--program',str(path),'--json'],capture_output=True,text=True,env=env)
x=json.loads(v.stdout);epochs=x['results'][0]['outcome']['epochs'];score=sum(e['passed'] for e in epochs)
(r/('search-native.json' if args.search else 'reproduction-native.json')).write_text(v.stdout)
assert score>=251;print('Native coverage',score,'/ 256')
