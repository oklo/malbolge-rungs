"""Minimal classic-Malbolge-51 model VM, mirroring crates/classic_malbolge/src/lib.rs.

Opcodes (instruction_code(word, addr) = (word + addr) % 94):
    4  JMP  C = m[D]
    5  OUT  emit A % 256
   23  IN   A = next input byte (or 59048 at EOF)
   39  ROT  m[D] = rotr(m[D]); A = m[D]
   40  MOVD D = m[D]
   62  CRZ  m[D] = crazy(A, m[D]); A = m[D]
   68  NOP
   81  HALT
After every non-halt instruction: m[C] = encipher(m[C]); C += 1; D += 1.
"""

OPSET = (4, 5, 23, 39, 40, 62, 68, 81)
JMP, OUT, IN, ROT, MOVD, CRZ, NOP, HALT = OPSET
NAMES = {4: "JMP", 5: "OUT", 23: "IN", 39: "ROT", 40: "MOVD", 62: "CRZ", 68: "NOP", 81: "HALT"}

ENCIPHER = (br"5z]&gqtyfr$(we4{WP)H-Zn,[%\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G" + b'"i@')
assert len(ENCIPHER) == 94, len(ENCIPHER)

MOD = 59049

_CRAZY = {(0, 0): 1, (0, 1): 0, (0, 2): 0,
          (1, 0): 1, (1, 1): 0, (1, 2): 2,
          (2, 0): 2, (2, 1): 2, (2, 2): 1}


def trits10(w):
    t = []
    for _ in range(10):
        t.append(w % 3)
        w //= 3
    return t


def crazy(a, d):
    """crazy_word(a, d): result trit = table[(d_trit, a_trit)]."""
    at, dt = trits10(a), trits10(d)
    r, p = 0, 1
    for i in range(10):
        r += _CRAZY[(dt[i], at[i])] * p
        p *= 3
    return r


def rotr(w):
    return w // 3 + (w % 3) * 19683


def icode(v, a):
    return (v + a) % 94


def legal_byte(v, a):
    return 33 <= v <= 126 and icode(v, a) in OPSET


def bytes_for(op, addr):
    """All printable bytes at `addr` decoding to `op`."""
    base = (op - addr) % 94
    return [v for v in (base, base + 94) if 33 <= v <= 126]


class VM:
    def __init__(self, program, inp):
        self.mem = [0] * MOD
        for i, b in enumerate(program):
            self.mem[i] = b
        for i in range(len(program), MOD):
            self.mem[i] = crazy(self.mem[i - 1], self.mem[i - 2])
        self.a = self.c = self.d = 0
        self.inp = inp
        self.ii = 0
        self.out = []

    def run(self, max_steps=8192, max_out=2, trace=False):
        for step in range(max_steps):
            f = self.mem[self.c]
            if not (33 <= f <= 126):
                return "InvalidRuntimeInstruction", step
            code = icode(f, self.c)
            if trace:
                print(f"  {step:4d} C={self.c:4d} D={self.d:5d} A={self.a:6d} "
                      f"{NAMES.get(code,'?'):5s} m[D]={self.mem[self.d]}")
            if code == JMP:
                self.c = self.mem[self.d]
            elif code == OUT:
                if len(self.out) >= max_out:
                    return "OutputLimitExceeded", step
                self.out.append(self.a % 256)
            elif code == IN:
                if self.ii < len(self.inp):
                    self.a = self.inp[self.ii]
                    self.ii += 1
                else:
                    self.a = 59048
            elif code == ROT:
                v = rotr(self.mem[self.d])
                self.mem[self.d] = v
                self.a = v
            elif code == MOVD:
                self.d = self.mem[self.d]
            elif code == CRZ:
                v = crazy(self.a, self.mem[self.d])
                self.mem[self.d] = v
                self.a = v
            elif code == HALT:
                return "Halted", step
            # NOP and unknown fall through
            w = self.mem[self.c]
            if not (33 <= w <= 126):
                return "InvalidRuntimeInstruction", step
            self.mem[self.c] = ENCIPHER[w - 33]
            self.c = (self.c + 1) % MOD
            self.d = (self.d + 1) % MOD
        return "StepLimitExceeded", max_steps


def check_source(program):
    for a, v in enumerate(program):
        if not legal_byte(v, a):
            return f"byte {v} at {a} decodes to {icode(v, a)} (illegal)"
    return None
