#!/usr/bin/env python3
"""Pre-commit: FAIL when a staged ledger edit re-claims an already-claimed row.

The dominant multi-session failure is two sessions building the same item.
The claim (owner field) is the defense; this check is its teeth. It compares
the STAGED ledger (`git show :LEDGER`) against HEAD's (`git show HEAD:LEDGER`)
and rejects any row whose owner changes from one non-'-' value to a DIFFERENT
non-'-' value. Releasing (owner -> '-') and first claims ('-' -> session) pass.

REPO ROOT RESOLUTION (load-bearing): resolved from the COMMITTING WORKTREE via
`git rev-parse --show-toplevel` at hook time -- NEVER from an environment
variable. With several worktrees live, an env var set by one session points
another session's hook at the wrong ledger, and the hook passes while
guarding nothing.

Exit 0 clean / 1 collision / 2 infra. Initial commit (no HEAD) passes.
Usage: check_claim_collision.py [LEDGER-RELPATH]   (default: DOCKET.md)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ledger import parse_rows_text  # noqa: E402


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8")


def main(argv: list[str]) -> int:
    ledger = argv[0] if argv else "DOCKET.md"

    top = _git(["rev-parse", "--show-toplevel"], Path.cwd())
    if top.returncode != 0:
        print("[claim-collision] ERROR: not inside a git worktree", file=sys.stderr)
        return 2
    root = Path(top.stdout.strip())

    staged = _git(["show", f":{ledger}"], root)
    if staged.returncode != 0:
        print(f"[claim-collision] PASS: {ledger} not staged in this commit")
        return 0
    head = _git(["show", f"HEAD:{ledger}"], root)
    if head.returncode != 0:
        print("[claim-collision] PASS: no HEAD version (initial commit)")
        return 0

    if staged.stdout.strip() and not parse_rows_text(staged.stdout):
        print(f"[claim-collision] ERROR: staged {ledger} is non-empty but "
              f"parses to zero rows -- wrong id prefix or malformed table. "
              f"Refusing to bless a commit over a ledger the check cannot read.")
        return 2

    old = {r.id: r for r in parse_rows_text(head.stdout) if r.id != "UB-ID-PENDING"}
    collisions = []
    for row in parse_rows_text(staged.stdout):
        prev = old.get(row.id)
        if prev is None:
            continue
        if prev.owner not in ("-", "") and row.owner not in ("-", "") \
                and prev.owner != row.owner:
            collisions.append((row.id, prev.owner, row.owner))

    if collisions:
        for ub, was, now in collisions:
            print(f"[claim-collision] FAIL {ub}: owned by '{was}', this commit "
                  f"re-claims it for '{now}'")
        print("[claim-collision] a claimed row is someone's live work. "
              "Coordinate, or wait for the release (owner -> '-') on the record.")
        return 1
    print("[claim-collision] PASS: no staged re-claim of a claimed row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
