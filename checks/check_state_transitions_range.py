#!/usr/bin/env python3
"""Run check_state_transitions.py across EVERY parent->child edge in a range.

The checker it drives is sound; the range CI handed it was not. The old
workflow fetched depth 2 and compared HEAD~1 against HEAD -- one edge, the
last one. Push five commits where the third silently flips a DONE row back to
OPEN and the fifth tidies it back to DONE, and the only edge examined is
5->HEAD, which is clean. The reopen is in the history, unannotated, and no
reader was ever told. THAT is the defect this driver closes: it walks every
edge in the range, so a silent reopen anywhere in a push is caught even when
both endpoints agree.

MERGE COMMITS ARE INCLUDED, against their first parent. A bad conflict
resolution is a way to reopen a row silently without any authored commit
saying so -- exactly the merge-shaped blindness PROTOCOL.md 7 is about -- so
merges are the last edges that should be skipped.

This driver never re-implements the comparison: it extracts the two ledger
versions and invokes the shipped check_state_transitions.py as a subprocess,
once per edge. If the comparison rule ever changes, it changes in one place.

Exit 0 clean / 1 at least one edge failed / 2 infra.
Usage: check_state_transitions_range.py --base REF --head REF [--ledger F]
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

CHECKER = Path(__file__).parent / "check_state_transitions.py"


def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8")


def _ledger_at(rev: str, ledger: str) -> str | None:
    r = _git(["show", f"{rev}:{ledger}"])
    return r.stdout if r.returncode == 0 else None


def main(argv: list[str]) -> int:
    args = dict(zip(argv[::2], argv[1::2]))
    base, head = args.get("--base"), args.get("--head")
    ledger = args.get("--ledger", "DOCKET.md")
    if not base or not head:
        print("usage: check_state_transitions_range.py --base REF --head REF "
              "[--ledger F]", file=sys.stderr)
        return 2

    if _git(["rev-parse", "--git-dir"]).returncode != 0:
        print("[state-range] ERROR: not inside a git worktree", file=sys.stderr)
        return 2
    if _git(["rev-parse", "--verify", "--quiet", f"{head}^{{commit}}"]).returncode != 0:
        print(f"[state-range] ERROR: --head {head} does not resolve", file=sys.stderr)
        return 2

    # No usable base: a new branch, a force push, or a shallow clone. There is
    # no range to walk. Say that, distinctly from a clean result -- an
    # instrument that did not run has not found anything.
    if set(base.strip()) <= {"0"} or \
            _git(["rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"]).returncode != 0:
        print(f"[state-range] NOT RUN: --base {base} does not resolve (new "
              f"branch, force push, or shallow clone) -- no edges to examine. "
              f"This is not a pass over the range; it is no reading.")
        return 0

    rev = _git(["rev-list", "--reverse", f"{base}..{head}"])
    if rev.returncode != 0:
        print(f"[state-range] ERROR: git rev-list {base}..{head} failed: "
              f"{rev.stderr.strip()}", file=sys.stderr)
        return 2
    commits = [c for c in rev.stdout.split() if c]

    compared = 0
    failed: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        old_p, new_p = Path(td) / "old.md", Path(td) / "new.md"
        for sha in commits:
            new_text = _ledger_at(sha, ledger)
            if new_text is None:
                continue
            parent = _git(["rev-parse", "--verify", "--quiet", f"{sha}^"])
            if parent.returncode != 0:
                continue                      # root commit: no edge
            old_text = _ledger_at(parent.stdout.strip(), ledger)
            if old_text is None:
                continue                      # ledger did not exist yet
            if old_text == new_text:
                continue                      # ledger untouched on this edge
            old_p.write_text(old_text, encoding="utf-8")
            new_p.write_text(new_text, encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(CHECKER), "--old", str(old_p),
                 "--new", str(new_p)],
                capture_output=True, text=True, encoding="utf-8")
            compared += 1
            if r.returncode != 0:
                failed.append(f"[state-range] edge {parent.stdout.strip()[:7]}"
                              f"->{sha[:7]} (exit {r.returncode}):\n"
                              f"{r.stdout.rstrip()}{r.stderr.rstrip()}")

    if failed:
        for f in failed:
            print(f)
        print(f"[state-range] FAIL: {len(failed)} of {compared} ledger-changing "
              f"edge(s) in {base[:7]}..{head[:7]} did not pass. A closed matter "
              f"does not quietly reopen -- not in the last commit of a push, "
              f"and not in the middle of one.")
        return 1

    print(f"[state-range] PASS: {compared} ledger-changing edge(s) examined "
          f"across {len(commits)} commit(s) in {base[:7]}..{head[:7]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
