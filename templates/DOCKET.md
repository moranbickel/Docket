# DOCKET — work ledger

> One row = one matter = one number, for life. Never reused, never renumbered.
> Minting mode: **B** (file with `UB-ID-PENDING`; the designated authority assigns numbers in reconciliation passes).
> Claims before work; closures cite commits; reopens carry a dated `reopened:` note.
> Full rules: https://github.com/moranbickel/Docket/blob/main/PROTOCOL.md
>
> Closing a row: set `DONE` and name the commit that closed it, e.g.
> `closed by commit 4f21c0d 2026-08-02` (PROTOCOL 6.1). `check_closure_references.py`
> resolves that hash in YOUR history, so no DONE row ships in this starter --
> a sample hash from someone else's repository would fail your first build.

| id | state | title | scope | owner | blocked-by | notes |
|----|-------|-------|-------|-------|------------|-------|
| UB-101 | OPEN | Fix the flaky auth test (times out on cold cache) | symptom | - | - | filed 2026-08-01 |
| UB-102 | OPEN | Input validation missing on the upload route — check ALL routes | class | session-B | - | filed 2026-08-02; claimed by session-B 2026-08-03 |
| UB-103 | BLOCKED | Migrate the report renderer to the new template engine | symptom | - | UB-102 | filed 2026-08-03; blocked: renderer shares the validation helper UB-102 is rewriting |
