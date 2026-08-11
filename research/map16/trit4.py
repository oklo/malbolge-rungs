#!/usr/bin/env python3
"""The trit-4 forcing law for L2.FM3.xor51-map16, and a sweep of every
configuration that can satisfy it.

Every table operand is a printable byte, 33..126, so its trit 4 is 0 or 1 --
never 2.  The two crazy rows that trit 4 can therefore select,
T[0] = (1,0,0) and T[1] = (1,0,2), AGREE on a = 0 and a = 1.  So once the
accumulator's trit 4 is 0 or 1 it alternates 1,0,1,0,... deterministically and
no choice of table byte can change it.  Only a = 2 has a choice (stay at 2, or
fall into the alternating orbit and never return).

Consequence: for a lane whose dispatched trit 4 is 0 or 1, the final trit 4 is
a function of (that trit, K parity) alone -- it is decided before any table
exists.  The lane's required low value L* = (target - H) mod 256 must have
exactly that trit 4, or the lane is dead no matter what.

The dispatch can apply a per-trit map g = M[w2] o M[w1].  Only eight such maps
exist and only five of them keep the sixteen dispatched addresses distinct at
trit 4, so g4 is a five-way choice, not a free one.  This sweeps
(g4, H, K parity) and reports how many lanes can pass the trit-4 law.
"""
import itertools

INPUTS = [0x02, 0x06, 0x09, 0x30, 0x82, 0x6f, 0xa7, 0xc0,
          0xc5, 0xf6, 0x1c, 0x87, 0xf0, 0x2d, 0x4a, 0x85]
TARGETS = [b ^ 0x51 for b in INPUTS]
RED = [b % 243 for b in INPUTS]
M = [[1, 0, 0], [1, 0, 2], [2, 2, 1]]

# the eight realisable per-trit dispatch maps g = M[w2] o M[w1]
GMAPS = sorted({tuple(M[w2][M[w1][a]] for a in range(3))
                for w1 in range(3) for w2 in range(3)})

# g4 must keep the sixteen addresses distinct
def g4_ok(g):
    seen = set()
    for r in RED:
        a = (r % 81) + 81 * g[r // 81]
        if a in seen:
            return False
        seen.add(a)
    return True

G4 = [g for g in GMAPS if g4_ok(g)]

# reachable high parts H = 243*m: trits 5..9 land in {0,1} after >=1 crazy
# layer with operands < 243, and the initial high trits must fit under the
# 4096-byte program limit (trits 8,9 of K0 would cost 6561 cells), so trits
# 8,9 of the FINAL high part are pinned by parity.
def high_parts(Kodd):
    out = []
    for bits in itertools.product((0, 1), repeat=3):        # trits 5,6,7
        h8 = h9 = 1 if Kodd else 0
        m = bits[0] + 3 * bits[1] + 9 * bits[2] + 27 * h8 + 81 * h9
        out.append(243 * m)
    return sorted(set(out))


def forced_trit4(v, K):
    """final trit 4 given dispatched trit 4 v and walk length K (K >= 1)."""
    if v == 2:
        return None                    # free: stay at 2 or drop out
    return (v + K) % 2                 # 0 -> 1,0,1..  1 -> 0,1,0..


def sweep():
    rows = []
    for g in G4:
        for Kodd in (0, 1):
            for H in high_parts(Kodd):
                ok = 0
                dead = []
                for r, t in zip(RED, TARGETS):
                    L = (t - H) % 256
                    if L > 242:
                        dead.append((r, "range"))
                        continue
                    f = forced_trit4(g[r // 81], 1 if Kodd else 2)
                    if f is None or f == (L // 81) % 3:
                        ok += 1
                    else:
                        dead.append((r, "trit4"))
                rows.append((ok, g, Kodd, H, dead))
    rows.sort(key=lambda r: -r[0])
    print(f"realisable per-trit dispatch maps: {GMAPS}")
    print(f"g4 choices keeping addresses distinct: {G4}\n")
    for ok, g, Kodd, H, dead in rows[:14]:
        print(f"ceiling {ok:2d}/16  g4={g} K {'odd ' if Kodd else 'even'} "
              f"H={H:6d} (H%256={H % 256:3d})  dead={[d[0] for d in dead]}")
    print(f"\nbest ceiling over all {len(rows)} configurations: {rows[0][0]}/16")


if __name__ == "__main__":
    sweep()
