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

The target must be a Git repository. It may be brand new: with no commits yet,
the installer skips the one check that needs a commit to read (closure
references), says so, and still finishes. Nothing is left half-installed.

Read [`templates/install.sh`](../templates/install.sh) before you run it. It
writes only inside the target repository: `checks/`, `tests/`,
`.github/workflows/ledger-ci.yml`, `DOCKET.md` (only if absent), a stanza
appended to `.gitattributes`, and a block appended to the repository's
`pre-commit` hook. If you have set `core.hooksPath`, the hook goes to that
directory (the installer asks Git where hooks live), which may be shared by
other repositories; check `git config core.hooksPath` first. It refuses to
overwrite a differing file.

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
docket:   about a minute on a Windows 11 machine, where git subprocesses
docket:   are far more expensive. Be patient; it is not hung.
..............................sssssssss.................                 [100%]
47 passed, 9 skipped in 17.65s
docket: OK -- checks ran clean and the fixture suite passed.
```

Into a repository with **no commits**, the same install prints the notice below
in place of the closure line and ends
`docket: OK -- checks ran clean (closure check skipped: no commits yet) and the fixture suite passed.`
(exit 0):

```text
docket: NOTICE -- closure check SKIPPED: this repository has no commits yet,
docket:          so there is no HEAD to resolve closure notes against.
docket:          It runs in CI, and here once you have made a commit.
```

**The 9 skipped tests** are the tests of the installer itself. They need
`templates/`, which is not copied into your project, so the installed suite
skips them with a stated reason instead of failing. They run in the Docket
clone's own suite.

**Windows cost.** The suite builds a scratch Git repository per case, and Git
subprocesses are slow on Windows. Measured on a Windows 11 machine: the whole
install took 28 s into the one-commit repository and 57 s into the empty one;
Docket's own 56-test suite took 120 s. Expect it to vary with antivirus and
disk, and do not interrupt it. If pytest is not installed the installer says so
and reports the suite as pending rather than passed.

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

There is no uninstall script. The installer's changes are all inside the target
repository, so removing them is manual. Keep `DOCKET.md` if it holds real rows.
From the repository root, in a POSIX shell:

```sh
rm -r checks tests .github/workflows/ledger-ci.yml
sed -i '/^# --- docket-checks/,/^# --- end docket-checks/d' .git/hooks/pre-commit
sed -i '/^# --- Docket ledger:/,/^# -----*$/d' .gitattributes
```

Only run the first line if `checks/` and `tests/` contain nothing of yours; the
installer refuses to overwrite a differing file, so they held only Docket's
files if the install succeeded. If `.git/hooks/pre-commit` is left holding only
`#!/bin/sh`, delete it. Remove `DOCKET.md` as well if you do not want the
ledger. On Windows, run these in Git Bash. These commands were run against the
scratch repository from step 1; afterwards only `DOCKET.md` and the original
files remained, the hook held only its `#!/bin/sh` line, and `.gitattributes`
was empty.
