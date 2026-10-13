# Quickstart: install, first check, uninstall

All output below was captured by running these commands on Windows 11 (Git for
Windows, Python 3.12) against a scratch repository. Paths are shortened to
`/path/to/your-repo`. The example IDs (`UB-101`) come from Docket's synthetic
fixtures and starter ledger; the default prefix is configurable (see the README).

You need Git, Python 3 and a POSIX `sh`. The installer is a shell script. On
Windows use the `sh` that ships with Git for Windows.

## 0. See a check fail and pass, installing nothing

```text
git clone https://github.com/moranbickel/Docket
cd Docket
python checks/check_duplicate_ids.py tests/fixtures/dup_red.md
python checks/check_duplicate_ids.py tests/fixtures/dup_green.md
```

Real output (the first command exits 1, the second exits 0):

```text
[duplicate-ids] FAIL: UB-101 appears 2 times (tests\fixtures\dup_red.md:4, tests\fixtures\dup_red.md:6)
[duplicate-ids] one number, one matter -- within a ledger and across shards alike. Merge the rows; never renumber by hand-picking a fresh id outside the minting mode.
[duplicate-ids] PASS: every id appears exactly once (2 rows across 1 ledger(s))
```

(On Linux and macOS the paths print with `/`.)

## 1. Install into a project

The target must be a Git repository. It may be brand new or a shallow clone:
where there is no history to read, the installer skips the one check that needs
it (closure references), says so, and still finishes.

Give the repository's top level (the directory that holds `.git`, or for a
linked worktree its own root). A subdirectory is refused, because the hook and
the uninstaller assume the top level:

```text
docket: ERROR: /path/to/your-repo/sub is not the top level of its repository.
docket:        Pass the top level instead: /path/to/your-repo
docket:        nothing was written.
```

(exit 2). Every other precondition that can be checked before writing is
checked first too: a Git worktree, a Python, no existing file that differs from
the one to be installed, and no path of the wrong kind (a directory where a file
goes, or a file where a directory goes). If any fails, nothing has been written. Once writing has started, the
remaining steps check your ledger; a failure there reports on the ledger and
does not undo the install (use the uninstaller below for that).

**Shared hooks.** If `core.hooksPath` is set (in any scope) or the repository has
linked worktrees, the pre-commit hook may be shared with other checkouts, whose
commits would run Docket's block against files they may not have. The installer
then installs the files and does **not** write the hook, unless you pass
`--shared-hook`:

```text
docket: NOTICE -- pre-commit hook NOT written: the hook may be shared with other checkouts.
docket:   - core.hooksPath is set (/path/to/shared-hooks)
docket:   Docket's files are installed; its pre-commit check is not. To write the hook into
docket:   /path/to/shared-hooks/pre-commit anyway, re-run with --shared-hook. Removing it later is a manual step.
```

(exit 0). Re-run with `sh Docket/templates/install.sh --shared-hook /path/to/your-repo`
to write the block anyway; removing it later is a manual step (see Uninstall).

Read [`templates/install.sh`](../templates/install.sh) before you run it. It
writes only inside the target repository: `checks/`, `tests/`,
`.github/workflows/ledger-ci.yml`, `DOCKET.md` (only if absent), a stanza
appended to `.gitattributes`, and a block appended to the repository's
`pre-commit` hook. It also writes an install manifest (see Uninstall) inside the
git directory. The hook is written only when it is this checkout's own; with
`core.hooksPath` set or linked worktrees present it is not (see "Shared hooks"). It
refuses to overwrite a differing file.

POSIX shell, or Git Bash on Windows, from the directory that contains your
Docket clone:

```sh
sh Docket/templates/install.sh /path/to/your-repo
```

Windows PowerShell:

```powershell
& 'C:\Program Files\Git\bin\sh.exe' Docket/templates/install.sh D:/path/to/your-repo
```

Use forward slashes in the target path, as shown.

Real output, into a repository that already has one commit (paths shortened;
the exit code is 0):

```text
docket: starter ledger -> /path/to/your-repo/DOCKET.md
docket: .gitattributes stanza appended
docket: pre-commit hook -> /path/to/your-repo/.git/hooks/pre-commit
docket: verifying -- running the installed single-ledger checks against /path/to/your-repo
[duplicate-ids] PASS: every id appears exactly once (3 rows across 1 ledger(s))
[merge-driver] DOCKET.md: merge -> unspecified (ok)
[merge-driver] PASS: no ledger path resolves to merge=union
[pending-markers] PASS: 0 pending row(s)
[closure-refs] PASS: 0 DONE row(s) each cite a commit reachable from HEAD
docket: running the fixture suite that arms these checks. It builds a
docket:   scratch git repo per case: a few seconds on Linux/macOS, and
docket:   noticeably longer on Windows, where git subprocesses are far
docket:   more expensive. Be patient; it is not hung.
..............................ssssssssssssssssssssssssssssssssssssss.... [ 84%]
.............                                                            [100%]
47 passed, 38 skipped in 57.29s
docket: OK -- checks ran clean and the fixture suite passed.
```

Into a repository whose current branch has **no commits yet**, the same install
prints the notice below in place of the closure line and ends
`docket: OK -- checks ran clean (closure check skipped: no commits yet) and the fixture suite passed.`
(exit 0, `47 passed, 38 skipped`):

```text
docket: NOTICE -- closure check SKIPPED: the current branch has no commits yet.
docket:          It runs in CI, and here once there is history to check.
```

In a shallow clone (`git clone --depth 1`) the notice reads `this is a shallow
clone, where commit reachability cannot be decided` instead.

**The 38 skipped tests** are the tests of the installer and uninstaller
themselves. They need `templates/`, which is not copied into your project, so
the installed suite skips them with a stated reason instead of failing. They run
in the Docket clone's own suite.

**Windows cost.** The suite builds a scratch Git repository per case, and Git
subprocesses are slow on Windows. Measured on a Windows 11 machine: the whole
install took between 26 s and 58 s on repeated runs into a one-commit or empty repository. Docket's own
85-test suite, which also runs the installer and uninstaller many times, took
19 minutes in one run on a machine shared with other work (earlier, smaller
versions took between 7 and 25 minutes); on Linux it takes seconds. Expect it to vary
with antivirus and disk, and do not interrupt it. If pytest is not installed
the installer says so and reports the suite as pending rather than passed.

## 2. First check in your project

Commit the installed files, then add a row that reuses an existing ID. The
pre-commit hook runs the duplicate-ID and claim checks and refuses the commit:

```sh
printf '| UB-101 | OPEN | Duplicate of the first row | symptom | - | - | filed 2026-08-05 |\n' >> DOCKET.md
git add DOCKET.md
git commit -m "dup"
```

Real output (`git commit` exits 1; nothing is committed):

```text
[duplicate-ids] FAIL: UB-101 appears 2 times (DOCKET.md:15, DOCKET.md:18)
[duplicate-ids] one number, one matter -- within a ledger and across shards alike. Merge the rows; never renumber by hand-picking a fresh id outside the minting mode.
```

Remove the extra line and the commit goes through. The hook runs only the
duplicate-ID and claim-collision checks. The other checks run in the installed
CI workflow; the range checks (state transitions, commit IDs) and the
tracked-file check (phantom IDs) cannot run at install time because they need
history to compare.

## 3. Uninstall

The installer records exactly what it created, with a content hash for each
file, in `docket-install.manifest` inside the repository's git directory (find
it with `git rev-parse --git-path docket-install.manifest`; it is not in your
working tree, so there is nothing to commit). `templates/uninstall.sh` reads that
manifest. From the directory that contains your Docket clone:

```sh
sh Docket/templates/uninstall.sh /path/to/your-repo
```

Windows PowerShell:

```powershell
& 'C:\Program Files\Git\bin\sh.exe' Docket/templates/uninstall.sh D:/path/to/your-repo
```

What it does, and does not do:

- Removes a file only if it is listed in the manifest **and** its content still
  matches the hash recorded at install time. A Docket file you have edited, and
  `DOCKET.md` once you have added rows to it, are left in place with a
  `left in place (changed since install)` message.
- Never deletes a directory wholesale. Your own files in `checks/` and `tests/`
  stay; a directory the installer created is removed only once it is empty.
- Removes Docket's marked block from the pre-commit hook only when that hook is
  this checkout's own, and only if both marker lines are still there; it deletes
  the hook only if nothing but a shebang is left. When `core.hooksPath` is set,
  the repository has linked worktrees, or the hook recorded at install time is not
  the one Git resolves now, the **whole uninstall is refused** (exit 2, nothing
  changed) and the manual steps are printed, because removing this checkout's files
  would break the commits of every checkout that shares the hook, and removing the
  block would disarm their check. See "Shared hooks" below.
- Removes Docket's stanza from `.gitattributes` only if it is still exactly what
  was installed (opening line, closing line and text, checked against a hash taken
  at install time). If you have deleted the closing line or edited the stanza, the
  file is left untouched and the script tells you what to remove by hand.
- Ignores, with a message, a manifest entry that is an absolute path or climbs out
  of the repository with `..`, and keeps it in the manifest. The manifest is
  deleted only once every entry has been dealt with.
- Accepts a subdirectory of the repository, says it is using the top level, and
  proceeds from there (an uninstall is recovery, so it does not refuse).
- Is safe to run twice: the second run reports that there is nothing to uninstall.

Real output, from a scratch repository whose own `checks/lint_mine.py` and
`tests/test_mine.py` were committed before the install, with the install itself
committed afterwards (the per-file `removed` lines between the first and last
file are omitted here):

```text
docket: removed checks/check_claim_collision.py
docket: removed checks/check_closure_references.py
docket: removed checks/check_commit_ids.py
...
docket: removed tests/test_checks.py
docket: removed .github/workflows/ledger-ci.yml
docket: removed DOCKET.md
docket: removed pre-commit hook /path/to/your-repo/.git/hooks/pre-commit (nothing else was in it)
docket: removed .gitattributes (Docket created it and nothing else was in it)
docket: removed empty directory tests/fixtures/
docket: removed empty directory .github/workflows/
docket: removed empty directory .github/
docket: uninstalled. Commit the removal if you had committed the install.
```

Afterwards `ls checks tests` shows only `lint_mine.py` and `test_mine.py`. Because
the install had been committed, `git status` lists the removed files as deletions;
committing them succeeds with no hook in the way (`Remove Docket`, exit 0). A
second run:

```text
docket: nothing to uninstall -- no install manifest for this working tree (/path/to/your-repo/.git/docket-install.manifest).
```

If the stanza's closing line has been deleted and you appended your own rule,
this is the real output for `.gitattributes` (your lines are untouched):

```text
docket: .gitattributes left untouched: Docket's stanza is not exactly as installed
docket:   (a marker line is missing or its text was edited), so it was not cut.
docket:   Remove by hand the comment block starting '# --- Docket ledger:' and the
docket:   rule 'DOCKET.md text eol=lf', if you no longer want them.
docket: uninstalled, except what is listed above. Those entries stay in the
docket: manifest; re-run this script after you have dealt with them.
```

### Shared hooks

Real output when the repository uses a shared `core.hooksPath` hook that carries
Docket's block (exit 2; no file, hook or manifest was touched):

```text
docket: REFUSING to uninstall -- nothing was changed.
docket:   There is a Docket hook to deal with, and it may be shared or is not the one recorded.
docket:   - core.hooksPath is set (/path/to/shared-hooks)
docket:   The hook Git resolves for this repository is: /path/to/shared-hooks/pre-commit
docket:   Docket's block there calls checks/ in whichever checkout commits, so removing this
docket:   checkout's files first would break commits, and removing the block disarms Docket's
docket:   pre-commit check for every checkout that uses that hook file. If you accept that:
docket:     1. open that hook file and delete the lines from '# --- docket-checks (installed by'
docket:        through '# --- end docket-checks';
docket:     2. re-run: sh uninstall.sh --skip-hook /path/to/your-repo
docket:   Otherwise leave Docket installed here.
```

After you have deleted the block from that hook file by hand, `--skip-hook`
continues with the safe parts (files, stanza, empty directories). It is allowed
only when no Docket block remains in the hook; if one does, it refuses the same
way:

```sh
sh Docket/templates/uninstall.sh --skip-hook /path/to/your-repo
```

(exit 0; the hook file, which is yours, is left as you edited it; the last line is
`docket: uninstalled. Commit the removal if you had committed the install.`.) Removing the block disarms Docket's pre-commit check for every
checkout that uses that hook file, which is why this step is yours and not the
script's. The same refusal applies to a linked worktree; once the other worktrees
are gone the main checkout can uninstall normally.

One more limit: the manifest belongs to this clone. A fresh clone of your
repository has the committed files but no manifest, so run the uninstaller in the
clone where you ran the installer, or delete the files by hand.
