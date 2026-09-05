#!/usr/bin/env python3
"""Post-fold family for L2.R0.xor-1: walk, funnel, then fold against b itself.

  0..8      IN, MOVD x3, CRZ x2 (park m[72]=b), MOVD x3   D = b+1
  ..        NOP x (K0-1)                                  D = b+K0
  ..        CRZ x k       window m[b+K0 .. b+K0+k-1]      acc = w(b)
  ..        MOVD x 7      funnel: D collapses onto root 114
  ..        NOP x 7       D -> 121
  ..        MOVD          D = m[121]+1 = 72               (pin 121:71)
  ..        [op@72, MOVD@73, MOVD@62] x (d-1), op@72      pattern F/S/R
  ..        OUT, HALT     out = acc mod 256

Pattern ops at 72 (m[72] = b at entry): F/S: m72 = crazy(acc, m72), acc = m72;
R: m72 = rotr(m72), acc = m72.  First op must be F.  P = 23 + K0 + k + 3d.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "xor-1-push"))
import mal

MASK = 0x51
L = 256
FUN = json.load(open(os.path.join(HERE, "funnel114.json")))
TREE = {int(a): v for a, v in FUN["pins"].items()}
ROOT = FUN["root"]
EXIT_CELL, EXIT_VAL, EXIT_NOPS = FUN["exit_cell"], FUN["exit_val"], FUN["exit_nops"]
DATA = {40: 122, 62: 71, 71: 121, 72: 121, 73: 61, 123: 70}
ALLPINS = dict(DATA)
ALLPINS.update(TREE)
ALLPINS[EXIT_CELL] = EXIT_VAL
assert len(ALLPINS) == len(DATA) + len(TREE) + 1, "pin collision"


def valid_bytes(addr):
    return sorted(mal.legal_bytes(addr).values())


def code_ops(pat, k, k0):
    d = len(pat)
    ops = [23, 40, 40, 40, 62, 62, 40, 40, 40]
    ops += [68] * (k0 - 1) + [62] * k
    ops += [40] * 7 + [68] * EXIT_NOPS + [40]
    for i, ch in enumerate(pat):
        if i:
            ops += [40, 40]
        ops += [39] if ch == "R" else [62]
    ops += [5, 81]
    return ops


def spec_and_prog(pat, k, k0):
    ops = code_ops(pat, k, k0)
    P = len(ops)
    if P > 64:
        raise ValueError("code reaches funnel zone")
    prog = [None] * L
    for a, op in enumerate(ops):
        b = mal.byte_for(op, a)
        assert b is not None
        prog[a] = b
    for a, v in ALLPINS.items():
        assert a >= P, (a, P)
        assert v in valid_bytes(a), (a, v)
        prog[a] = v
    src_lo, src_hi = k0 + k, 255 + k0 + k          # walk-end cells
    lines = []
    for a in range(L):
        if a < P:
            lines.append(f"X {a} {mal.XLAT2[prog[a] - 33]}")
        elif a in (71, 72):
            lines.append(f"X {a} {DATA[a]}")
        elif a in ALLPINS:
            lines.append(f"F {a} {ALLPINS[a]}")
        else:
            if src_lo <= a <= src_hi:
                allowed = [v for v in valid_bytes(a) if (v + 1) in TREE or v + 1 == ROOT]
                assert allowed, a
                lines.append(f"A {a} {len(allowed)} " + " ".join(map(str, allowed)))
            else:
                lines.append(f"E {a}")
    # dead inputs
    dead = set()
    treeplus = set(TREE) | {EXIT_CELL}
    for b in range(256):
        end = b + k0 + k
        win = range(b + k0, b + k0 + k)
        if end >= L:
            dead.add(b)                            # end cell is crazy fill
        elif end in ALLPINS and not (ALLPINS[end] + 1 in TREE or ALLPINS[end] + 1 == ROOT):
            dead.add(b)                            # pinned non-tree end
        elif end < P:
            e = mal.XLAT2[prog[end] - 33]
            if not (33 <= e <= 126 and (e + 1 in TREE or e + 1 == ROOT)):
                dead.add(b)                        # enciphered code end misses tree
        if any((c in treeplus) or c in (62, 73) for c in win):
            dead.add(b)                            # walk would corrupt funnel/cycle pins
    for b in sorted(dead):
        lines.append(f"Z {b}")
    return "\n".join(lines) + "\n", prog, ops, dead


def solve(pat, k, k0, emit=False):
    spec, prog, ops, dead = spec_and_prog(pat, k, k0)
    sp = os.path.join(HERE, f".spec4_{os.getpid()}.txt")
    open(sp, "w").write(spec)
    cmd = [os.path.join(HERE, "dpk3"), sp, str(k), str(L), str(k0), pat] + (["emit"] if emit else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(sp)
    score = int(r.stderr.strip().split("best=")[1].split("/")[0])
    return score, r.stdout, prog, ops, dead


def patterns(maxd):
    out = ["F"]
    frontier = ["F"]
    for _ in range(maxd - 1):
        frontier = [p + c for p in frontier for c in "SR"]
        out += frontier
    return out


def assemble(pat, k, k0):
    score, stdout, prog, ops, dead = solve(pat, k, k0, emit=True)
    for line in stdout.strip().splitlines():
        a, v = line.split()
        a, v = int(a), int(v)
        if a >= len(ops) and a not in ALLPINS and prog[a] is None:
            prog[a] = v if v in valid_bytes(a) else valid_bytes(a)[0]
    for a in range(L):
        if prog[a] is None:
            prog[a] = valid_bytes(a)[0]
        assert mal.code_of(prog[a], a) in mal.VALID_CODES, (a, prog[a])
    return score, bytes(prog)


def measure(pb):
    ok = []
    for b in range(256):
        out, st, _ = mal.run(list(pb), [b], max_steps=2048)
        if st == "Halted" and out == bytes([b ^ MASK]):
            ok.append(b)
    return ok


if __name__ == "__main__":
    if sys.argv[1] == "sweep":
        maxd = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        best = None
        for pat in patterns(maxd):
            for k in (3, 5):
                for k0 in (1, 2, 4, 6, 8):
                    try:
                        s, _, _, _, dead = solve(pat, k, k0)
                    except (ValueError, AssertionError):
                        continue
                    print(f"pat={pat:6s} k={k} K0={k0} -> {s}/256 (dead {len(dead)})", flush=True)
                    if best is None or s > best[0]:
                        best = (s, pat, k, k0)
        print("BEST", best)
    elif sys.argv[1] == "one":
        pat, k, k0 = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
        score, pb = assemble(pat, k, k0)
        path = os.path.join(HERE, f"cand4_{pat}_k{k}_o{k0}.mal")
        open(path, "wb").write(pb)
        ok = measure(pb)
        print(f"pat={pat} k={k} K0={k0} dp={score}/256 model={len(ok)}/256 -> {path}")
        print("covered:", ok)
