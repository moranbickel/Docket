#!/usr/bin/env python3
"""FAIL when a commit advances a ledger row without citing its id, or cites
an id that was never minted.

PROTOCOL.md 3.1: every commit that ADVANCES an item MUST carry the item's id
verbatim in the commit message. 3.3: a citation to a number with no row
behind it is a detectable class. `check_phantom_ids.py` enforces 3.3 across
tracked FILES; commit messages are not files, so they were the one citation
surface with no check on them. This is that check.

TWO ARMS, one pass over the range:
  1. ADVANCING COMMITS CITE. A commit that modifies an existing row -- its
     state, owner, or notes -- must name at least one of the ids it moved.
  2. CITED IDS EXIST. Every `UB-<n>` in the message must have a row in the
     ledger at --head.

FILING IS NOT ADVANCING, and this is the rule, not a convenience. Under Mode
B a session files with `UB-ID-PENDING`, which has no number to cite; under
either mode, adding a row is not moving one. So a commit that only ADDS rows
owes no citation -- including the commit that installs the starter ledger,
which would otherwise hand every adopter a red first build. Modifying a row
that already existed is what 3.1 governs.

MERGES ARE EXEMPT: their messages are generated, and everything a merge
carries was already judged on the branch that authored it.

Exit 0 clean (or nothing in range) / 1 violation / 2 infra.
Usage: check_commit_ids.py --base REF --head REF [--ledger DOCKET.md]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ledger import CITE_RE, ID_PREFIX, PENDING_ID, parse_rows_text, unreadable_rows  # noqa: E402

ZERO = "0" * 40


def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8")


def _ledger_at(rev: str, ledger: str) -> str | None:
    r = _git(["show", f"{rev}:{ledger}"])
    return r.stdout if r.returncode == 0 else None


def _rows_by_id(text: str) -> dict[str, str]:
    return {r.id: r.raw.strip() for r in parse_rows_text(text)
            if r.id != PENDING_ID}


def main(argv: list[str]) -> int:
    args = dict(zip(argv[::2], argv[1::2]))
    base, head = args.get("--base"), args.get("--head")
    ledger = args.get("--ledger", "DOCKET.md")
    if not base or not head:
        print("usage: check_commit_ids.py --base REF --head REF [--ledger F]",
              file=sys.stderr)
        return 2

    if _git(["rev-parse", "--git-dir"]).returncode != 0:
        print("[commit-ids] ERROR: not inside a git worktree", file=sys.stderr)
        return 2

    if _git(["rev-parse", "--verify", "--quiet", f"{head}^{{commit}}"]).returncode != 0:
        print(f"[commit-ids] ERROR: --head {head} does not resolve", file=sys.stderr)
        return 2

    # A brand-new branch / force push gives an all-zero or absent base. There
    # is no range to walk, so nothing is examined -- say exactly that. "Did
    # not run" and "found nothing wrong" are different claims.
    if set(base.strip()) <= {"0"} or \
            _git(["rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"]).returncode != 0:
        print(f"[commit-ids] NOT RUN: --base {base} does not resolve (new "
              f"branch, force push, or shallow clone) -- no commit range to "
              f"examine. This is not a pass over the commits; it is no reading.")
        return 0

    head_text = _ledger_at(head, ledger)
    if head_text is None:
        print(f"[commit-ids] ERROR: {ledger} does not exist at {head}",
              file=sys.stderr)
        return 2
    bad = unreadable_rows(head_text)
    if bad:
        print(f"[commit-ids] ERROR: {ledger} at {head} has {len(bad)} "
              f"unreadable row(s) at line(s) {', '.join(map(str, bad))} -- an "
              f"id minted on one of them would read as a phantom citation. "
              f"Refusing to report success.")
        return 2
    minted = set(_rows_by_id(head_text))

    rev = _git(["rev-list", "--reverse", "--no-merges", f"{base}..{head}"])
    if rev.returncode != 0:
        print(f"[commit-ids] ERROR: git rev-list {base}..{head} failed: "
              f"{rev.stderr.strip()}", file=sys.stderr)
        return 2
    commits = [c for c in rev.stdout.split() if c]

    failures: list[tuple[str, str]] = []
    examined = 0
    for sha in commits:
        new_text = _ledger_at(sha, ledger)
        if new_text is None:
            continue                      # ledger not present at this commit
        parent = _git(["rev-parse", "--verify", "--quiet", f"{sha}^"])
        old_text = _ledger_at(parent.stdout.strip(), ledger) \
            if parent.returncode == 0 else None
        if old_text is None:
            continue                      # root commit, or ledger newly added
        if old_text == new_text:
            continue                      # ledger untouched by this commit
        examined += 1

        old_rows, new_rows = _rows_by_id(old_text), _rows_by_id(new_text)
        advanced = {ub for ub in old_rows.keys() & new_rows.keys()
                    if old_rows[ub] != new_rows[ub]}

        msg = _git(["log", "-1", "--format=%B", sha]).stdout
        cited = {f"{ID_PREFIX}{m.group(1)}" for m in CITE_RE.finditer(msg)}
        short = sha[:7]

        if advanced and not (advanced & cited):
            failures.append((short, f"advances {', '.join(sorted(advanced))} "
                                    f"but its message cites "
                                    f"{', '.join(sorted(cited)) or 'no id'}"))
        for ub in sorted(cited - minted):
            failures.append((short, f"cites {ub} -- no such row in {ledger} "
                                    f"at {head}"))

    if failures:
        for short, why in failures:
            print(f"[commit-ids] FAIL {short}: {why}")
        print("[commit-ids] the number travels: a commit that moves a row "
              "names it, and a number in a message has a row behind it.")
        return 1

    print(f"[commit-ids] PASS: {examined} ledger-touching commit(s) in "
          f"{base[:7]}..{head[:7]} cite what they advance "
          f"({len(commits)} non-merge commit(s) in range)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
