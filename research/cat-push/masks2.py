from vm import *
from masks import A,e,build2,R_pair
BASES=[v for v in range(33,127) if all(t in (0,2) for t in trits(v)[:5]) and all(t==0 for t in trits(v)[5:])]
print("raw M2 candidates:",BASES)
found={}
for M2 in BASES:
    b=trits(M2)
    for disc in (6,7,8):
        m1=[0]*10
        for i in range(5): m1[i]=0 if b[i]==2 else 2
        m1[5]=2
        for i in (6,7,8,9): m1[i]=1 if i==disc else 2
        M1=fromtrits(m1)
        rs,re=R_pair(M1,M2)
        if len(rs)!=1: continue
        rb=rs.pop()
        if rb>=8192 or rb==re: continue
        rec=build2(M1)
        if rec: found[(M2,disc)]=(M1,rb,re,rec[0])
for k in sorted(found): print(k,"M1=%d R_byte=%d R_eof=%d via a1=%d(rotr^%d of %d) a2=%d(rotr^%d of %d)"%(
    found[k][0],found[k][1],found[k][2],found[k][3][0],found[k][3][1][1],found[k][3][1][0],found[k][3][2],found[k][3][3][1],found[k][3][3][0]))
print("distinct buildable R_byte targets:",len({v[1] for v in found.values()}))
