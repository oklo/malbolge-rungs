#!/usr/bin/env python3
"""Build the L2.C0b.xor51-cov36 candidate: a THREE-layer permuting dispatch.

Prior art.  cov34 proved 34/256 is the exact branchless ceiling; cov40 found the
dispatch architecture (park a computed word v in a cell, MOVD on that cell to get
D = v+1, read the program's own bytes as a 256-entry table) and cov48 corrected
its legal-byte rule and extended the tail depth.  Both fix the dispatch at TWO
CRAZY layers, which forces the composed map on trits 0..5 to be the identity --
M1 o M1 = id is the only injective composition of two rows -- so index(b) = b+K0
and the used table cells are 256 consecutive cells with maximal sharing.

This build uses THREE layers.  The only injective composed low map from three
rows is M1 itself (M1oM1oM1 = M1; anything containing M0 or M2 is non-injective
and stays so), so index(b) = pi(b) + K0 with pi the trit-wise (0->1,1->0,2->2)
permutation on trits 0..5.  pi scatters the 256 used cells over a 377-wide
window, which loosens the coupling the DP has to fight.  research/cov36/perm_dp.c
scores both index maps exactly for every offset and depth.

Shipped configuration: pi = M1, K0 = 2187, k = 3 table layers -> 51/256.
(pi = M1, K0 = 729, k = 2 scores exactly 36 -- the threshold with a two-cell tail,
which no 2-layer dispatch reaches at any offset -- but its table starts at 839 and
the layout below does not fit under that address.)

Layout, Builder and the register-machine BFS are cov32/cov40's, reused:
research/cov40/build.py.
"""
import sys
from collections import deque

M = [[1,0,0],[1,0,2],[2,2,1]]
ENC = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CODE_NOP, CODE_OUT, CODE_IN, CODE_ROT, CODE_MOVD, CODE_CRZ, CODE_HALT = 68,5,23,39,40,62,81

def codebyte(addr, code):
    b = (code - addr) % 94
    if b < 33: b += 94
    assert 33 <= b <= 126
    return b
def xval(addr): return ENC[codebyte(addr, CODE_NOP)-33]

# ---- fast crazy: positionwise, so split the 10-trit word into two 5-trit halves
def _crz_slow(a, d):
    r = 0; p = 1
    for _ in range(5):
        r += M[d%3][a%3]*p; p *= 3; a //= 3; d //= 3
    return r
CT = [[_crz_slow(a,d) for d in range(243)] for a in range(243)]
def crz(a, d):
    return CT[a%243][d%243] + 243*CT[a//243][d//243]
def rot(v): return v//3 + (v%3)*19683
def word(tr): return sum(t*3**i for i,t in enumerate(tr))

# ------------------------------------------------------- the three dispatch words
K0, KDEPTH = 2187, 3
def triples_for(value, acc0=0):
    out = []
    for w1 in range(3):
        for w2 in range(3):
            for w3 in range(3):
                if M[w3][M[w2][M[w1][acc0]]] == value: out.append((w1,w2,w3))
    return out
LOW = [t for t in triples_for(None) if False]  # placeholder, computed below
low = []
for w1 in range(3):
    for w2 in range(3):
        for w3 in range(3):
            if tuple(M[w3][M[w2][M[w1][a]]] for a in range(3)) == (1,0,2): low.append((w1,w2,w3))
assert low == [(1,1,1)], low
LOWT = low[0]

K0trits = [(K0//3**i)%3 for i in range(10)]
assert all(t == 0 for t in K0trits[:6])
POS = [ [LOWT] if i < 6 else triples_for(K0trits[i]) for i in range(10) ]

def pi(b):
    r = 0; p = 1
    for _ in range(6):
        r += M[1][b%3]*p; p *= 3; b //= 3
    return r
IDX = [pi(b)+K0 for b in range(256)]
LO, HI = min(IDX)+1, max(IDX)+KDEPTH

# ------------------------------------------------------- register-machine BFS
CELLS = list(range(34,128))
SEEDS = sorted({xval(a) for a in CELLS})

def bfs(start, forbidden=frozenset(), first_must_be_crz=False):
    prev = {start: None}
    dq = deque([(start, True)])
    while dq:
        v, isfirst = dq.popleft()
        for s in SEEDS:
            if s in forbidden: continue
            n = crz(v, s)
            if n not in prev: prev[n] = (v,'crz',s); dq.append((n, False))
        if not (isfirst and first_must_be_crz):
            n = rot(v)
            if n not in prev: prev[n] = (v,'rot',None); dq.append((n, False))
    return prev
def chain_to(prev, target):
    out = []; v = target
    while prev[v] is not None:
        p, op, s = prev[v]; out.append((op,s)); v = p
    return list(reversed(out))

def words_at(layer):
    """all operand words for CRAZY layer `layer` (0,1,2), as a list"""
    vals = set()
    def rec(i, acc):
        if i == 10: vals.add(acc); return
        for t in POS[i]: rec(i+1, acc + t[layer]*3**i)
    rec(0, 0)
    return sorted(vals)

def compatible(layer, fixed):
    """words for `layer` consistent with already-fixed layers (dict layer->word)"""
    vals = set()
    def rec(i, acc):
        if i == 10: vals.add(acc); return
        for t in POS[i]:
            if all(t[l] == (fixed[l]//3**i)%3 for l in fixed): rec(i+1, acc + t[layer]*3**i)
        return
    rec(0, 0)
    return sorted(vals)

print("BFS from 0 ...", file=sys.stderr)
prev0 = bfs(0)
cands1 = [w for w in words_at(0) if w in prev0]
cands1.sort(key=lambda w: len(chain_to(prev0, w)))
print("O1 candidates reachable:", len(cands1), "best len", len(chain_to(prev0,cands1[0])), file=sys.stderr)

def seeds_of(ch): return [s for op,s in ch if op=='crz']
def distinct(*chs):
    """every CRAZY consumes its cell, and xval is injective on 34..127, so a seed
    byte names exactly one cell -- no chain may use one twice, within a leg either"""
    all_s = sum((seeds_of(c) for c in chs), [])
    return len(all_s) == len(set(all_s))

best = None
for O1 in cands1[:4]:
    c1 = chain_to(prev0, O1)
    if not distinct(c1): continue
    used1 = set(seeds_of(c1))
    prev1 = bfs(O1, forbidden=used1, first_must_be_crz=True)
    c2opts = [w for w in compatible(1, {0:O1}) if w in prev1]
    c2opts.sort(key=lambda w: len(chain_to(prev1,w)))
    for O2 in c2opts[:6]:
        c2 = chain_to(prev1, O2)
        if not distinct(c1, c2): continue
        used2 = used1 | set(seeds_of(c2))
        prev2 = bfs(O2, forbidden=used2, first_must_be_crz=True)
        c3opts = [w for w in compatible(2, {0:O1,1:O2}) if w in prev2]
        c3opts.sort(key=lambda w: len(chain_to(prev2,w)))
        for O3 in c3opts[:6]:
            c3 = chain_to(prev2, O3)
            if not distinct(c1, c2, c3): continue
            tot = len(c1)+len(c2)+len(c3)
            if best is None or tot < best[0]: best = (tot, O1,O2,O3, c1,c2,c3)
            break
    if best and best[0] <= 15: break
assert best, "no reachable operand triple"
tot, O1,O2,O3, c1,c2,c3 = best
print("operands", O1,O2,O3, "chain lens", len(c1),len(c2),len(c3), file=sys.stderr)
# sanity: the composed dispatch really is pi(b)+K0
for b in (0,7,255,128):
    assert crz(crz(crz(b,O1),O2),O3) == pi(b)+K0, (b, crz(crz(crz(b,O1),O2),O3), pi(b)+K0)

# ----------------------------------------------------------------- table bytes
TBL = {}
with open(sys.argv[2] if len(sys.argv)>2 else "table.txt") as f:
    hdr = f.readline().split()
    mode, k0, kk, lo, hi, sc = map(int, hdr)
    assert (mode,k0,kk,lo,hi) == (1,K0,KDEPTH,LO,HI), (hdr, LO, HI)
    for line in f:
        a,v = line.split(); TBL[int(a)] = int(v)
print("table", lo, hi, "expected score", sc, file=sys.stderr)

# --------------------------------------------------------------------- layout
class Builder:
    """cov32/cov40 layout: prefix of NOP cells doubling as a MOVD pointer table."""
    def __init__(self, prefix_end, reserved):
        self.prog, self.addr, self.d = {}, prefix_end, prefix_end
        self.first, self.reserved, self.prefix_end = True, set(reserved), prefix_end
    def emit(self, code):
        self.prog[self.addr] = codebyte(self.addr, code); self.addr += 1; self.d += 1
    def movd(self, q):
        if self.first:
            while ((q-1) + self.addr) % 94 != CODE_MOVD: self.emit(CODE_NOP)
            self.prog[self.addr] = q-1; self.addr += 1; self.d = q; self.first = False; return
        while xval(self.d) != q-1 or self.d in self.reserved:
            self.emit(CODE_NOP)
            if self.d >= self.prefix_end: raise RuntimeError("D walked past the prefix")
        self.prog[self.addr] = codebyte(self.addr, CODE_MOVD); self.addr += 1; self.d = q
    def movd_here(self):
        self.prog[self.addr] = codebyte(self.addr, CODE_MOVD); self.addr += 1; self.d = 0

def assign_cells(chain, avail):
    out = []; last = None; taken = []
    for op, s in chain:
        if op == 'crz':
            q = next(a for a in avail if xval(a) == s and a not in taken)
            taken.append(q); out.append((op,q)); last = q
        else:
            out.append((op,last))
    return out

def build(prefix_end):
    ch1 = assign_cells(c1, CELLS)
    used = [q for _,q in ch1]
    ch2 = assign_cells(c2, [a for a in CELLS if a not in used])
    used += [q for _,q in ch2]
    ch3 = assign_cells(c3, [a for a in CELLS if a not in used])
    W1, W2, W3 = ch1[-1][1], ch2[-1][1], ch3[-1][1]
    reserved = {q for _,q in ch1+ch2+ch3}
    b = Builder(prefix_end, reserved)
    for op,q in ch1+ch2+ch3:
        b.movd(q); b.emit(CODE_CRZ if op=='crz' else CODE_ROT)
    b.emit(CODE_IN)
    b.movd(W1); b.emit(CODE_CRZ)
    b.movd(W2); b.emit(CODE_CRZ)
    b.movd(W3); b.emit(CODE_CRZ)      # A = v = pi(b)+K0, parked in mem[W3]
    b.movd(W3)                        # D = W3 again
    b.movd_here()                     # D = mem[W3] = v, then ++ -> v+1
    for _ in range(KDEPTH): b.emit(CODE_CRZ)
    b.emit(CODE_OUT); b.emit(CODE_HALT)
    if b.addr >= LO: raise RuntimeError("code ends at %d, table starts at %d" % (b.addr, LO))
    n = HI + 1
    src = bytearray(codebyte(a, CODE_NOP) for a in range(n))
    for a,v in b.prog.items(): src[a] = v
    for a,v in TBL.items(): src[a] = v
    return bytes(src), b.addr

prog = None
for pe in (256, 384, 512, 640, 768, 1024, 1280):
    try:
        prog, end = build(pe); print("prefix_end", pe, "OK", file=sys.stderr); break
    except RuntimeError as e:
        print("prefix_end", pe, "->", e, file=sys.stderr)
assert prog is not None, "no layout found"
out = sys.argv[1] if len(sys.argv)>1 else "cand36.mal"
open(out,'wb').write(prog)
print("wrote", out, len(prog), "bytes, code ends", end, "table", LO, HI, "score", sc, file=sys.stderr)
