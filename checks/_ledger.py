"""Shared row parser for the Docket checks. Reads, never writes.

A row is one Markdown table line:
| UB-NNNN | STATE | title | scope | owner | blocked-by | notes |
Header/separator lines and prose are ignored. UB-ID-PENDING is a legal id
placeholder (Mode B minting, PROTOCOL.md section 2).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROW_RE = re.compile(
    r"^\|\s*(UB-\d+|UB-ID-PENDING)\s*\|"            # id
    r"\s*(OPEN|PARTIAL|DONE|BLOCKED|WONTFIX)\s*\|"  # state
)

STATES = ("OPEN", "PARTIAL", "DONE", "BLOCKED", "WONTFIX")


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
