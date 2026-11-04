#!/usr/bin/env bash
# Fetch pcrecomp pinned to the commit every number in data/baseline.json was measured at.
# Usage: scripts/01_fetch_pcrecomp.sh   (installs Python deps too)
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
PIN=ef3f0da6e08a8eb7a3f869273f3df071ca8d7373
dst="$here/third_party/pcrecomp"
if [[ ! -d "$dst/.git" ]]; then
  git init -q "$dst"
  git -C "$dst" remote add origin https://github.com/sp00nznet/pcrecomp
fi
git -C "$dst" fetch -q --depth 1 origin "$PIN"
git -C "$dst" checkout -q --detach "$PIN"
echo "pcrecomp at $(git -C "$dst" rev-parse --short HEAD)"
python3 -m pip install -q capstone pefile lief unicorn 2>/dev/null \
  || python3 -m pip install -q --break-system-packages capstone pefile lief unicorn
