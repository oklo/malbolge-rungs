#!/usr/bin/env python3
"""Build the L2.C0c.xor51-cov40 candidate: identity dispatch into a program-byte table.

Branchless ceiling on this transform is 34 (research/cov32/family_ceiling.py,
realised by solutions/cov34).  cov40 needs 40, so it needs an input-dependent
branch.  research/cov40/dispatch_ceiling.c scores every realizable product
partition; research/cov40/table_dp.c scores this one exactly.

Mechanism.  Two CRAZY layers whose operands have trits 0..5 = 1 compose to the
identity there (M1 o M1 = id), so with the high trits picked to add K0 = 1458:

    A = v = b + 1458      (positions 0..5 are b's own trits, 6 is 2, 7..9 are 0)

v is parked in the cell the second CRAZY wrote.  MOVD on that cell sets
D = v + 1 = b + 1459: *the input is the dispatch index*, a 256-entry table with
no per-entry construction cost.  Three CRAZY layers then read mem[b+1459..b+1461]
-- program bytes past the code, never executed.  Each such byte has exactly eight
source-valid values, and consecutive inputs share cells, so the optimum over the
whole table is a transfer-matrix DP: 48/256.
"""
import sys
sys.setrecursionlimit(10000)

M = [[1,0,0],[1,0,2],[2,2,1]]
ENC = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
CODE_NOP, CODE_OUT, CODE_IN, CODE_ROT, CODE_MOVD, CODE_CRZ, CODE_HALT = 68,5,23,39,40,62,81
OPS = [4,5,23,39,40,62,68,81]

def codebyte(addr, code):
    b = (code - addr) % 94
    if b < 33: b += 94
    assert 33 <= b <= 126
    return b
def xval(addr): return ENC[codebyte(addr, CODE_NOP)-33]

def crz(a,d):
    r=0;p=1
    for _ in range(10):
        r += M[d%3][a%3]*p; p*=3; a//=3; d//=3
    return r
def rot(v): return v//3 + (v%3)*19683

def word(trits): return sum(t*3**i for i,t in enumerate(trits))
O1 = word([1,1,1,1,1,1,0,1,1,1])
O2 = word([1,1,1,1,1,1,2,1,1,1])
K0 = 1458
assert crz(crz(7,O1),O2) == 7 + K0

# ---------------------------------------------------------------- BFS on words
CELLS = list(range(34,128))
SEEDS = sorted({xval(a) for a in CELLS})

def bfs(start, forbidden=frozenset(), first_must_be_crz=False):
    """A <- crazy(A, seed) on a fresh cell, or A <- rot(A) on the cell just written."""
    from collections import deque
    prev = {start: None}
    dq = deque([(start, True)])
    seen = {(start, True)}
    while dq:
        v, isfirst = dq.popleft()
        for s in SEEDS:
            if s in forbidden: continue
            n = crz(v, s)
            if n not in prev:
                prev[n] = (v, 'crz', s); dq.append((n, False)); 
        if not (isfirst and first_must_be_crz):
            n = rot(v)
            if n not in prev:
                prev[n] = (v, 'rot', None); dq.append((n, False))
    return prev

def chain_to(prev, target):
    out = []
    v = target
    while prev[v] is not None:
        p, op, s = prev[v]; out.append((op, s)); v = p
    return list(reversed(out))

prev0 = bfs(0)
if O1 not in prev0: print("O1 unreachable"); sys.exit(1)
c1 = chain_to(prev0, O1)
used = {s for op,s in c1 if op=='crz'}
prev1 = bfs(O1, forbidden=used, first_must_be_crz=True)
if O2 not in prev1: print("O2 unreachable from O1"); sys.exit(1)
c2 = chain_to(prev1, O2)
print("chain1", c1, file=sys.stderr)
print("chain2", c2, file=sys.stderr)

# ------------------------------------------------------------------- table DP
def legal(a): return sorted(codebyte(a, op) for op in OPS)
BASE = K0 + 1
K = 3
NC = 256 + K - 1
L = [legal(BASE+c) for c in range(NC)]
TGT = [b ^ 0x51 for b in range(256)]
# dp over states = (choice[c-1], choice[c-2])
NEG = -10**9
dp = {}
for i in range(8):
    for j in range(8):
        dp[(i,j)] = (0, None)
for c in range(K-1, NC):
    nd = {}
    b = c - (K-1)
    for (s1,s0), (sc, par) in dp.items():   # s1 = choice[c-2], s0 = choice[c-1]
        for nx in range(8):
            A = b + K0
            for op in (L[c-2][s1], L[c-1][s0], L[c][nx]):
                A = crz(A, op)
            hit = 1 if (A & 255) == TGT[b] else 0
            key = (s0, nx)
            val = sc + hit
            if key not in nd or val > nd[key][0]:
                nd[key] = (val, ((s1,s0), nx))
    dp = nd
best_key = max(dp, key=lambda k: dp[k][0])
score = dp[best_key][0]
print("DP score", score, file=sys.stderr)
# reconstruct is unnecessary for scoring but needed for the bytes: redo with parents
# (store full parent chain)
dp = {(i,j): (0, []) for i in range(8) for j in range(8)}
for c in range(K-1, NC):
    nd = {}
    b = c - (K-1)
    for (s1,s0), (sc, path) in dp.items():
        for nx in range(8):
            A = b + K0
            for op in (L[c-2][s1], L[c-1][s0], L[c][nx]):
                A = crz(A, op)
            hit = 1 if (A & 255) == TGT[b] else 0
            key = (s0, nx); val = sc + hit
            if key not in nd or val > nd[key][0]:
                nd[key] = (val, path + [nx])
    dp = nd
bk = max(dp, key=lambda k: dp[k][0])
score, tail = dp[bk]
choices = [bk[0] if False else None]
# path holds choices for cells K-1 .. NC-1; the first K-1 come from the seed state
first = None
for (s1,s0),(v,p) in [(bk, dp[bk])]: pass
# recover seed pair: rerun forward with the recorded tail is ambiguous; instead brute
# force the two seed choices that reproduce `score`
def evaluate(seed_pair, tailchoices):
    ch = [seed_pair[0], seed_pair[1]] + tailchoices
    n = 0
    for b in range(256):
        A = b + K0
        for t in range(K):
            A = crz(A, L[b+t][ch[b+t]])
        if (A & 255) == TGT[b]: n += 1
    return n, ch
found = None
for i in range(8):
    for j in range(8):
        n, ch = evaluate((i,j), tail)
        if n == score: found = ch; break
    if found: break
assert found is not None, "seed recovery failed"
CH = found
print("verified table score", score, file=sys.stderr)

# --------------------------------------------------------------------- layout
class Builder:
    def __init__(self, prefix_end, reserved):
        self.prog, self.addr, self.d = {}, prefix_end, prefix_end
        self.first, self.reserved, self.prefix_end = True, set(reserved), prefix_end
    def emit(self, code):
        self.prog[self.addr] = codebyte(self.addr, code); self.addr += 1; self.d += 1
    def movd(self, q):
        if self.first:
            while ((q-1) + self.addr) % 94 != CODE_MOVD:
                self.emit(CODE_NOP)
            self.prog[self.addr] = q-1; self.addr += 1; self.d = q; self.first = False; return
        while xval(self.d) != q-1 or self.d in self.reserved:
            self.emit(CODE_NOP)
            if self.d >= self.prefix_end: raise RuntimeError("D walked past the prefix")
        self.prog[self.addr] = codebyte(self.addr, CODE_MOVD); self.addr += 1; self.d = q
    def movd_here(self):
        """MOVD on the cell D already points at (used for the input-dependent dispatch)."""
        self.prog[self.addr] = codebyte(self.addr, CODE_MOVD); self.addr += 1; self.d = 0  # D is now input-dependent; no further movd() is emitted

def assign_cells(chain, start_cells):
    """Map each 'crz' step's seed byte to a cell holding it; 'rot' reuses the last cell."""
    out = []; last = None
    for op, s in chain:
        if op == 'crz':
            q = next(a for a in start_cells if xval(a) == s and a not in [c for _,c in out])
            out.append((op, q)); last = q
        else:
            out.append((op, last))
    return out

def build(prefix_end):
    ch1 = assign_cells(c1, CELLS)
    ch2 = assign_cells(c2, [a for a in CELLS if a not in [q for _,q in ch1]])
    W1 = ch1[-1][1]; W2 = ch2[-1][1]
    reserved = {q for _,q in ch1} | {q for _,q in ch2}
    b = Builder(prefix_end, reserved)
    for op, q in ch1 + ch2:
        b.movd(q); b.emit(CODE_CRZ if op=='crz' else CODE_ROT)
    b.emit(CODE_IN)
    b.movd(W1); b.emit(CODE_CRZ)
    b.movd(W2); b.emit(CODE_CRZ)          # A = v = b + K0, mem[W2] = v, D = W2+1
    b.movd(W2)                            # D = W2 again
    b.movd_here()                         # D = mem[W2] = v, then ++ -> b+1459
    b.emit(CODE_CRZ); b.emit(CODE_CRZ); b.emit(CODE_CRZ)
    b.emit(CODE_OUT); b.emit(CODE_HALT)
    if b.addr >= BASE: raise RuntimeError("code overruns the table at %d (ends %d)" % (BASE, b.addr))
    n = BASE + NC
    src = bytearray(codebyte(a, CODE_NOP) for a in range(n))
    for a, v in b.prog.items(): src[a] = v
    for c in range(NC): src[BASE+c] = L[c][CH[c]]
    return bytes(src), b.addr

for pe in (256, 384, 512, 640, 768, 1024):
    try:
        prog, end = build(pe); break
    except RuntimeError as e:
        print("prefix_end", pe, "->", e, file=sys.stderr); prog = None
if prog is None:
    print("no layout found", file=sys.stderr); sys.exit(1)
out = sys.argv[1] if len(sys.argv) > 1 else "cand.mal"
open(out,'wb').write(prog)
print("wrote", out, len(prog), "bytes, code ends at", end, "expected score", score, file=sys.stderr)
