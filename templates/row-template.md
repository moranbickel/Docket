# Row template

Copy the line, fill the seven cells. One line — do not wrap.

```
| UB-ID-PENDING | OPEN | <defect or deliverable, plain words> | symptom | - | - | filed YYYY-MM-DD |
```

Field rules (normative source: PROTOCOL.md §1.3):

- **id** — `UB-ID-PENDING` under minting Mode B; your own band's next number under Mode A. NEVER a number you computed by reading the ledger for the current maximum.
- **state** — `OPEN` | `PARTIAL` | `DONE` | `BLOCKED` | `WONTFIX`.
- **title** — the defect or the deliverable, not the plan for it.
- **scope** — `symptom` (this instance) or `class` (every instance; you now owe covering evidence at closure).
- **owner** — `-` until claimed; your session identifier after. Claim BEFORE working.
- **blocked-by** — comma-separated existing IDs, or `-`.
- **notes** — dated, append-only in spirit, newest last. Closure: `closed by commit <hash>`. Reopen: `reopened: <why>`.
