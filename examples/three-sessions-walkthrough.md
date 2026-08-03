# Worked example — three sessions, one ledger

Entirely synthetic. Three fictional AI coding sessions (S1, S2, S3) share one repository and one `DOCKET.md`, minting Mode B.

## Act 1 — S1 mints (via reconciliation)

S1 finds a bug and files it. It does **not** compute "the next free number" by reading the ledger — under Mode B it files pending:

```
| UB-ID-PENDING | OPEN | Retry loop hammers the API when the token expires | symptom | - | - | filed 2026-08-01 by S1 |
```

At the next reconciliation pass, the designated authority assigns numbers to all pending rows in file order. The row becomes:

```
| UB-201 | OPEN | Retry loop hammers the API when the token expires | symptom | - | - | filed 2026-08-01 by S1 |
```

From this moment, `UB-201` is this matter's name forever. S1's fix commit says `fix(auth): stop retry hammering on expired token (UB-201)`, and the closing edit is:

```
| UB-201 | DONE | Retry loop hammers the API when the token expires | symptom | S1 | - | filed 2026-08-01 by S1; closed by commit 9be41aa 2026-08-01 |
```

## Act 2 — S2 files pending, concurrently

While S1 works, S2 (a different session, possibly on a different branch) finds an unrelated defect and files pending too. No coordination needed; two pending rows never collide, because neither carries a number yet:

```
| UB-ID-PENDING | OPEN | CSV export drops rows with commas in the address field | symptom | - | - | filed 2026-08-01 by S2 |
```

`check_pending_markers.py` lists both markers file:line; the reconciliation pass (run with `--reconcile`, which fails while any marker survives) assigns `UB-202`.

## Act 3 — S3 claims before working

S3 picks up `UB-202`. **Before touching the code**, it writes itself into the owner field and commits:

```
| UB-202 | OPEN | CSV export drops rows with commas in the address field | symptom | S3 | - | filed 2026-08-01 by S2; claimed by S3 2026-08-02 |
```

If a fourth session now stages an edit changing that owner to itself, the pre-commit check rejects the commit:

```
[claim-collision] FAIL UB-202: owned by 'S3', this commit re-claims it for 'S4'
```

S4 lost nothing but the ten seconds the check took. Without the check, S4 loses the whole duplicate implementation at merge time.

---

## The pathology — the same edit, union-merged vs. conflicting

Two branches both edit **the same row** `UB-201`: branch A closes it; branch B marks it blocked. Same line, different content.

**Correct behavior (no union driver) — the merge CONFLICTS:**

```
<<<<<<< branch-a
| UB-201 | DONE | Retry loop hammers the API when the token expires | symptom | S1 | - | ...; closed by commit 9be41aa |
=======
| UB-201 | BLOCKED | Retry loop hammers the API when the token expires | symptom | S1 | UB-202 | ...; blocked: fix depends on the CSV path |
>>>>>>> branch-b
```

A human (or an explicitly instructed session) resolves it on the record. One row survives. The ledger stays a list of matters.

**The pathology (`DOCKET.md merge=union` in .gitattributes) — the merge "succeeds":**

```
| UB-201 | DONE | Retry loop hammers the API when the token expires | symptom | S1 | - | ...; closed by commit 9be41aa |
| UB-201 | BLOCKED | Retry loop hammers the API when the token expires | symptom | S1 | UB-202 | ...; blocked: fix depends on the CSV path |
```

No conflict. No warning. `UB-201` is now two rows with two states, and every future reader picks whichever suits them. Note **where** this appeared: only in the merge commit. Neither branch's authored edits ever contained a duplicate — which is why nobody sees it happen, and why the duplicate count in a history with this misconfiguration rises exactly at merge commits and nowhere else. That signature is how you audit old history for the disease.

`check_duplicate_ids.py` turns the corrupted state into a hard failure; `check_merge_driver.py` fails the build while the misconfiguration exists at all — checked against the attribute git actually resolves for the path, not against the text of `.gitattributes` (the union setting can arrive via a glob or a nested attributes file that a text search would miss).
