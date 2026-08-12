#!/bin/sh
# wait for round-1 runs, pick the best, launch round 2 seeded from it
cd "$(dirname "$0")"
while pgrep -f "hero -N .* -o run_" >/dev/null; do sleep 5; done
best=""; bs=0
for f in run_*.mal; do
  [ -f "$f" ] || continue
  n=$(./hero -N $(wc -c < "$f" | tr -d ' ') -s "$f" -t 0 -o /tmp/z.mal 2>&1 | sed -n 's/^start \([0-9]*\).*/\1/p')
  echo "$f -> $n"
  if [ "$n" -gt "$bs" ]; then bs=$n; best=$f; fi
done
echo "BEST round1: $best = $bs"
cp "$best" round1_best.mal
NB=$(wc -c < "$best" | tr -d ' ')
for r in 21 22 23 24 25 26 27 28; do
  ./hero -N $NB -s round1_best.mal -t 900 -nodes 1500000 -span 9 -T 0.9 -r $r -o run_d_$r.mal > run_d_$r.txt 2> run_d_$r.log &
done
wait
