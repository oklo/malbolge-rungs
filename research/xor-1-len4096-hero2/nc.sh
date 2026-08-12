#!/bin/sh
# Parallel all-256 native check. Usage: ./nc.sh <program.mal>
D=$(dirname "$0")
P=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
seq 0 255 | xargs -P 14 -n1 "$D/one.sh" "$P" | sort -n > /tmp/nc_bad.txt
n=$(wc -l < /tmp/nc_bad.txt | tr -d " ")
echo "native coverage: $((256-n))/256"
echo "wrong: $(tr "\n" " " < /tmp/nc_bad.txt)"
