#!/usr/bin/env python3
"""FAIL when the ledger's EFFECTIVE merge attribute resolves to union.

Resolved via `git check-attr merge -- <ledger>` -- never by grepping
.gitattributes for a substring. The attribute can arrive through a glob, a
macro, a nested attributes file, or $GIT_DIR/info/attributes; a source-text
grep passes on all of those while the pathology is live. (PROTOCOL.md
section 7.4 -- the guard asserts the resolved behavior, not the config text.)

Exit 0 clean / 1 union detected / 2 infra.
Usage: check_merge_driver.py LEDGER [LEDGER ...]
"""
from __future__ import annotations

import subprocess
import sys


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_merge_driver.py LEDGER [LEDGER ...]", file=sys.stderr)
        return 2
    r = subprocess.run(["git", "check-attr", "merge", "--", *argv],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(f"[merge-driver] ERROR: git check-attr failed: {r.stderr.strip()}",
              file=sys.stderr)
        return 2
    failed = False
    for line in r.stdout.splitlines():
        # format: <path>: merge: <value>
        try:
            path, _, value = (s.strip() for s in line.rsplit(":", 2))
        except ValueError:
            continue
        if value == "union":
            failed = True
            print(f"[merge-driver] FAIL {path}: merge attribute resolves to "
                  f"'union' -- concurrent same-row edits will merge into "
                  f"silent duplicates instead of conflicting")
        else:
            print(f"[merge-driver] {path}: merge -> {value} (ok)")
    if failed:
        print("[merge-driver] the design test: is a concurrent same-key edit a "
              "conflict or a feature? For a ledger it is a conflict. Remove the "
              "union driver for this path.")
        return 1
    print("[merge-driver] PASS: no ledger path resolves to merge=union")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
