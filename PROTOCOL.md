# Docket — the protocol

I wrote this file the way court rules are written: short numbered sections, no stories, because when two sessions disagree at a merge boundary, nobody wants my anecdotes — they want the rule and its number. The README tells the story; this file states the rules a machine — or a tired human — can hold you to. It is normative: **MUST**, **MUST NOT**, and **SHOULD** mean what they mean in RFC 2119.

One plain definition before the precise language starts: throughout this document, the item's number (its **ID**, `UB-NNNN`) is used as a *join key* — meaning the same literal string appears in the ledger row, the commit message, the PR title, and the closing note, so that a plain-text search on the number reassembles the item's whole history from otherwise unconnected records. That is the entire trick. Everything below exists to keep that trick trustworthy.

---

## 1. The ledger file

1.1. The ledger is **one tracked plain-text file** in the repository root (this repo uses `DOCKET.md`; the name is yours to choose, the checks take it as an argument).

1.2. **One row = one line.** A row is a Markdown table line:

```
| UB-NNNN | STATE | title | scope | owner | blocked-by | notes |
```

The `UB-` prefix is part of the protocol in v0.1 — the checks parse exactly that shape, and they refuse to report success on a ledger that parses to zero rows (a run over nothing is not a pass). Changing the prefix means changing `checks/_ledger.py` and the phantom check's citation pattern together, deliberately.

1.3. Fields:

| Field | Content | Rules |
|---|---|---|
| `id` | `UB-` + integer | immutable; never reused; never renumbered |
| `state` | `OPEN` \| `PARTIAL` \| `DONE` \| `BLOCKED` \| `WONTFIX` | transitions per §5 |
| `title` | one line, plain language | say the defect or the deliverable, not the plan |
| `scope` | `symptom` \| `class` | a `class` claim asserts the fix covers every member, not just the observed one |
| `owner` | session/agent identifier, or `-` | written at claim time (§4); exactly one owner at a time |
| `blocked-by` | comma-separated IDs, or `-` | must name rows that exist (the phantom check applies here too) |
| `notes` | dated annotations, newest last | closure notes per §6; reopen notes per §5.3 |

1.4. Long lines are the accepted cost. A one-line row makes a concurrent edit to the same item collide on exactly that line; splitting a row across lines reintroduces silent interleaving.

---

## 2. Minting IDs under concurrency

The hard problem: several sessions, one ID space, no shared lock. Two sanctioned modes. Pick one per repository and write the choice into the ledger header.

**Mode A — pre-allocated bands.** Each worker owns a band (worker 1: 1000–1999, worker 2: 2000–2999, …) and mints sequentially inside it.

- *Pro:* no coordination at mint time, ever.
- *Con:* IDs stop being chronological; bands exhaust unevenly; a worker roster change needs a header edit.

**Mode B — freeze + pending marker + single-authority reconciliation.** Any session may file a row **without an ID**, using the literal marker `UB-ID-PENDING` in the id field. One designated authority (a human, or one designated session at a scheduled moment) assigns real numbers to all pending rows in one pass, in file order.

- *Pro:* IDs stay dense and roughly chronological; any session can file at any moment without coordination.
- *Con:* pending rows can't be cited by number until reconciled; reconciliation is a real chore that must actually happen.

Mode B is the one proven in the origin system. Its failure mode is known and mechanical: a session that *guesses* the next number instead of filing pending — two sessions guess the same number, and you have a collision that no merge will flag. Hence:

2.1. A session **MUST NOT** compute "the next free number" by reading the ledger (grep-the-max is how the origin system got its one real collision). Under Mode B, file with `UB-ID-PENDING`; under Mode A, mint only inside your own band.

2.2. `check_pending_markers.py` enumerates pending rows `file:line`. It is informational by default and **MUST** be run strict (`--reconcile`, nonzero exit on any marker) as the reconciliation gate.

---

## 3. The number travels (citation convention)

3.1. Every commit that advances an item **MUST** carry the item's ID verbatim in the commit message. PR titles, review verdicts, and closure notes likewise.

3.2. Consequence, stated as the design intent: provenance becomes a grep. `git log --grep=UB-1023` and `git grep UB-1023` reassemble the item's history with no tooling beyond git.

3.3. Consequence, the other direction: **a citation to a number with no row behind it is a detectable class.** `check_phantom_ids.py` scans tracked files for `UB-\d+` references and fails on any ID that has no ledger row. The ID space is closed; fabrication is arithmetic, not judgment. (Allowlist: the ledger itself and `CHANGELOG.md`; extend it consciously, not conveniently.)

---

## 4. Claim discipline

4.1. Before working a row, a session **MUST** write its own identifier into the row's `owner` field and commit that edit.

4.2. The pre-commit check (`check_claim_collision.py`) **MUST** reject a commit that changes a row's owner from one non-`-` value to a different non-`-` value. Releasing a claim (owner → `-`) is always allowed.

4.3. This is the defense against the dominant multi-session failure — two sessions building the same item in parallel and merging both. The claim is cheap; the duplicate work it prevents is not.

4.4. The check resolves the repository root **from the worktree the commit is happening in** (`git rev-parse --show-toplevel` at hook time). It **MUST NOT** read the root from an environment variable: with several worktrees live, an env var set by one session silently points another session's hook at the wrong ledger, and the hook passes while guarding nothing.

---

## 5. States and transitions

5.1. `OPEN → PARTIAL → DONE`, `OPEN → BLOCKED → OPEN`, `OPEN → WONTFIX`, and `OPEN → DONE` directly — all ordinary.

5.2. **Out of `DONE` (or `WONTFIX`), any transition MUST carry an annotation** in `notes`, dated, containing the token `reopened:` and one line of why. Regressions reopen loudly, never silently.

5.3. `check_state_transitions.py` compares the previous ledger version to the current one and fails any `DONE`/`WONTFIX` row whose state changed without a `reopened:` token added in the same change.

---

## 6. Closure cites the artifact

6.1. A row moving to `DONE` **MUST** name, in `notes`, the artifact that closed it — at minimum one commit hash; a PR number or review verdict strengthens it.

6.2. A closure note that points at nothing ("done", "fixed", "handled") is not a closure; treat it as `PARTIAL` in review.

6.3. Scope honesty: a row filed as `class` **MUST NOT** close on evidence about a single member. Either the closure names the covering evidence, or the row narrows itself to `symptom` in the same edit — on the record.

---

## 7. The merge-driver rule (the headline)

7.1. The ledger **MUST NOT** be configured with git's union merge driver (`merge=union` in `.gitattributes`), and `check_merge_driver.py` fails CI if it is.

7.2. The design test, portable to any file you keep: **"Is a concurrent edit to the same key a conflict or a feature?"** For an append-only log (events, journals), union is a feature — order barely matters, nothing is keyed. For a ledger where lines are *records with identity*, union is silent corruption: two edits to the same row merge into two copies of the row, no conflict raised, and the duplicates appear **only in merge commits** — the one place no author is looking.

7.3. That signature — duplicate count flat across authored commits, rising only at merges — is how you detect the pathology in history retroactively. The origin system carried it for months; see `examples/` for the before/after.

7.4. The check resolves the **effective** attribute with `git check-attr merge -- <ledger>`. It **MUST NOT** grep `.gitattributes` for the substring `merge=union`: the attribute can arrive via a glob, a macro, a nested attributes file, or an `$GIT_DIR/info/attributes` entry that no substring search will see, and a guard that inspects the configuration source instead of the resolved behavior certifies nothing.

---

## 8. What the checks are, and are not

8.1. The six checks in `checks/` are the protocol's teeth: duplicates (§1.3 id), phantoms (§3.3), merge driver (§7), claim collisions (§4), pending markers (§2.2), state transitions (§5.3). CI runs five; the claim check runs pre-commit, where the colliding claim actually happens.

8.2. Every check ships with a fixture it fails and a fixture it passes, in `tests/`. If you extend a check, extend both fixtures first and watch the new failing case actually fail — a checker that has never been seen failing has not been seen working.

8.3. The checks read the ledger; they never write it. Repair is a human (or an explicitly instructed session) making an edit on the record.

---

## 9. Sharding, at the ceiling

When the file approaches the practical ceiling (order of a few thousand rows / ~1 MB), shard by closing the file (`DOCKET-2026.md`, frozen, still tracked, still grep-able) and opening a successor. IDs continue — the ID space spans shards: pass every shard to the checks together (`check_duplicate_ids.py DOCKET-2026.md DOCKET.md`), and the duplicate check counts ids ACROSS the whole set, so a number reused between shards fails exactly like a number reused within one.
