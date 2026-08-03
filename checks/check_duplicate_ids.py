#!/usr/bin/env python3
"""FAIL when the same UB-ID appears on two rows -- within one ledger or
ACROSS every ledger passed (PROTOCOL section 9: the ID space spans shards,
so `check_duplicate_ids.py DOCKET-2025.md DOCKET.md` counts the whole set).

A non-empty ledger that parses to ZERO rows (renamed prefix, mangled table)
exits 2 loudly instead of printing PASS: a run over nothing has measured
nothing, and a silent success over an unparseable ledger is exactly the
"checking something else" failure the README's origin story describes.

Exit 0 clean / 1 duplicates found / 2 usage, unreadable ledger, or
zero-parse ambiguity.
Usage: check_duplicate_ids.py LEDGER [LEDGER ...]
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ledger import parse_rows  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_duplicate_ids.py LEDGER [LEDGER ...]", file=sys.stderr)
        return 2

    sites: dict[str, list[str]] = defaultdict(list)   # id -> ["file:line", ...]
    total_rows = 0
    for arg in argv:
        path = Path(arg)
        if not path.is_file():
            print(f"[duplicate-ids] ERROR: no such ledger: {path}", file=sys.stderr)
            return 2
        rows = parse_rows(path)
        if not rows and path.read_text(encoding="utf-8").strip():
            print(f"[duplicate-ids] ERROR: {path} is non-empty but parses to "
                  f"zero rows -- wrong id prefix or malformed table. Refusing "
                  f"to report success over nothing.")
            return 2
        total_rows += len(rows)
        for r in rows:
            if r.id != "UB-ID-PENDING":
                sites[r.id].append(f"{path}:{r.line_no}")

    if total_rows == 0:
        print("[duplicate-ids] ERROR: zero rows parsed across all ledgers -- "
              "nothing was checked.")
        return 2

    dupes = {ub: where for ub, where in sites.items() if len(where) > 1}
    if dupes:
        for ub in sorted(dupes):
            print(f"[duplicate-ids] FAIL: {ub} appears {len(dupes[ub])} times "
                  f"({', '.join(dupes[ub])})")
        print("[duplicate-ids] one number, one matter -- within a ledger and "
              "across shards alike. Merge the rows; never renumber by "
              "hand-picking a fresh id outside the minting mode.")
        return 1
    print(f"[duplicate-ids] PASS: every id appears exactly once "
          f"({total_rows} rows across {len(argv)} ledger(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
