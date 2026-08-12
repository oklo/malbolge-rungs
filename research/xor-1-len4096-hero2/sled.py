#!/usr/bin/env python3
"""Sled analysis for L2.R0d.xor-1-len4096.

An input b resumes at address 9b+1.  For b = 0,1,2,3 that is 1, 10, 19, 28 --
inside the prologue, whose cells have already executed and been enciphered.
XLAT2 maps 33..126 onto 33..126, so those cells still execute; the VM errors
only on a NON-printable word, and any code outside the eight is `_ => {}`.
This prints, for every prologue address and every source code that could sit
there, what the ENCIPHERED image decodes to -- i.e. what the sled actually runs.
"""
X2 = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
NAMES = {4:'JMP',5:'OUT',23:'IN',39:'ROT',40:'MOVD',62:'CRZ',68:'NOP',81:'HLT'}
CODES = sorted(NAMES)
def byte_for(code, a):
    v = (code - a) % 94
    while v < 33: v += 94
    return v if v <= 126 else None
def enc(byte): return ord(X2[byte-33])
def code_of(w, a): return (w + a) % 94

PROLOGUE = "u'&%:9\"!}}|zzywwvttsqqpnnmkkjhhgf"
print("=== current prologue: source code -> enciphered (sled) code ===")
for a,ch in enumerate(PROLOGUE):
    b0 = ord(ch); c0 = code_of(b0, a); c1 = code_of(enc(b0), a)
    mark = ""
    if a in (1,10,19,28): mark = "  <== SLED ENTRY for b=%d" % ((a-1)//9)
    print("  %2d byte=%3d %-5s -> sled %-5s%s" % (
        a, b0, NAMES.get(c0,'src?%d'%c0), NAMES.get(c1,'nop(%d)'%c1), mark))

print()
print("=== what each source code enciphers to, at the four sled entries ===")
print("     addr  " + "  ".join("%-6s"%NAMES[c] for c in CODES))
for a in (1,10,19,28):
    row = []
    for c in CODES:
        b = byte_for(c, a)
        row.append("%-6s" % (NAMES.get(code_of(enc(b),a), '-') if b else "n/a"))
    print("  b=%d  %2d  " % ((a-1)//9, a) + "  ".join(row))
print("  ('-' = decodes outside the eight codes = runtime NOP = SAFE)")
