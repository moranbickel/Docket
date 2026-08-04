"""Shared row parser for the Docket checks. Reads, never writes.

A row is one Markdown table line:
| UB-NNNN | STATE | title | scope | owner | blocked-by | notes |
Header/separator lines and prose are ignored. The pending placeholder
(UB-ID-PENDING; Mode B minting, PROTOCOL.md section 2) is a legal id.

RENAMING THE PREFIX: change ID_PREFIX below -- the ONE site. Every check
derives its row pattern, its citation pattern, and the pending sentinel
from these constants; nothing else in checks/ carries the literal prefix.
(PROTOCOL.md section 1.2 states the same instruction; keep the two in sync.)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ID_PREFIX = "UB-"
PENDING_ID = ID_PREFIX + "ID-PENDING"

ROW_RE = re.compile(
    r"^\|\s*(" + re.escape(ID_PREFIX) + r"\d+|" + re.escape(PENDING_ID) + r")\s*\|"
    r"\s*(OPEN|PARTIAL|DONE|BLOCKED|WONTFIX)\s*\|"
)
CITE_RE = re.compile(r"\b" + re.escape(ID_PREFIX) + r"(\d+)\b")

STATES = ("OPEN", "PARTIAL", "DONE", "BLOCKED", "WONTFIX")

# A table separator line: | --- | --- | ... (any mix of -, :, spaces, pipes).
_SEP_RE = re.compile(r"^\|[\s\-:|]+\|?\s*$")


@dataclass
class Row:
    id: str
    state: str
    fields: list[str]   # all cells, stripped
    line_no: int
    raw: str

    @property
    def owner(self) -> str:
        return self.fields[4] if len(self.fields) > 4 else "-"

    @property
    def notes(self) -> str:
        return self.fields[6] if len(self.fields) > 6 else ""


def parse_rows_text(text: str) -> list[Row]:
    rows: list[Row] = []
    for n, line in enumerate(text.splitlines(), start=1):
        m = ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(Row(id=m.group(1), state=m.group(2),
                        fields=cells, line_no=n, raw=line))
    return rows


def parse_rows(path: Path) -> list[Row]:
    return parse_rows_text(path.read_text(encoding="utf-8"))


def _row_shaped(line: str) -> bool:
    """Is this line a ledger ROW by shape, whatever its id says?

    The test is the state column: cell 2 is one of the five states, cell 1
    is a single space-free token (an id, however spelled), and the line has
    a row's cell count. That reads a row whose id prefix was renamed, whose
    id is mangled, or whose leading pipe was stripped by a hand edit -- all
    of which MUST count as rows that failed to parse.

    It deliberately does not key on pipe density: ordinary prose carrying
    pipes ("id | state | title | scope", "a|b|c|d") has a multi-word first
    cell or no state in cell 2, so it is not row-shaped. The separator and
    the `| id | state | ...` header line are excluded the same way."""
    s = line.strip()
    if s.count("|") < 2 or _SEP_RE.match(s):
        return False
    body = s[1:] if s.startswith("|") else s
    cells = [c.strip() for c in body.split("|")]
    if len(cells) < 3:
        return False
    first = cells[0]
    return bool(first) and not any(c.isspace() for c in first) \
        and cells[1].upper() in STATES


def unreadable_rows(text: str) -> list[int]:
    """Line numbers of row-shaped lines that did NOT parse.

    Non-empty means the instrument is reading a ledger it cannot fully
    read: every check treats it as exit 2, never success. This is per-ROW,
    not per-file -- one good row must never mask a broken sibling, because
    a check that skips the line it cannot parse reports a clean PASS over a
    duplicate, a pending row, or a claim theft sitting in that very line.

    A correctly-shaped table with no rows filed yet returns [] -- an empty
    ledger is legitimate, and the checks proceed over zero rows and say so."""
    parsed = {r.line_no for r in parse_rows_text(text)}
    return [n for n, line in enumerate(text.splitlines(), start=1)
            if n not in parsed and _row_shaped(line)]
