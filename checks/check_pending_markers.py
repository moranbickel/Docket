#!/usr/bin/env python3
"""Enumerate UB-ID-PENDING rows (Mode B minting), file:line.

Default mode is INFORMATIONAL (exit 0 with the listing): pending rows are a
legal, sanctioned state between filing and reconciliation. In reconciliation
mode (--reconcile) any surviving marker is a failure: the whole point of the
reconciliation pass is that it ends with zero.

Exit 0 clean-or-informational / 1 markers found under --reconcile / 2 infra.
Usage: check_pending_markers.py LEDGER [LEDGER ...] [--reconcile]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ledger import PENDING_ID, parse_rows, zero_parse  # noqa: E402


def main(argv: list[str]) -> int:
    reconcile = "--reconcile" in argv
    ledgers = [a for a in argv if a != "--reconcile"]
    if not ledgers:
        print("usage: check_pending_markers.py LEDGER [--reconcile]", file=sys.stderr)
        return 2
    pending: list[tuple[str, int]] = []
    for arg in ledgers:
        path = Path(arg)
        if not path.is_file():
            print(f"[pending-markers] ERROR: no such ledger: {path}", file=sys.stderr)
            return 2
        if zero_parse(path.read_text(encoding="utf-8")):
            print(f"[pending-markers] ERROR: {path} is non-empty but parses "
                  f"to zero rows -- wrong id prefix or malformed table. "
                  f"'0 pending' over an unreadable ledger is a reading of "
                  f"nothing.")
            return 2
        for row in parse_rows(path):
            if row.id == PENDING_ID:
                pending.append((str(path), row.line_no))

    for f, n in pending:
        print(f"[pending-markers] {f}:{n}: {PENDING_ID}")
    if reconcile and pending:
        print(f"[pending-markers] FAIL: {len(pending)} row(s) still pending -- "
              f"reconciliation assigns every number or it has not happened")
        return 1
    print(f"[pending-markers] {'PASS' if not pending else 'INFO'}: "
          f"{len(pending)} pending row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
