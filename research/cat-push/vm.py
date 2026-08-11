XLAT2 = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
assert len(XLAT2) == 94
W = 59049; WMAX = 59048
VALID = {4,5,23,39,40,62,68,81}
NAMES = {4:'JMP',5:'OUT',23:'IN',39:'ROT',40:'MOVD',62:'CRZ',68:'NOP',81:'HALT'}

def trits(w):
    t=[]
    for _ in range(10):
        t.append(w%3); w//=3
    return t
def fromtrits(t):
    v=0
    for x in reversed(t): v = v*3 + x
    return v
CT = {(0,0):1,(0,1):0,(0,2):0,(1,0):1,(1,1):0,(1,2):2,(2,0):2,(2,1):2,(2,2):1}
def crazy(a,d):
    ta,td=trits(a),trits(d)
    return fromtrits([CT[(td[i],ta[i])] for i in range(10)])
def rotr(w): return w//3 + (w%3)*19683
def code(word, addr): return (word+addr)%94
def enc(w): return XLAT2[w-33]

def load(prog):
    ex=[b for b in prog if not (32==b or 9<=b<=13)]
    for i,b in enumerate(ex):
        if not (33<=b<=126): raise ValueError(f"nonprintable {b} at {i}")
        if code(b,i) not in VALID: raise ValueError(f"bad instr {code(b,i)} at {i} (byte {chr(b)})")
    return ex

def initmem(ex):
    m=[0]*W
    for i,b in enumerate(ex): m[i]=b
    for i in range(len(ex),W): m[i]=crazy(m[i-1],m[i-2])
    return m

def run(prog, inp, max_steps=65536, max_out=16, trace=None):
    ex=load(prog); m=initmem(ex)
    a=0;c=0;d=0;ii=0;out=bytearray()
    for step in range(max_steps):
        f=m[c]
        if not (33<=f<=126): return ('InvalidRuntimeInstruction',bytes(out),step)
        op=code(f,c)
        if trace is not None and step<trace:
            print(f"{step:5d} c={c:5d} d={d:5d} a={a:5d} m[c]={f:3d} op={NAMES.get(op,op)}")
        if op==4: c=m[d]
        elif op==5:
            if len(out)>=max_out: return ('OutputLimitExceeded',bytes(out),step)
            out.append(a%256)
        elif op==23:
            if ii<len(inp): a=inp[ii]; ii+=1
            else: a=WMAX
        elif op==39:
            m[d]=rotr(m[d]); a=m[d]
        elif op==40: d=m[d]
        elif op==62:
            m[d]=crazy(a,m[d]); a=m[d]
        elif op==81: return ('Halted',bytes(out),step+1)
        w=m[c]
        if not (33<=w<=126): return ('InvalidRuntimeInstruction',bytes(out),step)
        m[c]=enc(w)
        c=(c+1)%W; d=(d+1)%W
    return ('StepLimitExceeded',bytes(out),max_steps)
