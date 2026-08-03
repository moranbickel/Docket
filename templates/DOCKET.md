# DOCKET — work ledger

> One row = one matter = one number, for life. Never reused, never renumbered.
> Minting mode: **B** (file with `UB-ID-PENDING`; the designated authority assigns numbers in reconciliation passes).
> Claims before work; closures cite commits; reopens carry a dated `reopened:` note.
> Full rules: https://github.com/moranbickel/Docket/blob/main/PROTOCOL.md

| id | state | title | scope | owner | blocked-by | notes |
|----|-------|-------|-------|-------|------------|-------|
| UB-101 | DONE | Fix the flaky auth test (times out on cold cache) | symptom | - | - | filed 2026-08-01; claimed by session-A 2026-08-01; closed by commit 4f21c0d 2026-08-02 |
| UB-102 | OPEN | Input validation missing on the upload route — check ALL routes | class | session-B | - | filed 2026-08-02; claimed by session-B 2026-08-03 |
| UB-103 | BLOCKED | Migrate the report renderer to the new template engine | symptom | - | UB-102 | filed 2026-08-03; blocked: renderer shares the validation helper UB-102 is rewriting |
