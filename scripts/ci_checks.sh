#!/usr/bin/env bash
# CI's Linux job, and the same checks by hand in a sandbox before a commit.
# Needs none of the game's files: it checks what is tracked, pcrecomp's lifter
# at the pin, our Python tools, and our host code.
# Usage: scripts/ci_checks.sh   (after scripts/01_fetch_pcrecomp.sh)
# PYTHON picks the interpreter (default python3). MINGW_CC picks the i686
# mingw-w64 compiler (default i686-w64-mingw32-gcc).
set -euo pipefail
py="${PYTHON:-python3}"
mingw="${MINGW_CC:-i686-w64-mingw32-gcc}"
here="$(cd "$(dirname "$0")/.." && pwd)"
pc="$here/third_party/pcrecomp"
[[ -f "$pc/tools/audit_repo.py" ]] || { echo "run scripts/01_fetch_pcrecomp.sh first" >&2; exit 1; }
cd "$here"
fail=0

# The audit fails on game files, lifted code, or either in history. It only
# flags images under docs/ for review; this project commits no screenshots of
# the game at all, so an image there fails here too.
echo "[1/4] audit of what's tracked"
out="$("$py" "$pc/tools/audit_repo.py" . 2>&1)" || fail=1
echo "$out" | sed -n '/tracked files/,$p'
if grep -q '?? REVIEW' <<<"$out"; then echo "  an image under docs/: screenshots are never committed"; fail=1; fi

echo "[2/4] difftest: pcrecomp's lifter against Unicorn"
( cd "$pc" && RECOMP_CC="$here/scripts/gcc-lm" "$py" tools/lift/difftest.py | tail -1 ) || fail=1
echo "  baseline: 392/392 match hardware, 0 known divergences, 0 failures"

echo "[3/4] our Python tools compile"
"$py" -m py_compile tools/*.py && echo "  $(ls tools/*.py | wc -l) files OK" || fail=1
find tools -name __pycache__ -type d -prune -exec rm -rf {} +

# Our host code, as a 32-bit Windows target, with and without the bring-up
# diagnostics (JSR_TRACE). pcrecomp's native32.c is MSVC inline asm, so it is
# left to the Windows job.
echo "[4/4] mingw-w64 i686 syntax check of src/"
mapfile -t srcs < <(git ls-files 'src/*.c')
for trace in "" "-DRECOMP_TRACE"; do
  if "$mingw" -std=c17 -fsyntax-only -Wall -Werror \
       -Werror=implicit-function-declaration -Werror=implicit-int $trace \
       -I"$pc/runtime/recomp32" -I"$pc/runtime/native32" "${srcs[@]}"; then
    echo "  src/, ${#srcs[@]} .c${trace:+, $trace}: 0 errors, 0 warnings"
  else
    fail=1
  fi
done

[[ $fail -eq 0 ]] && echo "ci_checks: all passed" || { echo "ci_checks: FAILED" >&2; exit 1; }
