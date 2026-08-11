from vm import *
from collections import Counter
best=None
stats=Counter()
for p in range(33,127):
    for q in range(33,127):
        seq=[p,q]
        for _ in range(400): seq.append(crazy(seq[-1],seq[-2]))
        tail=seq[2:]
        s=set(tail)
        stats[len(s)]+=1
        if 59048 in s and (best is None or tail.index(59048)<best[2]):
            best=(p,q,tail.index(59048))
print("distinct-value-count histogram of fill:",stats.most_common(10))
print("earliest 59048:",best)
# look at one example fill
p,q=33,33
seq=[p,q]
for _ in range(30): seq.append(crazy(seq[-1],seq[-2]))
print("example fill from 33,33:",seq[:20])
# period detection
def period(p,q):
    seq=[p,q]; seen={}
    for i in range(2000):
        k=(seq[-2],seq[-1])
        if k in seen: return seen[k], i-seen[k]
        seen[k]=i
        seq.append(crazy(seq[-1],seq[-2]))
    return None
print("period from 33,33:",period(33,33))
print("period from 126,126:",period(126,126))
