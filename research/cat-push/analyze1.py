from vm import *
VALID=[4,5,23,39,40,62,68,81]
def valid_vals(addr):
    return sorted({33+((op-addr-33)%94) for op in VALID})
d01=[v for v in range(33,127) if all(t<2 for t in trits(v))]
print("digits01 cells:",d01)
ok=[a for a in range(94) if any(v in d01 for v in valid_vals(a))]
print("addr residues with a digits01 option:",len(ok),"/94")

# Enumerate achievable (R_byte,R_eof) from two CRZ masks m1,m2 applied to a=e(x)
# input trit sets per position: t0..t4 byte->{e(0),e(1),e(2)}={1,0,2}; t5 byte->{1,0}; t6..t9 byte->{1}; EOF always 2
def F(m1,m2,x): return CT[(m2, CT[(m1,x)])]
opts={}
for t in range(10):
    if t<=4: bin_=[1,0,2]
    elif t==5: bin_=[1,0]
    else: bin_=[1]
    L=[]
    for m1 in range(3):
        for m2 in range(3):
            outs={F(m1,m2,x) for x in bin_}
            if len(outs)==1:
                L.append((m1,m2,outs.pop(),F(m1,m2,2)))
    opts[t]=L
    print(t,L)
