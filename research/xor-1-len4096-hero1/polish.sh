#!/bin/sh
# alternate: tape coordinate-descent sweep, then an exhaustive per-input
# assembly pass that takes every block-local solution that costs nothing.
cd "$(dirname "$0")"
IN=$1; TAG=$2; SECS=$3; R=$4
cp "$IN" /tmp/p_$TAG.mal
i=0
while [ $i -lt 12 ]; do
  ./hero2_fix -N 2305 -s /tmp/p_$TAG.mal -sweep -hot 200 -t $SECS -steps 16 -nodes 3000000 -r $((R+i)) -o /tmp/q_$TAG.mal >/dev/null 2>>polish_$TAG.log
  [ -f /tmp/q_$TAG.mal ] && cp /tmp/q_$TAG.mal /tmp/p_$TAG.mal
  ./hero2_fix -N 2305 -s /tmp/p_$TAG.mal -assemble -steps 16 -fnodes 2000000000 -o /tmp/q_$TAG.mal 2>>polish_$TAG.log | tail -1 >> polish_$TAG.log
  [ -f /tmp/q_$TAG.mal ] && cp /tmp/q_$TAG.mal /tmp/p_$TAG.mal
  cp /tmp/p_$TAG.mal polish_$TAG.mal
  i=$((i+1))
done
