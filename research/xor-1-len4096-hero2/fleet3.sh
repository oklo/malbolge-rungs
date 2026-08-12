#!/bin/sh
# fleet3.sh -- final push with the JMP-corrected DFS (hero9).
run(){ T=$1; S=$2; R=$3; ST=$4; SP=$5; HI=$6; SE=$7; D=runs
  ./hero9 -s $S -N 2305 -t $SE -r $R -steps $ST -span $SP -o $D/d$T.a.mal > $D/d$T.log 2>&1
  ./hero9 -s $D/d$T.a.mal -N 2305 -assemble -steps $ST -span $SP -fnodes 30000000 -o $D/d$T.b.mal >> $D/d$T.log 2>&1
  ./hero9 -s $D/d$T.b.mal -N 2305 -hunt -lo 34 -hot $HI -steps $ST -span $SP -sample 40 -wit 8 \
          -t $SE -r $R -fnodes 8000000 -o $D/d$T.c.mal >> $D/d$T.log 2>&1
  ./hero9 -s $D/d$T.c.mal -N 2305 -assemble -steps $ST -span $SP -fnodes 40000000 -o $D/d$T.mal >> $D/d$T.log 2>&1
}
A=runs/c2.b.mal; B=runs/c9.b.mal; C=swap_rep.mal
run 1 $A 21 50 12 160 300 & run 2 $A 22 60 12 200 300 & run 3 $A 23 45 12 140 300 &
run 4 $A 24 60  9 180 300 & run 5 $A 25 70 12 160 300 & run 6 $B 26 50 12 160 300 &
run 7 $B 27 60 12 200 300 & run 8 $B 28 45 16 160 300 & run 9 $C 29 60 12 160 300 &
run 10 $C 30 50 12 200 300 & run 11 $A 31 55 16 180 300 & run 12 $A 32 65 12 120 300 &
run 13 $B 33 55 12 240 300 &
wait
echo FLEET3DONE
