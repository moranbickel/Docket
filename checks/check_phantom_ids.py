#!/usr/bin/env python3
"""FAIL when any tracked file cites a UB-ID that has no ledger row.

The ID space is closed: a citation to a number that was never minted is a
fabrication (human or AI -- the check cannot tell and does not care).
Allowlist: the ledger(s) themselves and CHANGELOG.md by default; extend
consciously with --allow (exact paths, or directory prefixes ending in '/'
-- e.g. `--allow docs/ examples/` for teaching surfaces full of synthetic
ids that are not, and must never become, citations of real work).

Exit 0 clean / 1 phantoms found / 2 infra (not a git repo, unreadable ledger).
Usage: check_phantom_ids.py LEDGER [LEDGER ...] [--allow PATH ...]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _ledger import parse_rows, zero_parse  # noqa: E402

CITE_RE = re.compile(r"\bUB-(\d+)\b")


def main(argv: list[str]) -> int:
    ledgers: list[str] = []
    allow: list[str] = []
    bucket = ledgers
    for a in argv:
        if a == "--allow":
            bucket = allow
            continue
        bucket.append(a)
    if not ledgers:
        print("usage: check_phantom_ids.py LEDGER [--allow PATH ...]", file=sys.stderr)
        return 2

    minted: set[str] = set()
    for lp in ledgers:
        p = Path(lp)
        if not p.is_file():
            print(f"[phantom-ids] ERROR: no such ledger: {p}", file=sys.stderr)
            return 2
        if zero_parse(p.read_text(encoding="utf-8")):
            print(f"[phantom-ids] ERROR: {p} is non-empty but parses to zero "
                  f"rows -- wrong id prefix or malformed table. Refusing to "
                  f"report success over nothing.")
            return 2
        minted |= {r.id for r in parse_rows(p) if r.id != "UB-ID-PENDING"}

    r = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                       encoding="utf-8")
    if r.returncode != 0:
        print("[phantom-ids] ERROR: git ls-files failed (not a repo?)", file=sys.stderr)
        return 2
    skip_exact = {str(Path(x)) for x in ledgers + allow + ["CHANGELOG.md"]
                  if not x.endswith("/")}
    skip_dirs = [x.rstrip("/") for x in allow if x.endswith("/")]

    def _allowed(f: str) -> bool:
        p = Path(f)
        if str(p) in skip_exact:
            return True
        return any(p.parts[:len(Path(d).parts)] == Path(d).parts
                   for d in skip_dirs)

    phantoms: list[tuple[str, int, str]] = []
    for f in r.stdout.splitlines():
        if _allowed(f):
            continue
        try:
            text = Path(f).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable: not a citation surface
        for n, line in enumerate(text.splitlines(), start=1):
            for m in CITE_RE.finditer(line):
                ub = f"UB-{m.group(1)}"
                if ub not in minted:
                    phantoms.append((f, n, ub))

    if phantoms:
        for f, n, ub in phantoms:
            print(f"[phantom-ids] FAIL {f}:{n}: cites {ub} -- no such row in the ledger")
        print("[phantom-ids] a number with no row behind it is not authority. "
              "File the row, or fix the citation.")
        return 1
    print(f"[phantom-ids] PASS: every cited id has a row ({len(minted)} minted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
