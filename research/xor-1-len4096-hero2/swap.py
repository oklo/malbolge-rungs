#!/usr/bin/env python3
"""Build the IN/MOVD-swapped prologue.

Address 1 must hold the first MOVD in prior art's phase, because a MOVD run
while d == c reads its own cell and is the only way to get d off the c track.
byte_for(MOVD,1) = 39 uniquely, and X2[39] decodes to IN at address 1 -- which
is why b=0 dies at its first sled step.

Fix: run the MOVD at address 0 instead (d = m[0] = 40, unique) and put the IN
at address 1.  Same 33-byte prologue, same instruction at every later address,
so every other input's block is untouched; only the d-chain phase shifts by 2.
Address 2's MOVD then reads m[42] instead of m[40], and m[42] must be a byte
that is LEGAL AT ADDRESS 42 and routes d to the same place the old chain did.
"""
X2 = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CODES = {4,5,23,39,40,62,68,81}
NAMES = {4:'JMP',5:'OUT',23:'IN',39:'ROT',40:'MOVD',62:'CRZ',68:'NOP',81:'HLT'}
def legal(v,a): return 33<=v<=126 and (v+a)%94 in CODES
def byte_for(code,a):
    v=(code-a)%94
    while v<33: v+=94
    return v if v<=126 else None

prog = bytearray(open('cand.mal','rb').read())
print("old prog[0]=%d(%s) prog[1]=%d(%s) prog[40]=%d prog[123]=%d" % (
    prog[0], NAMES[(prog[0]+0)%94], prog[1], NAMES[(prog[1]+1)%94], prog[40], prog[123]))

# old chain: addr2 MOVD reads m[40]=122 -> d=122, addr3 MOVD reads m[123]=70 -> d=70,
# then d=71 for the CRAZY pair at (71,72).  New: addr2 MOVD reads m[42].
# Need V=m[42] legal at 42, and m[V+1]=70 legal at V+1.
tgt = 70
cands=[]
for V in range(33,127):
    if not legal(V,42): continue
    if V+1 > 126 or not legal(tgt, V+1): continue
    cands.append(V)
print("one-hop chain values V for m[42]:", [(V, NAMES[(V+42)%94], V+1) for V in cands])
