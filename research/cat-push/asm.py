"""Minimal classic-malbolge-51-v0 assembler.

Cell values are forced: at address A, opcode OP => the unique byte in [33,126]
congruent to OP-A mod 94.  Data cells therefore admit exactly 8 values.
"""
from vm import *
OPS={'JMP':4,'OUT':5,'IN':23,'ROT':39,'MOVD':40,'CRZ':62,'NOP':68,'HALT':81}
def byte_for(op,addr): return 33+((op-addr-33)%94)
def op_of(val,addr): return (val+addr)%94
def data_choices(addr): return {op:byte_for(op,addr) for op in OPS.values()}
def can_hold(val,addr): return 33<=val<=126 and op_of(val,addr) in OPS.values()

class Prog:
    def __init__(self,n): self.cells=[None]*n
    def put_op(self,addr,name):
        v=byte_for(OPS[name],addr)
        assert self.cells[addr] is None or self.cells[addr]==v,(addr,name,self.cells[addr])
        self.cells[addr]=v
    def put_val(self,addr,val):
        assert can_hold(val,addr),(addr,val,"not holdable")
        assert self.cells[addr] is None or self.cells[addr]==val,(addr,val,self.cells[addr])
        self.cells[addr]=val
    def emit(self):
        out=bytearray()
        for i,c in enumerate(self.cells):
            out.append(byte_for(OPS['NOP'],i) if c is None else c)
        return bytes(out)

# smoke test: JMP at 0 skips to 99, then IN/OUT/HALT
p=Prog(103)
p.put_op(0,'JMP')            # m[0]=98 -> c=98 -> executes at 99
assert p.cells[0]==98, p.cells[0]
for a in (99,100,101): pass
p.put_op(99,'IN'); p.put_op(100,'OUT'); p.put_op(101,'HALT')
prog=p.emit()
print("len",len(prog))
print(run(prog,b'\x41'))
print(run(prog,b''))
open('/tmp/smoke.mal','wb').write(prog)
