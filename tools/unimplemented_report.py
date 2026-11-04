#!/usr/bin/env python3
"""Report instructions pcrecomp's lift32 could not translate, grouped by function.

Reads the generated C (never shipped; regenerate it with scripts/02_lift.sh) and
prints function name + mnemonic counts only, so the report itself contains no
game code. Writes JSON when --json is given.

    python3 -I tools/unimplemented_report.py work/gen [--json data/unimplemented_sites.json]
"""
import argparse, collections, glob, json, os, re, sys

FUNC = re.compile(r'^\s*(?:static\s+)?void\s+(sub_[0-9A-Fa-f]{8})\s*\(')
MARK = re.compile(r'UNIMPLEMENTED: (\w+)')


def scan(gen_dir):
    hits = collections.Counter()
    for path in sorted(glob.glob(os.path.join(gen_dir, 'recomp_0*.c'))):
        cur = None
        with open(path, errors='replace') as f:
            for line in f:
                m = FUNC.match(line)
                if m:
                    cur = m.group(1)
                u = MARK.search(line)
                if u:
                    hits[(cur, u.group(1))] += 1
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('gen_dir')
    ap.add_argument('--json')
    a = ap.parse_args()
    hits = scan(a.gen_dir)
    total = sum(hits.values())
    funcs = {f for f, _ in hits}
    print(f'unimplemented instructions: {total} in {len(funcs)} functions')
    for (fn, mn), n in sorted(hits.items()):
        print(f'  {fn}  {mn} x{n}')
    if a.json:
        json.dump({'sites': [{'function': fn, 'mnemonic': mn, 'count': n}
                             for (fn, mn), n in sorted(hits.items())]},
                  open(a.json, 'w'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
