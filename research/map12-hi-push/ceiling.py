"""Per-config lane-liveness ceiling for map12-hi under printable-operand tails.

Closed form derived from ubound.py/jreach.py and checked against crazy_reach:

  In the tail the accumulator starts at a = J(x) and every CRAZY operand is a
  printable byte (33..126), so every operand has trits 5..9 = 0 and trit4 in
  {0,1}.  Writing s = trit5(J), t4 = trit4 of the final accumulator, n = number
  of CRAZY ops and r = t0+3t1+9t2+27t3 in [0,80]:

     n odd :  a = 29160 + 243*(1-s) + 81*t4 + r
     n even:  a =         243*s     + 81*t4 + r

  so the output byte a%256 is confined to an 81-wide window selected by t4.
  Because every printable operand has trit4 in {0,1}, only g0=(1,0,0) and
  g1=(1,0,2) act on trit4, and BOTH restrict to the swap 0<->1 on {0,1}.
  Hence trit4 of the accumulator can only ever be 2 if trit4(J) is already 2,
  and h4(0) != h4(1) for every dispatch chain.

This script confirms that closed form against the brute-force reach sets and
then scores every separating config.
"""
from __future__ import annotations
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from research.map12hi import base  # noqa: E402
from jreach import crazy_reach  # noqa: E402
from ubound import reach_outputs  # noqa: E402

INPUTS = [0xA5, 0xE0, 0x90, 0x9C, 0x84, 0xA1, 0xBD, 0xC8, 0xBE, 0xF9, 0x86, 0xDD]
TGT = {x: x ^ 0x51 for x in INPUTS}
base.INPUTS = INPUTS
base.TGT = TGT
HOLE = set(range(0x9A, 0xD1))

# ---- closed-form window model ------------------------------------------
def window_reach(J):
    """Output bytes reachable as CRAZY^n(J), printable operands, closed form."""
    s = (J // 243) % 3
    t4J = (J // 81) % 3
    outs = {J % 256}
    for n in range(1, 9):
        # trit4 orbit: swap on {0,1}; 2 survives only under g1, and 2 can also
        # fall to 0 under g0, so from t4J=2 the reachable set at step n is
        # {2} plus the swap-orbit entered by dropping to 0 at some earlier step.
        if t4J == 2:
            t4s = {2, 0 if n % 2 == 1 else 1, 1 if n % 2 == 1 else 0}
        else:
            t4s = {(t4J ^ 1) if n % 2 else t4J}
        hi = 29160 if n % 2 else 0
        s_n = (1 - s) if n % 2 else s
        if s == 2:
            s_n = 0 if n % 2 else 1
        for t4 in t4s:
            for r in range(81):
                outs.add((hi + 243 * s_n + 81 * t4 + r) % 256)
    return outs


if __name__ == "__main__":
    # sanity: closed form must contain the brute-forced reach set
    bad = 0
    for J in list(range(0, 300)) + list(range(400, 500)):
        bf, cf = crazy_reach(J, 5), window_reach(J)
        if not bf <= cf:
            bad += 1
            if bad < 4:
                print(f"  MISMATCH J={J}: brute-force has {sorted(bf-cf)[:6]} not in closed form")
    print(f"closed-form check over 400 landings: {bad} landings where brute force escapes the model")

    ROTREACH = reach_outputs(0, depth=4) - crazy_reach(0, 4)  # ROT-seeded part
    ROTREACH = set(range(256)) - HOLE
    cfgs = base.enum_configs()
    scored = []
    for i, (cps, ts, J) in enumerate(cfgs):
        live = [x for x in INPUTS
                if TGT[x] not in HOLE or TGT[x] in crazy_reach(J[x], 5)]
        scored.append((len(live), i, cps, ts, J, live))
    scored.sort(key=lambda r: -r[0])
    from collections import Counter
    print(f"\n{len(cfgs)} configs; per-config lane-liveness ceiling distribution: "
          f"{dict(Counter(r[0] for r in scored))}")
    for n, i, cps, ts, J, live in scored[:6]:
        dead = [x for x in INPUTS if x not in live]
        print(f"  cfg{i:3d} ceiling={n}/12 cps={cps} ts={ts}")
        print(f"        landings={sorted(J.values())}  dead={[hex(x) for x in dead]}")

    # the two-lane impossibility, stated directly
    print("\ntrit4 of the four in-hole inputs:")
    for x in (0xE0, 0x90, 0x9C, 0xF9):
        print(f"  {x:#04x} -> target {TGT[x]:#04x}  trit4(input)={(x//81)%3}")
    print("  every dispatch chain acts on trit4 by g0=(1,0,0) or g1=(1,0,2);")
    print("  both are the swap 0<->1 on {0,1}, so h4(0) != h4(1) always,")
    print("  so 0x90 (trit4=1) and 0xf9 (trit4=0) can NEVER both land on trit4=2.")
