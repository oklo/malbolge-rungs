#!/bin/sh
# fleet5.sh -- hero3's window search (descending decomposition) at CHEAP DFS
# settings.  hero2 showed step cap >= 45 only matters for the sled inputs
# (0,1,3); for tape quality (26,16) and (60,27) both returned 249.  So buy
# probes, not depth: steps 34-40, span 9-10, small node caps.
D=runs
w(){ ./hero10 -s $2 -N 2305 -window -lo $3 -hot $4 -steps $5 -span $6 \
       -anodes 1500000 -wit 8 -t $7 -r $8 -o $D/x$1.mal > $D/x$1.log 2>&1; }
w 1  cand2.mal 34 190 36  9 1800 301 &
w 2  cand2.mal 34 145 40  9 1800 302 &
w 3  cand2.mal 34 100 36  9 1800 303 &
w 4  cand2.mal 34 190 34 10 1800 304 &
w 5  cand2.mal 62 145 38  9 1800 305 &
w 6  cand2.mal 34 145 36  9 1800 306 &
w 7  swap_rep.mal 34 190 36 9 1800 307 &
w 8  cand2.mal 34 120 45  9 1800 308 &
w 9  cand2.mal 34 190 40  9 1800 309 &
w 10 cand2.mal 34 145 34  9 1800 310 &
wait
echo FLEET5DONE
