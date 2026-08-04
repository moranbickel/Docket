#!/usr/bin/env python3
"""FAIL when a DONE row does not cite a commit that exists AND is reachable.

PROTOCOL.md 6.1: a row moving to DONE MUST name, in `notes`, the artifact
that closed it -- at minimum one commit hash. 6.2: a closure that points at
nothing ("done", "fixed", "handled") is not a closure. This check makes both
mechanical.

For every DONE row it requires at least one hex token in `notes` that
(a) resolves to a commit object here (`git cat-file -e <sha>^{commit}`) and
(b) is an ancestor of HEAD (`git merge-base --is-ancestor`). WONTFIX is
EXEMPT: a row closed as "not doing this" has no closing commit to cite, by
definition.

AT LEAST ONE, not every. Closure notes legitimately carry hashes from OTHER
repositories -- a sibling project's commit, an upstream fix -- which cannot
resolve here and must not fail the build. One local, resolving, reachable
commit is what the protocol asks for; the rest is context.

REACHABILITY IS THE HALF THAT MATTERS. A rewritten or dropped branch leaves
commit objects alive in the object database that no longer sit in the
project's history: `cat-file -e` still finds them, and a closure citing one
points at a commit no reader can reach. This repository learned it the
expensive way -- a history rewrite before publication dangled every closure
citation it had, and re-pointing them was hand work. Existence alone would
have reported all of them fine.

SHALLOW CLONES: a truncated history makes reachable commits look unreachable.
That is a defect in the checkout, not in the ledger, so it exits 2 (infra)
and says so -- never 1. CI must use fetch-depth: 0.

Exit 0 clean / 1 uncited or dangling closure / 2 infra.
Usage: check_closure_references.py LEDGER [LEDGER ...] [--head REF]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ledger import PENDING_ID, parse_rows, unreadable_rows  # noqa: E402

# A candidate commit citation: 7-40 hex characters standing as their own word.
# Deliberately permissive -- a token that is not a commit simply fails to
# resolve, and only costs a row its pass if NO token in the row resolves.
HASH_RE = re.compile(r"\b[0-9a-fA-F]{7,40}\b")

CLOSING_STATES = ("DONE",)   # WONTFIX is exempt: nothing closed it.


def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8")


def main(argv: list[str]) -> int:
    head = "HEAD"
    ledgers: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--head":
            if i + 1 >= len(argv):
                print("usage: check_closure_references.py LEDGER [--head REF]",
                      file=sys.stderr)
                return 2
            head = argv[i + 1]
            i += 2
            continue
        ledgers.append(argv[i])
        i += 1

    if not ledgers:
        print("usage: check_closure_references.py LEDGER [--head REF]",
              file=sys.stderr)
        return 2

    if _git(["rev-parse", "--git-dir"]).returncode != 0:
        print("[closure-refs] ERROR: not inside a git worktree", file=sys.stderr)
        return 2

    shallow = _git(["rev-parse", "--is-shallow-repository"])
    if shallow.stdout.strip() == "true":
        print("[closure-refs] ERROR: shallow clone -- reachability cannot be "
              "decided here and a truncated history would report live commits "
              "as dangling. Re-run with full history (CI: fetch-depth: 0).")
        return 2

    if _git(["rev-parse", "--verify", "--quiet", f"{head}^{{commit}}"]).returncode != 0:
        print(f"[closure-refs] ERROR: --head {head} does not resolve", file=sys.stderr)
        return 2

    rows = []
    for lp in ledgers:
        p = Path(lp)
        if not p.is_file():
            print(f"[closure-refs] ERROR: no such ledger: {p}", file=sys.stderr)
            return 2
        bad = unreadable_rows(p.read_text(encoding="utf-8"))
        if bad:
            print(f"[closure-refs] ERROR: {p} has {len(bad)} unreadable row(s) "
                  f"at line(s) {', '.join(map(str, bad))} -- a closure with no "
                  f"citation sitting on one of them would never be examined. "
                  f"Refusing to report success.")
            return 2
        rows += [(str(p), r) for r in parse_rows(p) if r.id != PENDING_ID]

    resolved_cache: dict[str, bool] = {}

    def _is_reachable_commit(tok: str) -> bool:
        if tok in resolved_cache:
            return resolved_cache[tok]
        ok = _git(["cat-file", "-e", f"{tok}^{{commit}}"]).returncode == 0 and \
            _git(["merge-base", "--is-ancestor", tok, head]).returncode == 0
        resolved_cache[tok] = ok
        return ok

    examined = 0
    bad_rows: list[tuple[str, str, str]] = []
    for path, row in rows:
        if row.state not in CLOSING_STATES:
            continue
        examined += 1
        tokens = HASH_RE.findall(row.notes)
        if not tokens:
            bad_rows.append((path, row.id,
                             "no commit hash in notes -- a closure that points "
                             "at nothing is not a closure (PROTOCOL 6.2)"))
            continue
        if not any(_is_reachable_commit(t) for t in tokens):
            bad_rows.append((path, row.id,
                             f"cites {', '.join(tokens)} -- none resolves to a "
                             f"commit reachable from {head}"))

    if bad_rows:
        for path, ub, why in bad_rows:
            print(f"[closure-refs] FAIL {path}: {ub}: {why}")
        print("[closure-refs] a DONE row names the commit that closed it, and "
              "that commit is findable. Cite it, or the row is not closed.")
        return 1

    print(f"[closure-refs] PASS: {examined} DONE row(s) each cite a commit "
          f"reachable from {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
