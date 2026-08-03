#!/usr/bin/env python3
"""FAIL when the same UB-ID appears on two ledger rows.

Exit 0 clean / 1 duplicates found / 2 usage or unreadable ledger.
Usage: check_duplicate_ids.py LEDGER [LEDGER ...]
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ledger import parse_rows  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_duplicate_ids.py LEDGER [LEDGER ...]", file=sys.stderr)
        return 2
    failed = False
    for arg in argv:
        path = Path(arg)
        if not path.is_file():
            print(f"[duplicate-ids] ERROR: no such ledger: {path}", file=sys.stderr)
            return 2
        rows = parse_rows(path)
        counts = Counter(r.id for r in rows if r.id != "UB-ID-PENDING")
        for ub, n in sorted(counts.items()):
            if n > 1:
                failed = True
                lines = [str(r.line_no) for r in rows if r.id == ub]
                print(f"[duplicate-ids] FAIL {path}: {ub} appears {n} times "
                      f"(lines {', '.join(lines)})")
    if failed:
        print("[duplicate-ids] one number, one matter. Merge the rows; never "
              "renumber by hand-picking a fresh id outside the minting mode.")
        return 1
    print("[duplicate-ids] PASS: every id appears exactly once")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
