from vm import *
OPS={'JMP':4,'OUT':5,'IN':23,'ROT':39,'MOVD':40,'CRZ':62,'NOP':68,'HALT':81}
def byte_for(op,addr): return 33+((op-addr-33)%94)
def can_hold(v,a): return 33<=v<=126 and (v+a)%94 in OPS.values()
D01=[v for v in range(33,127) if all(t<2 for t in trits(v))]

class Asm:
    def __init__(self,size):
        self.cell=[None]*size; self.pc=99; self.delta=1-99
        self.cell[0]=byte_for(OPS['JMP'],0); assert self.cell[0]==98
    def op(self,n):
        assert self.cell[self.pc] is None,(self.pc,'busy'); self.cell[self.pc]=byte_for(OPS[n],self.pc); self.pc+=1
    def putdata(self,addr,val):
        assert can_hold(val,addr),(addr,val); assert self.cell[addr] in (None,val),(addr,val,self.cell[addr])
        self.cell[addr]=val
    def movd(self,D):
        for pad in range(300):
            p=self.pc+pad+self.delta
            if 0<p<99 and can_hold(D-1,p) and self.cell[p] in (None,D-1):
                for _ in range(pad): self.op('NOP')
                self.putdata(p,D-1); self.op('MOVD'); self.delta=D-self.pc; return
        raise RuntimeError(f"movd {D} pc={self.pc} delta={self.delta}")
    def emit(self): return bytes(byte_for(OPS['NOP'],i) if c is None else c for i,c in enumerate(self.cell))

used={0,80,81}
def pick(pred,used,rng=range(34,99)):
    for a in rng:
        if a in used: continue
        for v in range(33,127):
            if can_hold(v,a) and pred(v): used.add(a); return a,v
    raise RuntimeError("no cell")
S,Sv  =pick(lambda v:v in D01,used)
A80,_ =pick(lambda v:v==80,used,range(34,99))
M2,_  =pick(lambda v:v==80,used,range(34,99))
N,Nv  =pick(lambda v:v in D01,used)
C1,C1v=pick(lambda v:v in D01,used)
Ta,Tav=pick(lambda v:v in D01,used)
Tb,Tbv=pick(lambda v:v in D01,used)
A122,_=pick(lambda v:v==122,used,range(34,99))
print("S,A80,M2,N,C1,Ta,Tb,A122 =",S,A80,M2,N,C1,Ta,Tb,A122)

a=Asm(6900)
for ad,v in [(S,Sv),(A80,80),(M2,80),(N,Nv),(C1,C1v),(Ta,Tav),(Tb,Tbv),(A122,122)]: a.putdata(ad,v)
a.cell[81]=byte_for(OPS['HALT'],81); a.cell[80]=byte_for(OPS['NOP'],80)
def crz(D): a.movd(D); a.op('CRZ')
def rot(D): a.movd(D); a.op('ROT')

crz(S); crz(Ta); crz(N); crz(Tb); crz(C1)      # S=N=C1=29524, a=29524
for _ in range(6): rot(A80)                    # a = rotr^6(80) = 6480
crz(C1)                                        # C1 = e(6480)
rot(A122)                                      # a = rotr(122) = 39406
crz(C1)                                        # C1 = M1 = 52407
a.op('IN')
crz(S)                                         # S = e(x), a = e(x)
crz(C1)                                        # a = crazy(e(x),M1)
crz(M2)                                        # m[M2] = R, a = R
a.movd(M2); a.op('JMP')                        # c = R ; byte 6641 -> 6642, eof 80 -> 81 HALT
print("code ends at",a.pc,"delta",a.delta)
dsave=M2+1
a.pc=6642; a.delta=dsave-6642
for _ in range(10): rot(S)                     # a = e(x), S back to e(x)
crz(N)                                         # a = x
a.op('OUT'); a.op('HALT')
prog=a.emit(); open('/tmp/blk.mal','wb').write(prog); print("len",len(prog))
for inp in [b'A',b'\x00',b'\xff',b'\xf3',b'\x51',b'']:
    print(repr(inp), run(prog,inp,max_steps=65536))
