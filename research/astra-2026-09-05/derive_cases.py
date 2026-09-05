"""Reproduce public hash-prefix cases using the pinned bincode/SHA-256 encoding."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]

def digest(domain, value):
    return hashlib.sha256((domain.encode() + b'\0') * 2 + value).digest()

def derive(rung):
    rows = []
    for epoch in range(rung.get('min_epochs', 1)):
        name = rung['id'].encode()
        seed = digest('malbolge-rungs:v0:challenge-seed', struct.pack('<Q', len(name)) + name + struct.pack('<I', epoch))
        for index in range(rung['cases']):
            idx = struct.pack('<I', index)
            data = digest('malbolge-coin:mal51:v0:input', seed + idx)
            output = digest('malbolge-coin:mal51:v0:hash-prefix', seed + struct.pack('<Q', len(data)) + data + idx)[:rung['output_bytes']]
            rows.append(dict(rung=rung['id'], epoch=epoch, index=index,
                             input_hex=data.hex(), expected_hex=output.hex()))
    return rows

if __name__ == '__main__':
    registry = json.loads((ROOT / 'crates/harness/registry.json').read_text())
    rows = [row for rung in registry if rung['family'] == 'HashPrefix' for row in derive(rung)]
    Path(__file__).with_name('cases.json').write_text(json.dumps(rows, indent=2) + '\n')
    for rung in registry:
        if rung['family'] == 'HashPrefix':
            print(rung['id'], len(derive(rung)), 'cases')
