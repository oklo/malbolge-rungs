"""Reproduce the exact GPT-6 Astra 2028-byte XOR solution; Python 3 + C compiler.
The frozen prefix/router is loader-legal source, not executable host code.
The C optimizer constructs the overlapping data table from the XOR contract.
"""
from pathlib import Path
import hashlib,json,subprocess,tempfile
r=Path(__file__).resolve().parent
manifest=json.loads((r/'manifest.json').read_text());cfg=json.loads((r/'config.json').read_text())
def bf(op,addr):
 x=(op-addr)%94
 return x+94 if x<33 else x
with tempfile.TemporaryDirectory(prefix='astra-xor2048-') as temp:
 tmp=Path(temp);binary=tmp/'table-dp';table=tmp/'table.bin'
 subprocess.run(['cc','-O3',str(r/'tail2_table_dp.c'),'-o',str(binary)],check=True)
 result=json.loads(subprocess.check_output([str(binary),'10','124',str(r/'allowed.txt'),','.join(map(str,manifest['masks'])),str(table)]))
 assert result['joint_score']==256,result
 layout=json.loads((r/'layout.json').read_text());p=bytearray(bf(68,a) for a in range(2048))
 for a,v in layout['initial_low_cells'].items():p[int(a)]=v
 for a,op in enumerate(layout['bootstrap_ops']):p[a]=bf(op,a)
 for i,op in enumerate(layout['main_ops']):a=layout['main_start']+i;p[a]=bf(op,a)
 assert p==(r/'dispatcher.mal').read_bytes()
 p[124:896]=table.read_bytes();ops=[68]*123
 for index,mask in enumerate(manifest['masks']):
  if index:ops+=cfg['return_ops']
  ops += [39 if mask&(1<<j) else 62 for j in range(5)]
 ops += [62,62,5,81];end=cfg['core_start']+len(ops)
 for i,op in enumerate(ops):p[cfg['core_start']+i]=bf(op,cfg['core_start']+i)
 result_bytes=bytes(p[:end]);digest=hashlib.sha256(result_bytes).hexdigest()
 assert digest==manifest['program_sha256'],digest
 output=r/'reproduced.mal';output.write_bytes(result_bytes)
 print(json.dumps({'program':str(output),'bytes':len(result_bytes),'sha256':digest,'diagnostic_correct':256,'native_verification':'Run the repository verify command on reproduced.mal.'}))
