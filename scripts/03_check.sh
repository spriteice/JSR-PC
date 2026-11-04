#!/usr/bin/env bash
# Check a lift against data/baseline.json: syntax-check every generated file and run
# pcrecomp's differential lifter test (lifted C vs Unicorn).
# Usage: scripts/03_check.sh
# PYTHON picks the interpreter (default python3).
set -euo pipefail
py="${PYTHON:-python3}"
here="$(cd "$(dirname "$0")/.." && pwd)"
pc="$here/third_party/pcrecomp"
gen="$here/work/gen"
inc="$pc/runtime/recomp32"
[[ -f "$gen/recomp_dispatch.c" ]] || { echo "run scripts/02_lift.sh first" >&2; exit 1; }

# No -w: it also silences -Werror= diagnostics. A call with no declaration is an
# error here because MSVC rejects the definition that follows it (C2371).
echo "[1/2] gcc -fsyntax-only on $(ls "$gen"/*.c | wc -l) files"
errs=0; warns=0
for f in "$gen"/*.c; do
  gcc -fsyntax-only -Werror=implicit-function-declaration -Werror=implicit-int \
      -I"$inc" -I"$gen" "$f" > "$f.chk" 2>&1 || true
  n=$(grep -c 'error:' "$f.chk" || true); w=$(grep -c 'warning:' "$f.chk" || true)
  [[ $n -eq 0 && $w -eq 0 ]] || echo "  $(basename "$f"): $n errors, $w warnings"
  errs=$((errs+n)); warns=$((warns+w))
done
echo "  syntax errors: $errs, warnings: $warns (baseline 0 and 0)"

echo "[2/2] difftest"
( cd "$pc" && RECOMP_CC="$here/scripts/gcc-lm" "$py" tools/lift/difftest.py | tail -1 )
echo "  baseline: 392/392 match hardware, 0 known divergences, 0 failures"
[[ $errs -eq 0 && $warns -eq 0 ]]
