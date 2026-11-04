#!/usr/bin/env bash
# Verify the user-supplied game files are the exact build this package was made from.
# Usage: scripts/00_verify_inputs.sh /path/to/Jet\ Set\ Radio
# Copies the four files into work/input/ (gitignored) after the hashes match.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
game="${1:?usage: $0 <game install dir>}"
mkdir -p "$here/work/input"
fail=0
while read -r sum name; do
  src="$game/$name"
  if [[ ! -f "$src" ]]; then echo "MISSING  $name"; fail=1; continue; fi
  got=$(sha256sum "$src" | cut -d' ' -f1)
  if [[ "$got" == "$sum" ]]; then echo "OK       $name"; cp "$src" "$here/work/input/$name"
  else echo "MISMATCH $name  (got $got)"; fail=1; fi
done < "$here/data/inputs.sha256"
if [[ $fail -ne 0 ]]; then
  echo "Inputs do not match the Steam build of 2013-03-12 this package targets." >&2
  echo "A different build needs its own function catalog and baseline; do not mix them." >&2
  exit 1
fi
echo "All inputs verified -> work/input/"
