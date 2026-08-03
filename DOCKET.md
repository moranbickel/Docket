# DOCKET — this repo's own ledger

> This repository keeps its own work under its own protocol, from the first commit.
> One row = one matter = one number, for life. Minting mode: **B** (`UB-ID-PENDING` + reconciliation; reconciliation authority: the operator).
> Full rules: [PROTOCOL.md](./PROTOCOL.md).

| id | state | title | scope | owner | blocked-by | notes |
|----|-------|-------|-------|-------|------------|-------|
| UB-1 | DONE | Author README + PROTOCOL in the series voice | symptom | - | - | filed 2026-08-03; claimed 2026-08-03; closed by commit a0919d9 2026-08-03 |
| UB-2 | DONE | Ship the six checks with exit-code contracts | symptom | - | - | filed 2026-08-03; claimed 2026-08-03; closed by commit a0919d9 2026-08-03 |
| UB-3 | DONE | Fixture pair (one failing, one passing) per check; claim-collision RED arm in a secondary worktree | symptom | - | - | filed 2026-08-03; claimed 2026-08-03; closed by commit a0919d9 2026-08-03 (16 tests, both arms per check) |
| UB-4 | DONE | Wire CI: five checks, each its own step and exit code | symptom | - | - | filed 2026-08-03; claimed 2026-08-03; closed by commit a0919d9 2026-08-03 |
| UB-5 | DONE | Templates + three-session example + diagram | symptom | - | - | filed 2026-08-03; claimed 2026-08-03; closed by commit a0919d9 2026-08-03; diagram's synthetic ids consciously allowlisted after the phantom check caught them |
| UB-6 | OPEN | EVIDENCE.md figures verified against primary artifacts | symptom | - | - | filed 2026-08-03; BLOCKED-in-substance on operator sign-off (item 8 of the build dispatch); draft carries sourced candidates only |
| UB-7 | OPEN | Review pass on README + PROTOCOL at the series floor (>= 9.0, 0 Critical/Important) | symptom | session-d4c8910c | - | filed 2026-08-03; claimed 2026-08-03; R1 REWORK 3.6 (4C/2I/3M) folded same day -- headline figure ungated by EVIDENCE removed, zero-parse and cross-shard vacuities in the duplicate/claim checks closed with test arms, diagram+example surfaced, stanza claim corrected; R2 pending |
| UB-8 | OPEN | Cross-link PRs into the five sibling repos | symptom | - | UB-7 | filed 2026-08-03; prepared locally, pushed only after the main repo is up |
| UB-9 | OPEN | GitHub topics on repo creation (series core set + work-ledger, task-tracking, backlog, session-coordination) | symptom | - | UB-7 | filed 2026-08-03; applies at push time via gh repo edit |
