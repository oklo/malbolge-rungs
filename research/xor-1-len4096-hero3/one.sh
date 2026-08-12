#!/bin/sh
# one.sh <prog> <i> -> prints i if wrong
B=/Users/greglaughlin/Projects/attempts/survey/malbolge-rungs/target/release/malbolge-rungs
hx=$(printf "%02x" $2)
got=$($B execute --program "$1" --input-hex $hx 2>/dev/null | tr -d " \n" | sed -n 's/.*"output":\[\([0-9]*\)\].*/\1/p')
want=$(( $2 ^ 81 ))
[ "$got" = "$want" ] || echo "$2"
