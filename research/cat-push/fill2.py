from vm import *
vals={}
for p in range(33,127):
    for q in range(33,127):
        seq=[p,q]
        for _ in range(60): seq.append(crazy(seq[-1],seq[-2]))
        for v in set(seq[20:]): vals.setdefault(v,[]).append((p,q))
print("distinct fill values overall:",len(vals))
for v in sorted(vals):
    print(v, trits(v), len(vals[v]))
