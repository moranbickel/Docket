#!/usr/bin/env python3
"""FAIL when a DONE/WONTFIX row changed state with no written reason.

Regressions reopen loudly, never silently: any transition OUT of DONE or
WONTFIX must add a dated `reopened:` annotation to that row's notes in the
same change (PROTOCOL.md section 5). This check compares two versions of the
ledger -- CI wires them from git (see ledger-ci.yml), so the check itself
stays a pure two-file diff with no git dependency.

Exit 0 clean / 1 silent reopen / 2 usage.
Usage: check_state_transitions.py --old OLD_FILE --new NEW_FILE
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ledger import PENDING_ID, parse_rows, unreadable_rows  # noqa: E402

TERMINAL = ("DONE", "WONTFIX")
TOKEN = "reopened:"


def main(argv: list[str]) -> int:
    args = dict(zip(argv[::2], argv[1::2]))
    old_p, new_p = args.get("--old"), args.get("--new")
    if not old_p or not new_p:
        print("usage: check_state_transitions.py --old OLD --new NEW", file=sys.stderr)
        return 2
    old_f, new_f = Path(old_p), Path(new_p)
    if not old_f.is_file() or not new_f.is_file():
        print("[state-transitions] ERROR: old/new ledger file missing", file=sys.stderr)
        return 2
    for label, f in (("old", old_f), ("new", new_f)):
        bad = unreadable_rows(f.read_text(encoding="utf-8"))
        if bad:
            print(f"[state-transitions] ERROR: {label} ledger {f} has "
                  f"{len(bad)} unreadable row(s) at line(s) "
                  f"{', '.join(map(str, bad))} -- a silent reopen on one of "
                  f"them would compare as absent on both sides.")
            return 2

    old = {r.id: r for r in parse_rows(old_f) if r.id != PENDING_ID}
    new = {r.id: r for r in parse_rows(new_f) if r.id != PENDING_ID}

    silent = []
    for ub, prev in old.items():
        cur = new.get(ub)
        if cur is None or prev.state not in TERMINAL:
            continue
        if cur.state != prev.state and TOKEN not in cur.notes:
            silent.append((ub, prev.state, cur.state))

    if silent:
        for ub, was, now in silent:
            print(f"[state-transitions] FAIL {ub}: {was} -> {now} with no "
                  f"'{TOKEN}' annotation in notes")
        print("[state-transitions] a closed matter does not quietly reopen. "
              "Add a dated 'reopened: <why>' note in the same edit.")
        return 1
    print("[state-transitions] PASS: no silent transition out of DONE/WONTFIX")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
