#!/usr/bin/env python3
"""How many target bytes does the constant-output family cover?

Closure of A=0 under {CRZ with a fresh-cell constant, ROT}, projected mod 256.
This says whether the one-CRAZY solve for epoch 0 was luck or a property of the
family: if the projection covers all 256 bytes, any epoch's target is a
straight-line constant away, and only multi-epoch (multi-case) verification
makes this rung hard.
"""
from search import crazy, rotr, operands

ops = list(operands())
seen, frontier, depth_of = {0}, [0], {0: 0}
while frontier:
    nxt = []
    for a in frontier:
        for b in [rotr(a)] + [crazy(a, v) for v in ops]:
            if b not in seen:
                seen.add(b)
                depth_of[b] = depth_of[a] + 1
                nxt.append(b)
    frontier = nxt
bytes_hit = {}
for w in seen:
    bytes_hit.setdefault(w % 256, min(depth_of[w], bytes_hit.get(w % 256, 99)))
print(f"reachable words: {len(seen)} of 59049")
print(f"distinct output bytes: {len(bytes_hit)} of 256")
print("max depth needed over covered bytes:", max(bytes_hit.values()))
missing = sorted(set(range(256)) - set(bytes_hit))
print(f"unreachable target bytes ({len(missing)}):", [hex(m) for m in missing])
