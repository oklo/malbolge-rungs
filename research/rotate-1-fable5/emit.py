#!/usr/bin/env python3
"""Exact emitter for straight-line two-register genomes on L2.R2.rotate-1.

Layout (register on park2, pristine b on park1):
    C0..5   IN, MOVD x3 (D: 1->40->123->71), CRZ x2   m[72]=b, D=73
    C6..13  NOP, MOVD (74:101 -> 102), NOP x4, CRZ x2  m[107]=b, D=108
    [prep: rot constant/stage cells; A disposable]
    [cycle: (MOVD 108->86, MOVD 86->107, ROT@107) x j0; A=reg=rotr^j0(b)]
    [circuit ops; A=acc live]
    OUT, HALT
    P <= 71 (cell 71 is the 121-pin); code[40] must be NOP (byte 122).

Genome ops:
    ('crz', c)  acc = crazy(acc, c)     manufactured chain cell
    ('rot',)    acc = rotr(acc)         at the current acc cell
    ('swp', c)  acc = crazy(c, acc)     c ROT-loaded from a stage cell
    ('reg',)    acc = crazy(acc, reg)   CRZ at 107 (destroys reg; once)
    ('finb',)   acc = crazy(acc, b)     CRZ at 72 (destroys park1; once)
D is b-independent throughout; MOVD only ever executes at pin cells.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "xor-1-push"))
import mal

OPS = {"jmp": 4, "out": 5, "in": 23, "rot": 39, "movd": 40, "crz": 62, "nop": 68, "hlt": 81}


def crazy(a, d):
    T = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]
    r, f = 0, 1
    for _ in range(10):
        r += T[d % 3][a % 3] * f
        a //= 3
        d //= 3
        f *= 3
    return r


def rotr(w):
    return w // 3 + (w % 3) * 19683


def rotl(w):
    return (w % 19683) * 3 + w // 19683


def legal(addr):
    return sorted(mal.legal_bytes(addr).values())


class Nav(Exception):
    pass


class Emit:
    def __init__(self, j0, ops, place=None):
        self.j0, self.ops = j0, ops
        self.place = place or {}
        self.code = []
        # fixed pins: addr -> byte
        self.pins = {40: 122, 123: 70, 74: 101, 108: 85, 86: 106}
        self.parks = {71: 121, 72: 121, 106: 121, 107: 121}
        self.consts = {}          # addr -> start byte (constants/stages)
        self.D = None
        self.log = []

    def all_data(self):
        d = {}
        d.update(self.pins)
        d.update(self.parks)
        d.update(self.consts)
        return d

    def is_free(self, a):
        return 75 <= a <= 122 and a not in self.all_data() and a not in (86, 106, 107, 108)

    # emission ------------------------------------------------------------
    def ins(self, name, note=""):
        assert not (len(self.code) == 40 and name != "nop"), "pad missed at C=40"
        self.code.append(name)
        self.log.append(f"C={len(self.code)-1:3d} {name:4s} D={self.D} {note}")

    def nop(self):
        self.ins("nop")
        self.D += 1

    def movd(self):
        b = self.pins.get(self.D)
        assert b is not None, f"MOVD at non-pin cell {self.D}"
        self.ins("movd", f"D->{b + 1}")
        self.D = b + 1

    def rot(self, note=""):
        self.ins("rot", note)
        self.D += 1

    def crz(self, note=""):
        self.ins("crz", note)
        self.D += 1

    # routing: D -> T using glides and pin hops ----------------------------
    def act(self, T, fn, *a, **kw):
        while True:
            self.nav(T)
            if len(self.code) == 40:
                self.nop()
                continue
            return fn(*a, **kw)

    def nav(self, T, budget=14):
        start_code = len(self.code)
        guard = 0
        while self.D != T:
            guard += 1
            assert guard < 8, f"nav thrash {self.D}->{T}"
            path = self._route(self.D, T, budget, set())
            redo = False
            for step in path:
                if len(self.code) == 40 and step != "nop":
                    self.nop()          # pad; D moved, path stale
                    redo = True
                    break
                if step == "nop":
                    self.nop()
                else:
                    _, addr, byte = step
                    if addr not in self.pins:
                        self.pins[addr] = byte
                    self.movd()
            if not redo:
                break
        assert self.D == T, (self.D, T)
        return len(self.code) - start_code

    def _route(self, D, T, budget, seen):
        """BFS over D-states 0..123. Steps: 'nop' or ('hop', addr, byte).
        Glide from any state; hop via existing pin; hop via assignable pin
        (one byte choice recorded per state). Fewest instructions wins."""
        from collections import deque
        if D == T:
            return []
        prev = {D: None}
        q = deque([D])
        while q:
            x = q.popleft()
            outs = []
            if x + 1 <= 123:
                outs.append((x + 1, "nop"))
            if x in self.pins:
                outs.append((self.pins[x] + 1, ("hop", x, self.pins[x])))
            elif self.is_free(x):
                for v in legal(x):
                    nd = v + 1
                    if 34 <= nd <= 123:
                        outs.append((nd, ("hop", x, v)))
            for nd, step in outs:
                if nd not in prev:
                    prev[nd] = (x, step)
                    if nd == T:
                        path = []
                        cur = T
                        while prev[cur] is not None:
                            cur, st = prev[cur]
                            path.append(st)
                        path.reverse()
                        if len(path) > budget:
                            raise Nav(f"route {D}->{T} too long ({len(path)})")
                        return path
                    q.append(nd)
        raise Nav(f"no route {D}->{T}")

    # constant placement ---------------------------------------------------
    def place_const(self, value, need_rot_pin):
        """Find (cell, start_byte, k). Prefer small k, then cheap rot route."""
        best = None
        for cell in range(75, 123):
            if not self.is_free(cell):
                continue
            for v in legal(cell):
                w = v
                for k in range(10):
                    if w == value:
                        cost = k * 3
                        if best is None or cost < best[3]:
                            best = (cell, v, k, cost)
                    w = rotr(w)
        if best is None:
            raise Nav(f"constant {value} unplaceable")
        cell, v, k, _ = best
        self.consts[cell] = v
        return cell, k

    # build ----------------------------------------------------------------
    def build(self):
        self.code = ["in", "movd", "movd", "movd", "crz", "crz"]
        self.D = 73
        self.code += ["nop", "movd", "nop", "nop", "nop", "nop", "crz", "crz"]
        self.D = 108
        self.log.append("head+parks done, D=108")

        # plan chain/stage cells
        plan = []          # per op: (kind, cell)
        preps = []         # (cell, k)
        for oi, op in enumerate(self.ops):
            if op[0] == "crz":
                if oi in self.place:
                    cell, v, k = self.place[oi]
                    self.consts[cell] = v
                else:
                    cell, k = self.place_const(op[1], True)
                if k:
                    preps.append((cell, k))
                plan.append(("crz", cell))
            elif op[0] == "swp":
                cell, k = self.place_const(rotl(op[1]), False)
                if k:
                    preps.append((cell, k))
                plan.append(("swp", cell))
            else:
                plan.append((op[0], None))

        # prep rotations (A disposable)
        for cell, k in preps:
            for i in range(k):
                self.act(cell, self.rot, f"prep {cell} ({i+1}/{k})")

        # register cycle
        for i in range(self.j0):
            while len(self.code) in (38, 39, 40):
                self.nop()
            self.act(108, self.movd)
            self.movd()
            self.rot(f"reg {i+1}/{self.j0}")

        # circuit
        acc_cell = None
        for kind, cell in plan:
            if kind == "crz":
                self.act(cell, self.crz, f"crz@{cell}")
                acc_cell = cell
            elif kind == "rot":
                tgt = acc_cell if acc_cell is not None else 107
                self.act(tgt, self.rot, f"rotacc@{tgt}")
            elif kind == "swp":
                self.act(cell, self.rot, f"stage@{cell}")
                tgt = acc_cell if acc_cell is not None else 107
                self.act(tgt, self.crz, f"swp@{tgt}")
            elif kind == "reg":
                self.act(107, self.crz, "reg@107")
                acc_cell = 107
            elif kind == "finb":
                self.act(72, self.crz, "finb@72")
                acc_cell = 72
        self.code += ["out", "hlt"]
        return self.finish()

    def finish(self):
        P = len(self.code)
        data = self.all_data()
        assert P <= 71, f"code too long: {P}"
        assert self.code[40] == "nop" if P > 40 else True
        L = max(data) + 1
        prog = []
        for a in range(L):
            if a == 40 and P > 40:
                prog.append(122)          # pin doubling as NOP
            elif a < P:
                b = mal.byte_for(OPS[self.code[a]], a)
                assert b is not None, (a, self.code[a])
                prog.append(b)
            elif a in data:
                prog.append(data[a])
            else:
                prog.append(legal(a)[0])
        return bytes(prog), P, L


def genome_py(j0, ops, b):
    reg = b
    for _ in range(j0):
        reg = rotr(reg)
    acc = reg
    for op in ops:
        if op[0] == "crz":
            acc = crazy(acc, op[1])
        elif op[0] == "rot":
            acc = rotr(acc)
        elif op[0] == "swp":
            acc = crazy(op[1], acc)
        elif op[0] == "reg":
            acc = crazy(acc, reg)
        elif op[0] == "finb":
            acc = crazy(acc, b)
    return acc % 256


def rotlb(b):
    return ((b << 1) | (b >> 7)) & 0xFF


def check(j0, ops, tag, dump=None):
    want = sum(1 for b in range(256) if genome_py(j0, ops, b) == rotlb(b))
    e = Emit(j0, ops)
    prog, P, L = e.build()
    ok = []
    for b in range(256):
        out, st, _ = mal.run(list(prog), [b])
        if st == "Halted" and out == bytes([rotlb(b)]):
            ok.append(b)
    print(f"{tag}: genome={want}/256 assembled={len(ok)}/256 P={P} L={L} len={len(prog)}")
    if dump and len(ok) == want:
        open(dump, "wb").write(prog)
        print(f"  wrote {dump}")
    if len(ok) != want:
        for line in e.log:
            print("   ", line)
    return len(ok), want, prog


if __name__ == "__main__":
    # smoke: j0=1, single reg op: acc = crazy(rotr(b), rotr(b))
    check(1, [("reg",)], "smoke-reg")
    # smoke with a byte constant + rot + finb
    check(2, [("crz", 100), ("rot",), ("finb",)], "smoke-mix")
