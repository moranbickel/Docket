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


def _data_shaped(line: str) -> bool:
    """A pipe-line that should have been a row: not the separator, not the
    column-header line (which starts `| id |` by protocol field order)."""
    s = line.strip()
    if not s.startswith("|"):
        return False
    if _SEP_RE.match(s):
        return False
    first_cell = s.strip("|").split("|", 1)[0].strip().lower()
    return first_cell != "id"


def zero_parse(text: str) -> bool:
    """True ONLY in the ambiguous instrument state: the text carries
    data-shaped table lines, yet zero of them parse (renamed id prefix,
    mangled table). A correctly-shaped table with no rows filed yet is a
    LEGITIMATE empty ledger, not this state -- checks proceed over zero
    rows and say so. Every check treats True as exit 2, never success: a
    run over unreadable rows has measured nothing."""
    if parse_rows_text(text):
        return False
    return any(_data_shaped(l) for l in text.splitlines())
