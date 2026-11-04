#!/usr/bin/env bash
# Fetch pcrecomp, from the JSR-PC fork, pinned to the commit every number in
# data/baseline.json was measured at.
# Usage: scripts/01_fetch_pcrecomp.sh   (installs Python deps too)
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE=https://github.com/spriteice/pcrecomp
PIN=4bbe6363dcb85deeaafff2f56e7e9a99607fd696
dst="$here/third_party/pcrecomp"
if [[ ! -d "$dst/.git" ]]; then
  git init -q "$dst"
  git -C "$dst" remote add origin "$REMOTE"
fi
git -C "$dst" remote set-url origin "$REMOTE"   # a checkout made before the fork moves over
git -C "$dst" fetch -q --depth 1 origin "$PIN"
git -C "$dst" checkout -q --detach "$PIN"
echo "pcrecomp at $(git -C "$dst" rev-parse --short HEAD)"
python3 -m pip install -q capstone pefile lief unicorn 2>/dev/null \
  || python3 -m pip install -q --break-system-packages capstone pefile lief unicorn
