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

The target must be a Git repository **with at least one commit**. On a repository
with no commits the installer writes its files and then stops at the closure
check (`[closure-refs] ERROR: --head HEAD does not resolve`), exiting non-zero
before the fixture suite runs. Make an initial commit first.

Read [`templates/install.sh`](../templates/install.sh) before you run it. It
writes only inside the target repository: `checks/`, `tests/`,
`.github/workflows/ledger-ci.yml`, `DOCKET.md` (only if absent), a stanza
appended to `.gitattributes`, and a block appended to the repository's
`pre-commit` hook. It refuses to overwrite a differing file. If you have set `core.hooksPath`, the hook
goes to that directory (the installer asks Git where hooks live), which may be shared
by other repositories; check `git config core.hooksPath` first.

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

Real output (the installer's checks section):

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
docket:   scratch git repo per case: ~4s on Linux/macOS, ~14min on
docket:   Windows, where git subprocesses are far more expensive.
```

### Known issue in the final step

Two things to know about the suite step, both observed on the machine above:

- **Time.** The whole install took 35 s on Windows here, and Docket's own suite
  (52 tests) took 67 s, not the 14 minutes the message estimates. Expect it to
  vary with antivirus and disk.
- **Five failures in an adopter repository.** The installer copies `checks/` and
  `tests/` but not `templates/`, and five of the installed tests are tests of the
  installer itself, which need `templates/`. They fail with `No such file or
  directory ... templates/install.sh`, so the installer exits 1 and never
  prints its final `OK` line. The checks above it ran and passed. The other 47
  tests pass:

  ```text
  python -m pytest tests/test_checks.py -q -k "not installer and not installed and not installing"
  47 passed, 5 deselected in 47.98s
  ```

  The five are `test_installed_workflow_paths_all_resolve`,
  `test_parity_control_fails_when_the_installer_drops_the_suite`,
  `test_installer_refuses_to_clobber_a_differing_file`,
  `test_installing_twice_does_not_duplicate_the_gitattributes_rule` and
  `test_installer_leaves_an_existing_ledger_alone`. Run the full suite from your
  Docket clone, where they pass, if you want those too.

If pytest is not installed the installer says so and reports the suite as
pending rather than passed.

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
