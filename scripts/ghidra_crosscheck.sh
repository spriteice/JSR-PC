#!/usr/bin/env bash
# M3: Ghidra's functions against the catalogue, with every difference explained.
# Usage: scripts/ghidra_crosscheck.sh <Ghidra install dir>   (~4 min; Ghidra 11 or later,
#        and the JDK it asks for in JAVA_HOME)
# Writes work/ghidra/ (the Ghidra project, its exports, the score) and
# data/recovery_crosscheck.tsv, which is committed. Run 00_verify_inputs.sh and
# 01_fetch_pcrecomp.sh first. PYTHON picks the interpreter (default python3).
set -euo pipefail
py="${PYTHON:-python3}"
here="$(cd "$(dirname "$0")/.." && pwd)"
ghidra="${1:?usage: $0 <Ghidra install dir>}"
pc="$here/third_party/pcrecomp"
exe="$here/work/input/jetsetradio.exe"
out="$here/work/ghidra"
headless="$ghidra/support/analyzeHeadless"
[[ -f "$exe" ]] || { echo "run scripts/00_verify_inputs.sh first" >&2; exit 1; }
[[ -d "$pc/tools" ]] || { echo "run scripts/01_fetch_pcrecomp.sh first" >&2; exit 1; }
[[ -x "$headless" ]] || { echo "no $headless: give the Ghidra install dir" >&2; exit 1; }
version="$(sed -n 's/^application.version=//p' "$ghidra/Ghidra/application.properties")"
rm -rf "$out" && mkdir -p "$out/proj"
echo "[1/4] Ghidra $version: analyse the exe, export its functions"
"$headless" "$out/proj" jsr -import "$exe" -scriptPath "$pc/tools/ghidra" \
    -postScript DumpBounds.java "$out/bounds.csv" \
    -postScript ExportFunctions.java "$out" > "$out/analyze.log" 2>&1 \
  || { tail -20 "$out/analyze.log" >&2; exit 1; }
echo "[2/4] the addresses where the two disagree"
"$py" -I "$here/tools/recovery_crosscheck.py" "$exe" --bounds "$out/bounds.csv" \
    --addresses "$out/addresses.txt"
echo "[3/4] Ghidra: what it has at each"
"$headless" "$out/proj" jsr -process jetsetradio.exe -noanalysis -readOnly \
    -scriptPath "$here/tools/ghidra" \
    -postScript RecoveryFacts.java "$out/addresses.txt" "$out/facts.tsv" > "$out/facts.log" 2>&1 \
  || { tail -20 "$out/facts.log" >&2; exit 1; }
echo "[4/4] the score (score_recovery.py) and the list"
"$py" -I "$here/tools/recovery_crosscheck.py" "$exe" --bounds "$out/bounds.csv" \
    --facts "$out/facts.tsv" --source "Ghidra $version" --reference-json "$out/reference.json" \
    -o "$here/data/recovery_crosscheck.tsv" > "$out/crosscheck.log"
gzip -dc "$here/data/functions.json.gz" > "$out/candidate.json"
(cd "$out" && "$py" "$pc/tools/disasm/score_recovery.py" \
    --reference reference.json --candidate candidate.json) | tee "$out/score.txt" | sed -n '1,/F1/p'
tail -1 "$out/crosscheck.log"
