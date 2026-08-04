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
| UB-7 | DONE | Review pass on README + PROTOCOL at the series floor (>= 9.0, 0 Critical/Important) | symptom | - | - | filed 2026-08-03; claimed 2026-08-03; R1 REWORK 3.6 -> R2 REVISE 7.8 -> R3 REVISE 7.3 -> R4 REVISE 6.5, each folded (ungated headline figure removed; cross-shard + zero-parse vacuities closed; prefix rename made single-site; per-ROW unreadable guard replacing the per-file one, with the prose exemption armed by mutation both directions); R5 PASS 9.5, 0C/0I/0M -- floor met, arc terminal; closed by commits a0919d9..598c04d. CORRECTION (R5 Note): commit 598c04d's message says the mutation killed '4 RED arms' and '2 exemption twins'; those were the -k selected subsets. The full-suite counts are 9 and 15 (neutered guard / over-broadened predicate, restored: 30 passed). The claim understated the control and this is the correction. |
| UB-8 | OPEN | Cross-link PRs into the five sibling repos | symptom | - | UB-7 | filed 2026-08-03; prepared locally, pushed only after the main repo is up |
| UB-9 | OPEN | GitHub topics on repo creation (series core set + work-ledger, task-tracking, backlog, session-coordination) | symptom | - | UB-7 | filed 2026-08-03; applies at push time via gh repo edit |
