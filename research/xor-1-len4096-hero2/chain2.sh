#!/bin/sh
# chain2.sh <tag> <seed.mal> <rng> <steps> <span> <hot> <secs>
# anneal -> assemble -> hunt -> assemble, carrying the best program forward.
T=$1; S=$2; R=$3; ST=$4; SP=$5; HI=$6; SEC=$7
D=runs
./hero7 -s $S      -N 2305 -t $SEC -r $R -steps $ST -span $SP -o $D/c$T.a.mal  > $D/c$T.log 2>&1
./hero7 -s $D/c$T.a.mal -N 2305 -assemble -steps $ST -span $SP -fnodes 30000000 -o $D/c$T.b.mal >> $D/c$T.log 2>&1
./hero7 -s $D/c$T.b.mal -N 2305 -hunt -lo 34 -hot $HI -steps $ST -span $SP -sample 60 -wit 10 \
        -t $SEC -r $R -fnodes 15000000 -o $D/c$T.c.mal >> $D/c$T.log 2>&1
./hero7 -s $D/c$T.c.mal -N 2305 -assemble -steps $ST -span $SP -fnodes 40000000 -o $D/c$T.mal >> $D/c$T.log 2>&1
echo "$T done: $(grep -o 'wrong:.*' $D/c$T.log | tail -1)"
