"""Rebuild the successful two-byte lookup from its recorded seed."""
import json
from pathlib import Path
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
subprocess.run([sys.executable,str(HERE/'build.py'),'7'],check=True)
dest=HERE/'reproduce'
dest.mkdir(exist_ok=True)
for name in ['direct-base.mal','direct-lanes.txt','fixed.json','phase.json']:
    (dest/name).write_bytes((HERE/'phase-7'/name).read_bytes())
(dest/'extras.txt').write_text('10 95 109\n13 110 126\n')
subprocess.run([sys.executable,str(HERE/'search.py'),sys.argv[1],str(dest),
                'L5.R1.future-hash-prefix','1','437'],check=True)
program=(dest/'direct-result.mal').read_bytes()[:1463]
(dest/'solution.mal').write_bytes(program)
run=subprocess.run([str(ROOT/'target/release/malbolge-rungs'),'verify','--rung',
                    'L5.R1.future-hash-prefix','--program',str(dest/'solution.mal'),'--json'],
                   check=True,capture_output=True,text=True)
(dest/'verification.json').write_text(run.stdout)
assert json.loads(run.stdout)['all_passed']
print('Native verification passed all twenty cases; rebuilt',len(program),'bytes.')
