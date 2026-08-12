#!/bin/sh
# fleet4.sh -- hero2's would_try_next #1: full pipeline on the SWAPPED prologue
# with the JMP-corrected DFS at step cap >= 45.  Seeds: cand2 (247) and swap_rep.
run(){ T=$1; S=$2; R=$3; ST=$4; SP=$5; HI=$6; SE=$7; D=runs
  ./hero9 -s $S -N 2305 -t $SE -r $R -steps $ST -span $SP -o $D/f$T.a.mal > $D/f$T.log 2>&1
  ./hero9 -s $D/f$T.a.mal -N 2305 -assemble -steps $ST -span $SP -fnodes 40000000 -o $D/f$T.b.mal >> $D/f$T.log 2>&1
  ./hero9 -s $D/f$T.b.mal -N 2305 -hunt -lo 34 -hot $HI -steps $ST -span $SP -sample 60 -wit 10 \
          -t $SE -r $R -fnodes 12000000 -o $D/f$T.c.mal >> $D/f$T.log 2>&1
  ./hero9 -s $D/f$T.c.mal -N 2305 -assemble -steps $ST -span $SP -fnodes 60000000 -o $D/f$T.mal >> $D/f$T.log 2>&1
  echo "f$T done"
}
A=cand2.mal; B=swap_rep.mal
run 1 $A 101 50 12 200 900 & run 2 $A 102 60 14 240 900 & run 3 $A 103 45 12 160 900 &
run 4 $A 104 70 12 200 900 & run 5 $A 105 55 16 280 900 & run 6 $A 106 60 10 200 900 &
run 7 $B 107 50 12 200 900 & run 8 $B 108 60 14 240 900 & run 9 $A 109 65 12 180 900 &
run 10 $A 110 55 12 320 900 & run 11 $A 111 45 16 200 900 &
wait
echo FLEET4DONE
