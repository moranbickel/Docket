# Changelog

## v0.2 - 2026-08-04

An integrity release. Every item came from an external review of v0.1, and every one was re-verified against the files before it was accepted.

**The quick start was broken, and that was the release blocker.** `install-hooks.sh` copied three files into `.docket-checks/` while the CI workflow it told you to copy invoked five checks under `checks/` plus the suite under `tests/`. Each artifact was internally consistent; only their intersection was wrong, which is exactly why reading either one alone missed it. An adopter who followed the README exactly got a red first build.
- `templates/install.sh` replaces `install-hooks.sh` (renamed: it now installs more than hooks, and a file whose name understates what it does is how this defect started). One command places `checks/` and `tests/` whole, the hook, the workflow, a starter ledger and the `.gitattributes` stanza — then runs the checks it just installed. It refuses rather than overwrite anything of yours, leaves an existing `DOCKET.md` alone, and is idempotent.
- Running that installer against **this** repository — the first thing v0.1's installer was never tested against — immediately found two defects in the fix itself. `cp` refuses a same-file copy, so a self-install died on its first file; identical files are now a no-op. And the "already installed" test for the `.gitattributes` stanza keyed on the stanza's own comment text, so a repo that had written its own equivalent rule got the stanza appended anyway and ended up declaring `DOCKET.md text eol=lf` twice. The predicate now asks whether the ledger already has attributes, which is the real question, and a both-arms test covers it.
- `*.sh` is pinned to `eol=lf`. Without it a Windows clone with `core.autocrlf=true` checks the installer out with CRLF and `sh` dies on the shebang — a POSIX script shipped as the one-command entry point should not depend on the checkout that produced it.
- The guard is `test_installed_workflow_paths_all_resolve`: it runs the real installer into a scratch repo, extracts every path the INSTALLED workflow invokes, and asserts each is on disk — plus a negative control that neuters the installer and requires the guard to go red. The neutered installer still exits 0, which is the point: a broken install reporting success is the original bug.
- The README's known-gap disclosure is gone, deleted in the same change that made it false. It had also been published **three times verbatim** — a copy-paste fault in v0.1's own correction commit.

**State-transition CI only ever examined the final parent edge.** `fetch-depth: 2` and `HEAD~1` compare one edge. A `DONE`→`OPEN` in the middle of a multi-commit push, tidied before the tip, is invisible: both ends agree and nobody is told.
- `checks/check_state_transitions_range.py` walks every parent→child edge in the push or PR range, merges included (a bad conflict resolution reopens a row with no authored commit saying so). CI now checks out with `fetch-depth: 0` and resolves the real range. The checker itself was sound and is unchanged; only the range handed to it was wrong.
- Armed both ways, including a negative control that runs the OLD endpoint comparison over the same history and requires it to report clean — so the test proves range-awareness is what catches it.

**Two protocol rules had no mechanical check.** Both are now enforced. One of them found real defects in this repo's own ledger on its first run; the other ran clean over the history it was given, which is a result and not a demonstration.
- `checks/check_closure_references.py` (§6.1/6.2): a `DONE` row must cite a commit that resolves **and is reachable from HEAD**. Reachability, not existence, is the load-bearing half — rewriting this repository's history before publication left every closure note pointing at commits that still lived in git's object store but had left the project's history. On its first run it caught two rows: one citing only sibling-repository hashes that cannot resolve here, one citing nothing at all. Both now name the commit that actually closed them. `WONTFIX` is exempt.
- `checks/check_commit_ids.py` (§3.1/3.3): a commit that advances a row names it, and a number in a commit message has a row behind it. A commit message is not a tracked file, so it was the one citation surface `check_phantom_ids.py` could never read. Filing a row is explicitly not advancing one — under Mode B a filing has no number to cite yet.

**PROTOCOL rulings.**
- New §2.3: **work begins after reconciliation, not on a pending row.** A pending row cannot be claimed (the claim check must exclude the shared sentinel) and cannot be cited (there is no number), which puts §3.1 out of reach for the whole of that work. Filing still does not wait.
- New §5.4 (range-aware transitions) and enforcement pointers added to §3.1, §3.3, §6.1.
- Two sections were both numbered **4.4**; the second is now 4.5.

**Not built, deliberately.** The atomic claim-acquisition protocol remains specified in §4.4 and unbuilt. It needs a network round trip and a shared coordination branch, and it should not exist until someone measurably hits the collision it prevents.

**Also:** CI badge in the README; the starter ledger no longer ships a `DONE` row citing a sample hash, which would have failed every adopter's first closure check; diagram and counts updated (eight checks, seven in CI).

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
- No evidence file. An earlier draft collected production figures from the origin system; it was cut before publication rather than shipped with numbers that had not each been re-counted from their source. The two failure stories in the README carry the argument without them, and a repo whose subject is not citing what you have not verified should not open with unverified citations.
- Review: five adversarial rounds against the published sibling protocol's own reviewer template (REWORK 3.6 -> REVISE 7.8 -> 7.3 -> 6.5 -> PASS 9.5, zero Critical/Important/Minor at the floor). Each round's findings were folded and the next round verified the fold; the guards that survived were armed by mutation in both directions.
