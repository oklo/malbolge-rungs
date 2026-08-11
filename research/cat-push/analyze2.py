from vm import *
from itertools import product
def F(m1,m2,x): return CT[(m2, CT[(m1,x)])]
opts={}
for t in range(10):
    bin_=[1,0,2] if t<=4 else ([1,0] if t==5 else [1])
    L=[]
    for m1 in range(3):
        for m2 in range(3):
            outs={F(m1,m2,x) for x in bin_}
            if len(outs)==1: L.append((m1,m2,outs.pop(),F(m1,m2,2)))
    opts[t]=L
LIMIT=8192
res={}
def rec(t,rb,re,m1,m2):
    if rb>=LIMIT or re>=LIMIT: return
    if t==10:
        if rb!=re: res.setdefault((rb,re),[]).append((m1,m2))
        return
    for (a,b,cb,ce) in opts[t]:
        rec(t+1, rb+cb*3**t, re+ce*3**t, m1+a*3**t, m2+b*3**t)
rec(0,0,0,0,0)
print("num distinct (R_byte,R_eof):",len(res))
byte_targets=sorted({rb for (rb,re) in res})
print("distinct R_byte:",len(byte_targets), byte_targets[:40])
eof_targets=sorted({re for (rb,re) in res})
print("distinct R_eof:",len(eof_targets))
# distinct M1 values used
m1s=sorted({m1 for v in res.values() for (m1,m2) in v})
print("distinct M1:",len(m1s), m1s[:20])
