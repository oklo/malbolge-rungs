#!/bin/sh
# Run all 256 input bytes of a candidate through the NATIVE evaluator and report
# the exact coverage.  The only honest measurement on a Transform-family rung:
# `verify` draws one seed-derived byte per epoch, so a green verify is a
# sampling event, not a solve.
#
#   ./native_check.sh <program.mal>
#
# Prints "b <input> <got> <want> OK|BAD" per byte and a final count.
B=../../target/release/malbolge-rungs
P="$1"
ok=0
: > /tmp/nc_bad.txt
i=0
while [ $i -lt 256 ]; do
  hx=$(printf '%02x' $i)
  got=$($B execute --program "$P" --input-hex "$hx" 2>/dev/null \
        | tr -d ' \n' | sed -n 's/.*"output":\[\([0-9]*\)\].*/\1/p')
  want=$(( i ^ 81 ))
  if [ "$got" = "$want" ]; then ok=$((ok+1)); else echo "$i" >> /tmp/nc_bad.txt; fi
  i=$((i+1))
done
echo "native coverage: $ok/256"
echo "wrong: $(tr '\n' ' ' < /tmp/nc_bad.txt)"
