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
# The names that go into the lifted C come from data/function_map.tsv, and only from it.
# It is rebuilt from the exe first (2 s) and must match the committed one.
echo "[1/5] function map"
"$py" -I "$here/tools/map_functions.py" "$exe" -o "$out/function_map.tsv" \
      --known "$out/known_names.txt" > "$out/map_functions.log"
cmp -s "$out/function_map.tsv" "$here/data/function_map.tsv" || {
  echo "data/function_map.tsv is out of date: run tools/map_functions.py and commit it" >&2; exit 1; }
cd "$pc"
echo "[2/5] pe_analyze";  "$py" tools/pe/pe_analyze.py "$exe" --json "$out/pe_analysis.json" > "$out/pe_analyze.log"
echo "[3/5] disasm32";    "$py" tools/disasm/disasm32.py "$exe" --output "$out/functions.json" > "$out/disasm32.log" 2>&1
grep -E 'Functions:|Byte coverage' "$out/disasm32.log"
echo "[4/5] lift (--all)"; "$py" -m tools "$exe" --all --output "$out/gen/" > "$out/lift.log" 2>&1
grep -E 'Complete!|Generated files' "$out/lift.log"
"$py" -I "$here/tools/unimplemented_report.py" "$out/gen" --json "$out/unimplemented_sites.json"
# sub_XXXXXXXX becomes the map's name (njCnkDrawModel), with a header above each function.
echo "[5/5] names (name_lift --known-only)"
"$py" tools/cpp/rtti.py "$exe" -o "$out/rtti.json" > "$out/rtti.log"
"$py" tools/lift/name_lift.py "$exe" --gen "$out/gen" --rtti "$out/rtti.json" \
      --known-file "$out/known_names.txt" --known-only > "$out/name_lift.log"
tail -1 "$out/name_lift.log"
