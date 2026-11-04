#!/usr/bin/env bash
# Check a lift against data/baseline.json: syntax-check every generated file and run
# pcrecomp's differential lifter test (lifted C vs Unicorn).
# Usage: scripts/03_check.sh
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
pc="$here/third_party/pcrecomp"
gen="$here/work/gen"
inc="$pc/runtime/recomp32"
[[ -f "$gen/recomp_dispatch.c" ]] || { echo "run scripts/02_lift.sh first" >&2; exit 1; }

echo "[1/2] gcc -fsyntax-only on $(ls "$gen"/*.c | wc -l) files"
errs=0
for f in "$gen"/*.c; do
  if ! gcc -fsyntax-only -w -I"$inc" -I"$gen" "$f" > "$f.chk" 2>&1; then
    n=$(grep -c 'error:' "$f.chk" || true); echo "  $(basename "$f"): $n errors"; errs=$((errs+n))
  fi
done
echo "  syntax errors: $errs (baseline 0)"

echo "[2/2] difftest"
( cd "$pc" && RECOMP_CC="$here/scripts/gcc-lm" python3 tools/lift/difftest.py | tail -1 )
echo "  baseline: 392/392 match hardware, 0 known divergences, 0 failures"
[[ $errs -eq 0 ]]
