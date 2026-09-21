# Docket

[![ledger-ci](https://github.com/moranbickel/Docket/actions/workflows/ledger-ci.yml/badge.svg)](https://github.com/moranbickel/Docket/actions/workflows/ledger-ci.yml)

A numbered work ledger for concurrent coding sessions, with Python checks for
duplicate IDs, missing references, conflicting claims, and unsupported closures.

## Try a check before installing

Requires Git and Python 3. Run each command separately; the first check deliberately
exits with code 1 because the fixture contains a duplicate.

```text
git clone https://github.com/moranbickel/Docket
cd Docket
python checks/check_duplicate_ids.py tests/fixtures/dup_red.md
python checks/check_duplicate_ids.py tests/fixtures/dup_green.md
```

These are synthetic fixtures. The first repeats `UB-101`; the second has unique
IDs and exits with code 0. No hooks are installed by these commands.

The [phantom-reference crash test](https://github.com/moranbickel/agent-crash-tests/tree/main/cases/phantom-reference)
is another small example: a handoff cites a work item absent from the ledger.

## Install

From the parent of your Docket clone, using a POSIX shell (Git Bash on Windows):

```sh
sh Docket/templates/install.sh /path/to/your-repo
```

The installer adds checks, test fixtures, a CI workflow, a pre-commit hook, a
starter ledger, and Git attributes. Read the [installer](templates/install.sh)
first. It refuses differing check files and preserves an existing ledger; it
may append Docket configuration to existing hooks and attributes.

It runs the applicable installed checks and, when pytest is available, the
fixture suite. The suite can take minutes on Windows. Missing pytest is reported
as a pending suite, not a test pass. Range and tracked-file checks run in CI.

## Rules and limits

Each matter has one permanent ID and one row. Claim it before work; close it with
a reachable commit reference. Same-row edits must conflict: do not configure
the ledger with `merge=union`.

Local claim checks detect a takeover in the history they can see. They cannot
stop two isolated branches from claiming the same previously unclaimed row.

Read the [three-session example](examples/three-sessions-walkthrough.md),
[protocol](PROTOCOL.md), [checks](checks/), and [test suite](tests/test_checks.py).
The default prefix is `UB-`; change `ID_PREFIX` in `checks/_ledger.py` if needed.

Maintained by [Moran Bickel](https://github.com/moranbickel).
Prose: [CC BY 4.0](LICENSE-CC-BY-4.0). Templates and code: [MIT](LICENSE-MIT).
