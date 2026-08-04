# Changelog

## v0.1 - 2026-08-03

Initial public version, re-authored from the origin system's in-production ledger discipline (no origin content copied).

- README.md - the story, the failure it solves (silent union-merge duplication; phantom work-item citations), the protocol in 60 seconds, quick start, series relations, stated limits.
- PROTOCOL.md - normative core: one-line row form and fields; two sanctioned ID-minting modes under concurrency (pre-allocated bands; freeze + `UB-ID-PENDING` + single-authority reconciliation); the citation convention (the ID travels verbatim through commits, PRs, reviews, closures); claim discipline; loud-reopen rule; closure-cites-the-artifact; the merge-driver rule with the portable design test ("is a concurrent same-key edit a conflict or a feature?"); sharding at the ceiling.
- checks/ - six mechanical checks, each 30-80 lines, exit-code contracts stated in the header: `check_duplicate_ids`, `check_phantom_ids`, `check_merge_driver` (resolved attribute via `git check-attr`, never a config-text grep), `check_claim_collision` (pre-commit; repo root from the committing worktree, never an env var), `check_pending_markers`, `check_state_transitions`.
- tests/ - a RED and a GREEN arm for every check (14 static fixtures + two constructed scenarios); the claim-collision RED arm stages its collision in a secondary git worktree, because a project-dir fixture would pass before and after any fix and prove nothing.
- .github/workflows/ledger-ci.yml - the five CI checks, each its own step and exit code (no chained commands laundering verdicts), plus the fixture suite.
- templates/ - starter ledger, row template, `.gitattributes` stanza (explicitly NOT union, with the why), pre-commit hook installer.
- examples/ - a three-session walkthrough (mint, file-pending, claim) and the union-merge pathology shown against the correct conflict, before/after.
- DOCKET.md - this repo's own ledger, kept under its own protocol from the first commit.
- EVIDENCE.md - draft; every figure ships only on operator sign-off against primary artifacts.
- Review: five adversarial rounds against the published sibling protocol's own reviewer template (REWORK 3.6 -> REVISE 7.8 -> 7.3 -> 6.5 -> PASS 9.5, zero Critical/Important/Minor at the floor). Each round's findings were folded and the next round verified the fold; the guards that survived were armed by mutation in both directions.
