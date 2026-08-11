from vm import *
# A = accumulator values reachable as rotr^k(V) for a raw cell V in [33,126]
A={}
for V in range(33,127):
    w=V
    for k in range(10):
        A.setdefault(w,(V,k)); w=rotr(w)
def e(v): return crazy(v,29524)   # crazy(a,all-1s) = per-trit [1,0,2]
def build2(target):
    """C=all1s; CRZ(a1) -> C=e(a1); CRZ(a2) -> C=target.  return (a1,a2) recipes"""
    out=[]
    for a1 in A:
        C1=e(a1)
        c1t,tt=trits(C1),trits(target)
        a2t=[]
        ok=True
        for i in range(10):
            cand=[m for m in (0,1,2) if CT[(c1t[i],m)]==tt[i]]
            if not cand: ok=False;break
            a2t.append(cand)
        if not ok: continue
        # try to find an a2 in A matching
        for a2 in A:
            t2=trits(a2)
            if all(t2[i] in a2t[i] for i in range(10)):
                out.append((a1,A[a1],a2,A[a2]))
                break
    return out

def R_pair(M1,M2):
    """simulate: a=e(x); A=crazy(a,M1); R=crazy(A,M2). return (set of R over bytes, R_eof)"""
    rs=set()
    for x in range(256):
        a=e(x); Aa=crazy(a,M1); rs.add(crazy(Aa,M2))
    a=e(59048); Aa=crazy(a,M1); return rs, crazy(Aa,M2)

for S,name in [({6},'S6'),({7},'S7'),({8},'S8')]:
    m1=[0]*10
    for i in range(4): m1[i]=0      # M2 has 2 there
    m1[4]=2; m1[5]=2
    for i in (6,7,8,9): m1[i]=1 if i in S else 2
    M1=fromtrits(m1); M2=80
    rs,re=R_pair(M1,M2)
    print(name,"M1=",M1,"M2=",M2,"R_byte set:",sorted(rs),"R_eof:",re)
    r=build2(M1)
    print("   buildable recipes:",len(r), r[:3])
