#!/usr/bin/env bash
# Analyse, recover functions and lift jetsetradio.exe to C with pinned pcrecomp.
# Output goes to work/ (gitignored). The generated C is a derivative of SEGA's code:
# never commit it, never paste it into issues, chats or docs.
# Usage: scripts/02_lift.sh        (~6 min on 2 cores)
# PYTHON picks the interpreter (default python3), e.g. a venv's python.exe on Windows.
set -euo pipefail
py="${PYTHON:-python3}"
here="$(cd "$(dirname "$0")/.." && pwd)"
pc="$here/third_party/pcrecomp"
exe="$here/work/input/jetsetradio.exe"
out="$here/work"
[[ -f "$exe" ]] || { echo "run scripts/00_verify_inputs.sh first" >&2; exit 1; }
[[ -d "$pc/tools" ]] || { echo "run scripts/01_fetch_pcrecomp.sh first" >&2; exit 1; }
mkdir -p "$out/gen"
cd "$pc"
echo "[1/3] pe_analyze";  "$py" tools/pe/pe_analyze.py "$exe" --json "$out/pe_analysis.json" > "$out/pe_analyze.log"
echo "[2/3] disasm32";    "$py" tools/disasm/disasm32.py "$exe" --output "$out/functions.json" > "$out/disasm32.log" 2>&1
grep -E 'Functions:|Byte coverage' "$out/disasm32.log"
echo "[3/3] lift (--all)"; "$py" -m tools "$exe" --all --output "$out/gen/" > "$out/lift.log" 2>&1
grep -E 'Complete!|Generated files' "$out/lift.log"
"$py" -I "$here/tools/unimplemented_report.py" "$out/gen" --json "$out/unimplemented_sites.json"
