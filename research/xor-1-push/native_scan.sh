#!/bin/sh
# Native ground truth for a Transform-family rung: one `execute` per input byte.
# `verify` draws ONE seed-derived input per epoch, so a program correct on n of
# 256 inputs passes with probability (n/256)^epochs -- the only honest
# measurement is all 256 bytes.  Usage: ./native_scan.sh cand.mal [covered.txt]
B=../../target/release/malbolge-rungs
P="$1"
n=0
: > "${2:-covered_native.txt}"
i=0
while [ $i -lt 256 ]; do
  hx=$(printf '%02x' $i)
  want=$(printf '%02x' $(( i ^ 0x51 )))
  got=$("$B" execute --program "$P" --input-hex "$hx" 2>/dev/null \
        | sed -n 's/.*"output_hex": "\(.*\)".*/\1/p')
  st=$("$B" execute --program "$P" --input-hex "$hx" 2>/dev/null \
        | sed -n 's/.*"status": "\(.*\)".*/\1/p')
  if [ "$got" = "$want" ] && [ "$st" = "Halted" ]; then
    n=$((n+1)); echo "$i" >> "${2:-covered_native.txt}"
  fi
  i=$((i+1))
done
echo "native: $n/256"
