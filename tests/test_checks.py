"""Every check, both arms: the case it must FAIL and the case it must PASS.

A checker that has never been seen failing has not been seen working. Each
test invokes the shipped CLI as a subprocess (the artifact under test, never
a re-implementation) and asserts on exit code + the load-bearing output line.

The claim-collision RED arm stages its collision in a SECONDARY git worktree:
a fixture staged in the project dir would pass before and after any fix of
the worktree-root-resolution defect this check exists to avoid, and would
therefore prove nothing.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHECKS = Path(__file__).parent.parent / "checks"
FIX = Path(__file__).parent / "fixtures"


def run_check(script: str, *args: str, cwd: Path | None = None):
    return subprocess.run(
        [sys.executable, str(CHECKS / script), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=cwd,
    )


# ------------------------------------------------------------- duplicate ids

def test_duplicate_ids_red():
    r = run_check("check_duplicate_ids.py", str(FIX / "dup_red.md"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "UB-101 appears 2 times" in r.stdout


def test_duplicate_ids_green():
    r = run_check("check_duplicate_ids.py", str(FIX / "dup_green.md"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


def test_duplicate_ids_red_across_shards(tmp_path):
    """PROTOCOL §9: the ID space spans shards -- the same number once in each
    of two ledger files is a duplicate and must FAIL when both are passed."""
    a = tmp_path / "DOCKET-2025.md"
    b = tmp_path / "DOCKET.md"
    a.write_text("| UB-500 | DONE | old-year matter | symptom | - | - | closed by commit aaa1111 |\n",
                 encoding="utf-8")
    b.write_text("| UB-500 | OPEN | new-year matter | symptom | - | - | filed 2026-08-03 |\n",
                 encoding="utf-8")
    r = run_check("check_duplicate_ids.py", str(a), str(b))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "UB-500" in r.stdout and "DOCKET-2025.md" in r.stdout and "DOCKET.md" in r.stdout


def test_duplicate_ids_green_across_shards(tmp_path):
    a = tmp_path / "DOCKET-2025.md"
    b = tmp_path / "DOCKET.md"
    a.write_text("| UB-500 | DONE | old-year matter | symptom | - | - | closed by commit aaa1111 |\n",
                 encoding="utf-8")
    b.write_text("| UB-501 | OPEN | new-year matter | symptom | - | - | filed 2026-08-03 |\n",
                 encoding="utf-8")
    r = run_check("check_duplicate_ids.py", str(a), str(b))
    assert r.returncode == 0, r.stdout + r.stderr


def test_duplicate_ids_zero_parsed_rows_is_not_a_pass(tmp_path):
    """A non-empty ledger that parses to ZERO rows (wrong prefix, malformed
    table) must exit loudly, never print PASS -- a run over nothing has
    measured nothing. This is the check's own README story applied to itself."""
    l = tmp_path / "DOCKET.md"
    l.write_text(
        "| DOC-1 | OPEN | renamed-prefix row | symptom | - | - | filed |\n"
        "| DOC-1 | OPEN | duplicated, invisibly | symptom | - | - | filed |\n",
        encoding="utf-8")
    r = run_check("check_duplicate_ids.py", str(l))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unreadable" in r.stdout.lower()
    assert "PASS" not in r.stdout


# --------------------------------------------------------------- phantom ids

def _scratch_repo(tmp_path: Path, files: dict[str, Path]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    for name, src in files.items():
        (repo / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def test_phantom_ids_red(tmp_path):
    repo = _scratch_repo(tmp_path, {
        "DOCKET.md": FIX / "phantom_ledger.md",
        "notes.txt": FIX / "phantom_cite_red.txt",
    })
    r = run_check("check_phantom_ids.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "UB-999" in r.stdout and "no such row" in r.stdout


def test_phantom_ids_green(tmp_path):
    repo = _scratch_repo(tmp_path, {
        "DOCKET.md": FIX / "phantom_ledger.md",
        "notes.txt": FIX / "phantom_cite_green.txt",
    })
    r = run_check("check_phantom_ids.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_phantom_ids_dir_allowlist_both_arms(tmp_path):
    """A teaching dir full of synthetic ids: RED without the dir allow,
    GREEN with it -- same repo, same citation, opposite results."""
    repo = _scratch_repo(tmp_path, {"DOCKET.md": FIX / "phantom_ledger.md"})
    (repo / "docs").mkdir()
    (repo / "docs" / "guide.md").write_text(
        "An example row: UB-999 shows the shape.\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "docs"], cwd=repo, check=True)
    red = run_check("check_phantom_ids.py", "DOCKET.md", cwd=repo)
    assert red.returncode == 1 and "docs/guide.md" in red.stdout.replace("\\", "/")
    green = run_check("check_phantom_ids.py", "DOCKET.md", "--allow", "docs/", cwd=repo)
    assert green.returncode == 0, green.stdout + green.stderr


# -------------------------------------------------------------- merge driver

def _attr_repo(tmp_path: Path, attr_fixture: str) -> Path:
    repo = _scratch_repo(tmp_path, {"DOCKET.md": FIX / "phantom_ledger.md"})
    (repo / ".gitattributes").write_text(
        (FIX / attr_fixture).read_text(encoding="utf-8"), encoding="utf-8")
    return repo


def test_merge_driver_red_direct_spelling(tmp_path):
    repo = _attr_repo(tmp_path, "attr_red.gitattributes")
    r = run_check("check_merge_driver.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "resolves to" in r.stdout and "union" in r.stdout


def test_merge_driver_red_glob_spelling(tmp_path):
    """The spelling a config-text grep for 'DOCKET.md merge=union' would miss.
    Only resolving the attribute (git check-attr) catches it."""
    repo = _attr_repo(tmp_path, "attr_red_glob.gitattributes")
    r = run_check("check_merge_driver.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr


def test_merge_driver_green(tmp_path):
    repo = _attr_repo(tmp_path, "attr_green.gitattributes")
    r = run_check("check_merge_driver.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------- claim collision

LEDGER_CLAIMED = """\
| id | state | title | scope | owner | blocked-by | notes |
|----|-------|-------|-------|-------|------------|-------|
| UB-101 | OPEN | The auth bug | symptom | session-A | - | claimed 2026-08-02 |
| UB-102 | OPEN | Retry loop | symptom | - | - | filed 2026-08-02 |
"""


def _claimed_repo_with_second_worktree(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "primary"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "DOCKET.md").write_text(LEDGER_CLAIMED, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "ledger with claimed row"], cwd=repo, check=True)
    wt2 = tmp_path / "secondary"
    subprocess.run(["git", "worktree", "add", "-q", str(wt2), "-b", "side", "main"],
                   cwd=repo, check=True)
    return repo, wt2


def test_claim_collision_red_staged_in_secondary_worktree(tmp_path, monkeypatch):
    repo, wt2 = _claimed_repo_with_second_worktree(tmp_path)
    text = (wt2 / "DOCKET.md").read_text(encoding="utf-8")
    (wt2 / "DOCKET.md").write_text(
        text.replace("| session-A |", "| session-B |"), encoding="utf-8")
    subprocess.run(["git", "add", "DOCKET.md"], cwd=wt2, check=True)
    # Decoy env roots pointing at the PRIMARY worktree (whose staged state is
    # clean): an implementation that trusted any env var would look there and
    # pass. The shipped check must resolve the COMMITTING worktree and fail.
    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("DOCKET_ROOT", str(repo))
    r = run_check("check_claim_collision.py", "DOCKET.md", cwd=wt2)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "owned by 'session-A'" in r.stdout and "'session-B'" in r.stdout


def test_claim_collision_green_first_claim(tmp_path):
    _, wt2 = _claimed_repo_with_second_worktree(tmp_path)
    text = (wt2 / "DOCKET.md").read_text(encoding="utf-8")
    (wt2 / "DOCKET.md").write_text(
        text.replace("| UB-102 | OPEN | Retry loop | symptom | - |",
                     "| UB-102 | OPEN | Retry loop | symptom | session-C |"),
        encoding="utf-8")
    subprocess.run(["git", "add", "DOCKET.md"], cwd=wt2, check=True)
    r = run_check("check_claim_collision.py", "DOCKET.md", cwd=wt2)
    assert r.returncode == 0, r.stdout + r.stderr


def test_claim_collision_zero_parse_staged_is_loud(tmp_path):
    """A staged ledger that parses to zero rows while non-empty (renamed
    prefix, mangled table) must exit 2, not silently bless the commit."""
    repo = tmp_path / "primary"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "DOCKET.md").write_text(LEDGER_CLAIMED, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    (repo / "DOCKET.md").write_text(
        "| DOC-1 | OPEN | renamed prefix | symptom | S9 | - | filed |\n",
        encoding="utf-8")
    subprocess.run(["git", "add", "DOCKET.md"], cwd=repo, check=True)
    r = run_check("check_claim_collision.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unreadable" in (r.stdout + r.stderr).lower()


def test_claim_collision_green_release(tmp_path):
    _, wt2 = _claimed_repo_with_second_worktree(tmp_path)
    text = (wt2 / "DOCKET.md").read_text(encoding="utf-8")
    (wt2 / "DOCKET.md").write_text(
        text.replace("| session-A |", "| - |"), encoding="utf-8")
    subprocess.run(["git", "add", "DOCKET.md"], cwd=wt2, check=True)
    r = run_check("check_claim_collision.py", "DOCKET.md", cwd=wt2)
    assert r.returncode == 0, r.stdout + r.stderr


def test_phantom_ids_zero_parse_ledger_is_loud(tmp_path):
    """R2-C-1 arm: a non-empty ledger parsing to zero rows must exit 2 --
    with a renamed prefix BOTH sides go empty (0 minted, 0 UB-cites) and the
    old behavior blessed the void with 'PASS (0 minted)'."""
    repo = _scratch_repo(tmp_path, {"DOCKET.md": FIX / "phantom_ledger.md"})
    (repo / "DOCKET.md").write_text(
        "| DOC-1 | OPEN | renamed prefix | symptom | - | - | filed |\n",
        encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "renamed"], cwd=repo, check=True)
    r = run_check("check_phantom_ids.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unreadable" in (r.stdout + r.stderr).lower()


def test_state_transitions_zero_parse_is_loud(tmp_path):
    """R2-C-1 arm: old+new both non-empty but parsing to zero rows must exit
    2 -- the old behavior reported 'no silent transition' over a comparison
    of nothing with nothing."""
    old = tmp_path / "old.md"; new = tmp_path / "new.md"
    old.write_text("| DOC-1 | DONE | renamed | symptom | - | - | closed by commit abc1234 |\n",
                   encoding="utf-8")
    new.write_text("| DOC-1 | OPEN | renamed | symptom | - | - | quietly reopened |\n",
                   encoding="utf-8")
    r = run_check("check_state_transitions.py", "--old", str(old), "--new", str(new))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unreadable" in (r.stdout + r.stderr).lower()


def test_pending_markers_zero_parse_is_loud(tmp_path):
    """R2-C-1 arm, same class: 'PASS: 0 pending' over a ledger that parsed to
    zero rows is a reading of nothing."""
    l = tmp_path / "DOCKET.md"
    l.write_text("| DOC-1 | OPEN | renamed | symptom | - | - | filed |\n",
                 encoding="utf-8")
    r = run_check("check_pending_markers.py", str(l))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unreadable" in (r.stdout + r.stderr).lower()


# ---------------------------------------------------------- pending markers

def test_pending_markers_red_reconcile_mode():
    r = run_check("check_pending_markers.py", str(FIX / "pending_two.md"), "--reconcile")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "2 row(s) still pending" in r.stdout


def test_pending_markers_green_reconcile_mode():
    r = run_check("check_pending_markers.py", str(FIX / "pending_none.md"), "--reconcile")
    assert r.returncode == 0, r.stdout + r.stderr


def test_pending_markers_informational_lists_file_line():
    r = run_check("check_pending_markers.py", str(FIX / "pending_two.md"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert ":5: UB-ID-PENDING" in r.stdout and ":6: UB-ID-PENDING" in r.stdout


EMPTY_LEDGER = """\
# DOCKET

| id | state | title | scope | owner | blocked-by | notes |
|----|-------|-------|-------|-------|------------|-------|
"""


def test_empty_header_only_ledger_is_not_an_error(tmp_path):
    """R3-I-1: a correctly-shaped table with zero rows filed yet (a fresh
    adopter who cleared the sample rows) is a LEGITIMATE state, not the
    wrong-prefix ambiguity -- the zero-parse guard must not fire, and the
    checks proceed honestly over zero rows."""
    l = tmp_path / "DOCKET.md"
    l.write_text(EMPTY_LEDGER, encoding="utf-8")
    r = run_check("check_duplicate_ids.py", str(l))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "0 rows" in r.stdout
    r2 = run_check("check_pending_markers.py", str(l))
    assert r2.returncode == 0, r2.stdout + r2.stderr


def test_wrong_prefix_still_loud_after_empty_carveout(tmp_path):
    """NEGATIVE CONTROL FOR the R3-I-1 carve-out. DO NOT DELETE AS REDUNDANT.
    Protects: the zero-parse guard's RED arm after the empty-ledger exemption.
    Without it, unreadable_rows could be loosened to 'always []' -- every
    empty-ledger test above would still pass, and the wrong-prefix trap the
    guard exists for would return silently."""
    l = tmp_path / "DOCKET.md"
    l.write_text(EMPTY_LEDGER + "| DOC-1 | OPEN | renamed | symptom | - | - | filed |\n",
                 encoding="utf-8")
    r = run_check("check_duplicate_ids.py", str(l))
    assert r.returncode == 2, r.stdout + r.stderr


def test_leading_pipe_stripped_row_is_still_loud(tmp_path):
    """R4 probe: a row that lost its LEADING pipe (hand edit, bad conflict
    resolution) is neither parseable nor '|'-prefixed -- the empty-ledger
    carve-out must not swallow it as 'nothing filed yet'. Any line still
    carrying a row's pipe density is data-shaped, leading pipe or not."""
    l = tmp_path / "DOCKET.md"
    l.write_text(EMPTY_LEDGER +
                 "UB-101 | OPEN | lost its leading pipe | symptom | - | - | filed |\n",
                 encoding="utf-8")
    r = run_check("check_duplicate_ids.py", str(l))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unreadable" in r.stdout.lower()


def test_prose_with_pipes_on_an_empty_ledger_is_not_loud(tmp_path):
    """GREEN twin of the row-shape guard, on an EMPTY ledger so nothing else
    can carry the assertion.

    R4-I-1: the previous version of this test put the prose line in a ledger
    that ALSO held a real parsed row -- so it passed under any threshold
    (proven by mutation: dropping the pipe count to >=1 left it green). The
    fixture now confounds nothing: zero rows filed, prose with four pipes
    and prose naming the state words, and the checks must still be quiet."""
    l = tmp_path / "DOCKET.md"
    l.write_text(
        "# DOCKET\n\n"
        "> a row reads: id | state | title | scope, and a state is OPEN or DONE\n"
        "> notes may mention a | character or even a|b|c|d here\n\n"
        "| id | state | title | scope | owner | blocked-by | notes |\n"
        "|----|-------|-------|-------|-------|------------|-------|\n",
        encoding="utf-8")
    for script in ("check_duplicate_ids.py", "check_pending_markers.py"):
        r = run_check(script, str(l))
        assert r.returncode == 0, f"{script}: {r.stdout}{r.stderr}"


def test_unreadable_row_beside_good_rows_is_loud(tmp_path):
    """R4-C-1: the guard must fire on ANY row-shaped line that failed to
    parse -- not only when the whole file parses to zero rows. One good row
    used to mask every broken sibling, so a duplicate, a pending row, a
    claim theft and a silent reopen all hid behind a clean PASS."""
    l = tmp_path / "DOCKET.md"
    l.write_text(
        "| UB-101 | OPEN | good row | symptom | - | - | filed |\n"
        "UB-102 | OPEN | lost its leading pipe | symptom | - | - | filed |\n",
        encoding="utf-8")
    r = run_check("check_duplicate_ids.py", str(l))
    assert r.returncode == 2, r.stdout + r.stderr
    assert ":2" in r.stdout, r.stdout


def test_unreadable_row_hides_nothing_from_the_other_checks(tmp_path):
    """R4-C-1, the same defect through the checks the reviewer proved blind:
    a broken sibling row must not let a real duplicate / a real pending row
    slip past while other rows parse."""
    l = tmp_path / "DOCKET.md"
    l.write_text(
        "| UB-101 | OPEN | good row | symptom | - | - | filed |\n"
        "UB-101 | OPEN | duplicate, unparseable | symptom | - | - | filed |\n"
        "UB-ID-PENDING | OPEN | pending, unparseable | symptom | - | - | filed |\n",
        encoding="utf-8")
    for script, args in (("check_duplicate_ids.py", []),
                         ("check_pending_markers.py", ["--reconcile"])):
        r = run_check(script, str(l), *args)
        assert r.returncode == 2, f"{script} returned {r.returncode}: {r.stdout}"


def test_prefix_rename_single_site_is_complete(tmp_path):
    """R3-C-1: renaming the id prefix must be a ONE-SITE edit (ID_PREFIX in
    checks/_ledger.py) after which the whole check suite works against the
    new prefix -- including the pending sentinel, the reconciliation gate,
    and the pending-row exclusion in the duplicate check. R3 proved the old
    two-site instruction silently defeated the reconciliation gate and
    produced a silent pass on a real claim theft."""
    import shutil
    scratch = tmp_path / "checks"
    shutil.copytree(CHECKS, scratch)
    lg = scratch / "_ledger.py"
    text = lg.read_text(encoding="utf-8")
    assert 'ID_PREFIX = "UB-"' in text, "single rename site missing from _ledger.py"
    lg.write_text(text.replace('ID_PREFIX = "UB-"', 'ID_PREFIX = "DOC-"'),
                  encoding="utf-8")

    ledger = tmp_path / "DOCKET.md"
    ledger.write_text(
        "| DOC-101 | OPEN | first matter | symptom | - | - | filed |\n"
        "| DOC-ID-PENDING | OPEN | second matter | symptom | - | - | filed by S1 |\n"
        "| DOC-ID-PENDING | OPEN | third matter | symptom | - | - | filed by S2 |\n",
        encoding="utf-8")

    def run_scratch(script, *args, cwd=None):
        return subprocess.run([sys.executable, str(scratch / script), *args],
                              capture_output=True, text=True, encoding="utf-8", cwd=cwd)

    # Reconciliation gate sees BOTH renamed pending markers (R3's silent-zero defeat).
    r = run_scratch("check_pending_markers.py", str(ledger), "--reconcile")
    assert r.returncode == 1 and "2 row(s) still pending" in r.stdout, r.stdout + r.stderr
    # Two pending rows are NOT a duplicate-id false positive (pending excluded).
    r = run_scratch("check_duplicate_ids.py", str(ledger))
    assert r.returncode == 0, r.stdout + r.stderr
    # Phantom citations track the renamed prefix, both arms.
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "DOCKET.md").write_text(
        "| DOC-101 | OPEN | first matter | symptom | - | - | filed |\n", encoding="utf-8")
    (repo / "notes.txt").write_text("see DOC-101 and DOC-999\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    r = run_scratch("check_phantom_ids.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "cites DOC-999" in r.stdout, r.stdout
    assert "cites DOC-101" not in r.stdout, r.stdout


# -------------------------------------------------------- state transitions

def test_state_transitions_red_silent_reopen():
    r = run_check("check_state_transitions.py",
                  "--old", str(FIX / "st_old.md"),
                  "--new", str(FIX / "st_new_silent.md"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "UB-101: DONE -> OPEN" in r.stdout


def test_state_transitions_green_loud_reopen():
    r = run_check("check_state_transitions.py",
                  "--old", str(FIX / "st_old.md"),
                  "--new", str(FIX / "st_new_loud.md"))
    assert r.returncode == 0, r.stdout + r.stderr


# ==========================================================================
#                              v0.2 additions
# ==========================================================================
# Installer/CI parity, range-aware transitions, commit-id citation, closure
# references.
#
# Every guard below ships both arms. Where a GREEN arm could pass VACUOUSLY
# -- an extractor that found no paths, a range that compared no edges, a
# checker that examined no rows -- it asserts on the count the instrument
# reports, not merely on its exit code. A green that could not have been red
# is not evidence, and its emptiness is invisible precisely because green is
# the colour you were expecting.

import re as _re
import shutil as _shutil

REPO = Path(__file__).parent.parent
INSTALLER = REPO / "templates" / "install.sh"

# An adopter repo gets checks/ and tests/ but not templates/, so tests that run
# a script from templates/ cannot run there. They skip with a reason instead of
# failing. `installer_test` applies the skip, tags the test `installer` (so a
# run can select exactly these), and registers it for the armed-control and
# the adopter-suite test, which count them exactly.
_needs_installer = pytest.mark.skipif(
    not INSTALLER.is_file(),
    reason="templates/install.sh is not installed in an adopter repository; "
           "this test exercises the installer itself")
INSTALLER_TESTS = []


def installer_test(fn):
    INSTALLER_TESTS.append(fn)
    return pytest.mark.installer(_needs_installer(fn))


LEDGER_HEAD = ("| id | state | title | scope | owner | blocked-by | notes |\n"
               "|----|-------|-------|-------|-------|------------|-------|\n")


def _ledger(*rows: str) -> str:
    return LEDGER_HEAD + "".join(
        r if r.endswith("\n") else r + "\n" for r in rows)


def _g(repo: Path, *args: str, check: bool = True):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True,
                          text=True, encoding="utf-8", check=check)


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _g(path, "init", "-q", "-b", "main")
    _g(path, "config", "user.email", "t@t")
    _g(path, "config", "user.name", "t")
    return path


def _commit(repo: Path, message: str, files: dict[str, str] | None = None) -> str:
    for name, text in (files or {}).items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    _g(repo, "add", "-A")
    _g(repo, "commit", "-qm", message)
    return _g(repo, "rev-parse", "HEAD").stdout.strip()


# ------------------------------------------------ installer / CI parity

# The ONE instrument in this file with no shipped artifact behind it: nothing
# in checks/ extracts invoked paths from a workflow, so this test IS the
# extractor. Declared rather than left implicit; its own vacuity is guarded
# by the >= assertions at every call site.
_INVOKED_PATH_RE = _re.compile(
    r"\b((?:checks|tests)/[A-Za-z0-9_./-]+\.(?:py|md|txt))\b")


def _workflow_invoked_paths(text: str) -> set[str]:
    return set(_INVOKED_PATH_RE.findall(text))


def _source_copy(tmp_path: Path) -> Path:
    """A faithful copy of everything the installer reads, so a mutated copy
    of the installer still resolves its own source tree."""
    src = tmp_path / "docket-src"
    ignore = _shutil.ignore_patterns("__pycache__", "*.pyc")
    for rel in ("checks", "tests", "templates", ".github"):
        _shutil.copytree(REPO / rel, src / rel, ignore=ignore)
    return src


def _run_installer(installer: Path, target: Path, *flags: str):
    # `sh`, matching the script's own shebang, and POSIX-style paths.
    # Measured on Windows: the bare bash.EXE shipped with Git resolves a
    # drive-letter path against its own root and reports "No such file or
    # directory" for a script that is plainly there, while sh.EXE beside it
    # reads the same path fine. Both exist on CI, so the shebang decides.
    shell = _shutil.which("sh") or _shutil.which("bash") or "sh"
    return subprocess.run(
        [shell, Path(installer).as_posix(), *flags, Path(target).as_posix()],
        capture_output=True, text=True, encoding="utf-8")


@installer_test
def test_installed_workflow_paths_all_resolve(tmp_path):
    """THE control for the v0.1 quick-start defect.

    The installer copied three files into .docket-checks/ while the workflow
    it told you to copy invoked five checks under checks/ plus the suite
    under tests/. Both artifacts were internally consistent; only their
    INTERSECTION was wrong, which is why reading either one alone missed it
    for a whole release. This reads the INSTALLED workflow, extracts every
    path it invokes, and asserts each is on disk in the target."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "an adopter repo\n"})

    r = _run_installer(INSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr

    invoked = _workflow_invoked_paths(
        (target / ".github/workflows/ledger-ci.yml").read_text(encoding="utf-8"))
    # Non-vacuity: an extractor that found nothing would make the loop below
    # trivially true. Seven checks are invoked by name, plus the suite.
    assert len(invoked) >= 8, f"extractor found only {sorted(invoked)}"

    missing = [p for p in sorted(invoked) if not (target / p).is_file()]
    assert not missing, f"workflow invokes paths the installer did not place: {missing}"

    # And checks/ travelled WHOLE, not just the invoked subset:
    # check_state_transitions.py is invoked by the range driver, not by CI
    # directly, so path-extraction alone would never have asked for it.
    src_checks = {p.name for p in (REPO / "checks").glob("*.py")}
    assert len(src_checks) >= 7, f"source checks/ looks wrong: {sorted(src_checks)}"
    absent = [n for n in sorted(src_checks) if not (target / "checks" / n).is_file()]
    assert not absent, f"checks/ did not travel whole: {absent}"


@installer_test
def test_parity_control_fails_when_the_installer_drops_the_suite(tmp_path):
    """NEGATIVE CONTROL FOR test_installed_workflow_paths_all_resolve.
    DO NOT DELETE AS REDUNDANT.

    Protects: that the parity test can actually go RED. Without it, the
    parity assertions could be weakened -- or the extractor could quietly
    match nothing -- and the suite would stay green while the v0.1 defect
    was fully reintroduced. This reproduces that defect by neutering the
    installer's copy step and requires the parity predicate to catch it.

    Note what the neutered installer does: it EXITS 0. A broken install that
    reports success is the exact shape of the original bug, and is why the
    parity predicate, not the installer's exit code, is the guard."""
    # Mutate a faithful COPY of the source tree: the installer resolves its
    # own source from dirname($0)/.., so a lone script in a temp dir would
    # fail for the wrong reason and the control would prove nothing.
    src_tree = _source_copy(tmp_path)
    broken = src_tree / "templates" / "install.sh"
    src = broken.read_text(encoding="utf-8")
    assert "find checks tests -type f" in src, "installer copy step moved"
    broken.write_text(src.replace("find checks tests -type f",
                                  "find checks -type f"), encoding="utf-8")

    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "an adopter repo\n"})
    r = _run_installer(broken, target)
    assert r.returncode == 0, "the neutered installer is expected to still exit 0"

    invoked = _workflow_invoked_paths(
        (target / ".github/workflows/ledger-ci.yml").read_text(encoding="utf-8"))
    assert len(invoked) >= 8
    missing = [p for p in sorted(invoked) if not (target / p).is_file()]
    assert missing, ("the parity predicate stayed green over an install with "
                     "no tests/ -- it cannot fail, so it proves nothing")
    assert any(p.startswith("tests/") for p in missing), missing


@installer_test
def test_installer_refuses_to_clobber_a_differing_file(tmp_path):
    """An adopter with their own checks/check_duplicate_ids.py is told, not
    silently overwritten."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {
        "README.md": "an adopter repo\n",
        "checks/check_duplicate_ids.py": "# mine, not yours\n"})
    r = _run_installer(INSTALLER, target)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "refusing to overwrite" in (r.stdout + r.stderr).lower()
    assert (target / "checks/check_duplicate_ids.py").read_text(
        encoding="utf-8") == "# mine, not yours\n"


@installer_test
def test_installing_twice_does_not_duplicate_the_gitattributes_rule(tmp_path):
    """Idempotence, and a real defect this caught.

    The first version keyed its "already installed" test on the stanza's own
    comment text. Run against a repo that had written its OWN equivalent rule
    -- as this repository had -- the marker was absent, the stanza was
    appended anyway, and `.gitattributes` ended up declaring `DOCKET.md text
    eol=lf` twice. Found by running the installer against Docket itself.

    Both arms live here: a repo with a pre-existing hand-written rule must be
    left alone, and two consecutive installs must leave exactly one rule."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {
        "README.md": "an adopter repo\n",
        ".gitattributes": "# my own rule, written by hand\nDOCKET.md text eol=lf\n"})

    for _ in range(2):
        r = _run_installer(INSTALLER, target)
        assert r.returncode == 0, r.stdout + r.stderr

    attrs = (target / ".gitattributes").read_text(encoding="utf-8")
    rules = [ln for ln in attrs.splitlines()
             if ln.strip().startswith("DOCKET.md")]
    assert len(rules) == 1, f"ledger rule declared {len(rules)} times:\n{attrs}"


@installer_test
def test_installer_leaves_an_existing_ledger_alone(tmp_path):
    """A repo that already keeps a docket must not have it replaced by the
    starter. Three sample rows overwriting live work would be the most
    expensive possible install bug."""
    target = _init_repo(tmp_path / "adopter")
    mine = _ledger("| UB-77 | OPEN | my real matter | symptom | - | - | filed |")
    _commit(target, "initial", {"DOCKET.md": mine})
    r = _run_installer(INSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (target / "DOCKET.md").read_text(encoding="utf-8") == mine
    assert "left untouched" in r.stdout


# ----------------------------------- installed copy and empty-repo behaviour

_IS_DOCKET_SOURCE_TREE = (REPO / "PROTOCOL.md").is_file() and INSTALLER.is_file()


@pytest.mark.skipif(
    not _IS_DOCKET_SOURCE_TREE,
    reason="not the Docket source tree (PROTOCOL.md and templates/install.sh "
           "are not both present at the repository root)")
def test_installer_tests_are_armed_in_the_source_tree():
    """NEGATIVE CONTROL FOR the skip-when-templates-is-absent marker.
    DO NOT DELETE AS REDUNDANT.

    Protects: every installer test in Docket's own repository. If the marker's
    condition were wrongly true here, all of them would skip and the suite
    would stay green with nobody having run them. This control deliberately
    does NOT carry that marker (a skippable control skips itself on exactly the
    defect it guards); it is gated on a signal the installer never copies,
    PROTOCOL.md, so an adopter repo skips it and this repo cannot.

    It reads the skip conditions off the real decorated functions (the
    predicate pytest itself consults) and checks collection by asking pytest."""
    assert INSTALLER_TESTS, "no installer tests registered"
    for fn in INSTALLER_TESTS:
        conditions = [m.args[0] for m in fn.pytestmark if m.name == "skipif"]
        assert conditions, f"{fn.__name__} lost its skip marker"
        assert not any(conditions), f"{fn.__name__} would be skipped here"
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "installer",
         "-p", "no:cacheprovider", str(Path(__file__))],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    ids = [ln for ln in collected.stdout.splitlines() if "::" in ln]
    assert len(ids) == len(INSTALLER_TESTS), collected.stdout + collected.stderr


@installer_test
def test_installed_suite_passes_in_an_adopter_repo(tmp_path):
    """The installed copy of the installer self-tests must not fail.

    The installer copies checks/ and tests/ but not templates/, and every test
    marked `installer` in this file runs a script from templates/. In an
    adopter repo they used to fail with "No such file or directory", so the
    installer's own final step exited 1 and never printed its OK line.

    Protects: the adopter's first run of the installed suite. Without it, an
    installer test could regress to failing in an adopter repo while every
    other test here stays green, because this repository always has
    templates/ and so never sees the failure. The nested installer run inside
    pytest skips the suite step by design, so the suite is run here directly."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "an adopter repo\n"})
    r = _run_installer(INSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (target / "templates").exists()  # the premise: no templates/

    suite = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_checks.py", "-q", "-rs",
         "-p", "no:cacheprovider", f"--basetemp={(tmp_path / 'pt').as_posix()}",
         "-m", "installer"],
        cwd=target, capture_output=True, text=True, encoding="utf-8")
    out = suite.stdout + suite.stderr
    assert suite.returncode == 0, out
    # Exact, not a lower bound: every registered installer test must have been
    # selected and skipped (with a reason naming templates/), none deselected.
    assert f"{len(INSTALLER_TESTS)} skipped" in out, out
    assert "passed" not in out and "failed" not in out, out
    assert "templates" in out, out


@installer_test
def test_installer_on_a_repo_with_no_commits_installs_fully(tmp_path):
    """A target with no commits is a complete install, not a half-install.

    The closure check reads HEAD, so with no commit it used to stop the
    installer with "--head HEAD does not resolve" and exit non-zero, after the
    files were already written. The check is post-install verification only,
    so it is now skipped with a stated reason.

    Protects: an adopter who runs `git init` and then the installer. Without
    it, that path regresses to a non-zero exit with files written and the
    suite never reached; no other test installs into a repo with no HEAD."""
    target = _init_repo(tmp_path / "adopter")  # no commit
    r = _run_installer(INSTALLER, target)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "ERROR" not in out, out
    assert "current branch has no commits yet" in out and "closure" in out.lower(), out
    for rel in ("checks/check_duplicate_ids.py", "tests/test_checks.py",
                "DOCKET.md", ".github/workflows/ledger-ci.yml", ".gitattributes"):
        assert (target / rel).is_file(), f"{rel} missing after install"
    assert "docket-checks" in _hook_path(target).read_text(encoding="utf-8")


@installer_test
def test_installer_names_the_branch_not_the_repository_on_an_unborn_branch(tmp_path):
    """The notice must be true when the repository HAS commits but the current
    branch does not (an orphan checkout).

    Protects: the accuracy of the skip notice. Without it, the wording could
    drift back to "this repository has no commits", which is false here and
    would send the user looking for a problem that does not exist."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "an adopter repo\n"})
    _g(target, "checkout", "-q", "--orphan", "fresh")
    r = _run_installer(INSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "current branch has no commits yet" in r.stdout, r.stdout
    assert "repository has no commits" not in r.stdout, r.stdout


@installer_test
def test_installer_on_a_shallow_clone_installs_fully(tmp_path):
    """A shallow clone is a complete install, not a half-install.

    Reachability of a closure commit cannot be decided in a shallow history,
    so the closure check refuses to run there (exit 2) -- after the installer
    had already written its files. That check is verification only, so the
    installer now skips it with a notice, as it does for an unborn branch.

    Protects: adopters whose CI or tooling clones with --depth. Without it,
    that path leaves files and a hook written but exits non-zero with the suite
    never run; the no-commits test above does not reach this branch."""
    origin = _init_repo(tmp_path / "origin")
    _commit(origin, "one", {"README.md": "one\n"})
    _commit(origin, "two", {"README.md": "two\n"})
    shallow = tmp_path / "shallow"
    cloned = subprocess.run(
        ["git", "clone", "-q", "--depth", "1", origin.as_uri(), str(shallow)],
        capture_output=True, text=True, encoding="utf-8")
    assert cloned.returncode == 0, cloned.stderr
    assert _g(shallow, "rev-parse", "--is-shallow-repository").stdout.strip() == "true"
    r = _run_installer(INSTALLER, shallow)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "ERROR" not in out and "shallow clone" in out, out
    assert (shallow / "checks/check_closure_references.py").is_file()


@installer_test
def test_a_conflicting_file_aborts_before_anything_is_written(tmp_path):
    """NEGATIVE CONTROL FOR the install-is-all-or-nothing claim.
    DO NOT DELETE AS REDUNDANT.

    The installer refuses to overwrite a differing file, but it used to find
    that out part-way through copying, after other files and directories were
    already written. Now every conflict is found first.

    Protects: the claim that a refused install leaves the repository exactly as
    it was. Without it, the older partial-write behaviour passes
    test_installer_refuses_to_clobber_a_differing_file, which only looks at the
    one differing file."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {
        "README.md": "an adopter repo\n",
        "checks/check_pending_markers.py": "# mine, not yours\n"})

    def tree():
        return sorted(p.relative_to(target).as_posix() for p in target.rglob("*")
                      if ".git" not in p.relative_to(target).parts)

    before = tree()
    r = _run_installer(INSTALLER, target)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "nothing was written" in (r.stdout + r.stderr).lower()
    assert tree() == before, set(tree()) ^ set(before)
    assert not _hook_path(target).exists()


@installer_test
def test_installer_still_runs_the_closure_check_when_a_commit_exists(tmp_path):
    """NEGATIVE CONTROL FOR the no-commits and shallow skips.
    DO NOT DELETE AS REDUNDANT.

    Protects: the closure-reference verification for every normal adopter.
    Without it, an over-broad skip (always skipping the check) would pass the
    no-commits and shallow tests above, and an installed ledger would never be
    checked at install time, silently."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "an adopter repo\n"})
    r = _run_installer(INSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[closure-refs] PASS" in r.stdout, r.stdout
    assert "SKIPPED" not in r.stdout


# ------------------------------------------------------------- uninstaller

UNINSTALLER = REPO / "templates" / "uninstall.sh"
DOCKET_FILES = ("checks/check_duplicate_ids.py", "checks/_ledger.py",
                "tests/test_checks.py", ".github/workflows/ledger-ci.yml")


def _adopter_with_user_files(tmp_path: Path) -> Path:
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {
        "README.md": "an adopter repo\n",
        "tests/test_mine.py": "def test_mine():\n    assert True\n",
        "checks/lint_mine.py": "# my own lint\n"})
    return target


def _hook_path(repo: Path) -> Path:
    rel = _g(repo, "rev-parse", "--git-path", "hooks/pre-commit").stdout.strip()
    return (repo / rel).resolve()


@installer_test
def test_uninstall_removes_docket_files_and_keeps_the_users(tmp_path):
    """User files that share tests/ and checks/ survive uninstall.

    The installer copies into whatever checks/ and tests/ the adopter already
    has; only a file at the very same path as Docket's is refused. An uninstall
    that deleted the two directories took the adopter's own work with it.

    Protects: the adopter's files. Without it, an uninstall that removes the
    directories (or everything matching a pattern) passes every other test
    here, since none of them put a user file next to Docket's."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    for rel in DOCKET_FILES:
        assert (target / rel).is_file(), rel
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    for rel in DOCKET_FILES:
        assert not (target / rel).exists(), f"{rel} still present"
    assert (target / "tests/test_mine.py").read_text(encoding="utf-8") == \
        "def test_mine():\n    assert True\n"
    assert (target / "checks/lint_mine.py").read_text(encoding="utf-8") == \
        "# my own lint\n"
    assert not (target / "tests/fixtures").exists()
    assert not (target / ".github").exists()  # created by the installer
    assert not (target / "DOCKET.md").exists()  # untouched starter ledger
    status = _g(target, "status", "--porcelain").stdout
    assert status.strip() == "", status  # back to the committed state


@installer_test
def test_uninstall_leaves_changed_files_and_says_so(tmp_path):
    """A Docket file the user has since edited, and a ledger they have filled
    in, are left in place with a message.

    Protects: work done after the install. Without it, the uninstaller could
    delete by name and the hash comparison would never be exercised; the
    unmodified-file test above passes under either behaviour."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    check = target / "checks/check_duplicate_ids.py"
    with check.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n# local tweak\n")
    ledger = target / "DOCKET.md"
    with ledger.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("| UB-104 | OPEN | my row | symptom | - | - | filed |\n")
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "left in place" in r.stdout and "checks/check_duplicate_ids.py" in r.stdout
    assert "# local tweak" in check.read_text(encoding="utf-8")
    assert "UB-104" in ledger.read_text(encoding="utf-8")
    assert not (target / "checks/_ledger.py").exists()  # unmodified: removed


@installer_test
def test_uninstall_deletes_a_hook_that_only_docket_wrote(tmp_path):
    """If nothing but Docket's block (and the shebang) remains, the hook goes.

    Protects: a clean repository after uninstall. Without it, an empty
    executable stub is left behind on every repo that had no hook before."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    assert _hook_path(target).is_file()
    assert _run_installer(UNINSTALLER, target).returncode == 0
    assert not _hook_path(target).exists()


@installer_test
def test_uninstall_twice_is_harmless(tmp_path):
    """A second uninstall changes nothing and exits 0.

    Protects: re-running after a partial failure or by habit. Without it, a
    second run could fail on the missing manifest or delete something the user
    has since put back at a Docket path."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    assert _run_installer(UNINSTALLER, target).returncode == 0
    (target / "checks/_ledger.py").write_text("# the user's own file\n",
                                              encoding="utf-8")
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "nothing to uninstall" in r.stdout.lower()
    assert (target / "checks/_ledger.py").read_text(encoding="utf-8") == \
        "# the user's own file\n"


@installer_test
def test_uninstall_removes_only_the_gitattributes_stanza(tmp_path):
    """The user's own .gitattributes lines before and after the stanza stay.

    Protects: the adopter's attribute rules. Without it, deleting the file (or
    everything from the stanza to the end of the file) passes whenever the
    stanza was the only content, which is the case in every other test."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "x\n",
                                ".gitattributes": "*.png binary\n"})
    assert _run_installer(INSTALLER, target).returncode == 0
    with (target / ".gitattributes").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("*.jpg binary\n")
    assert _run_installer(UNINSTALLER, target).returncode == 0
    attrs = (target / ".gitattributes").read_text(encoding="utf-8")
    assert attrs.splitlines() == ["*.png binary", "*.jpg binary"], attrs


# ------------------------------- hardening: boundaries, targets, manifest

def _manifest_path(repo: Path) -> Path:
    rel = _g(repo, "rev-parse", "--git-path", "docket-install.manifest").stdout.strip()
    return (repo / rel).resolve()


def _tree(repo: Path):
    """Every file and directory under repo, .git included, with file bytes."""
    out = {}
    for p in sorted(repo.rglob("*")):
        key = p.relative_to(repo).as_posix()
        out[key] = p.read_bytes() if p.is_file() else None
    return out


def _stanza_closing_line(text: str) -> str:
    lines = text.splitlines()
    return next(ln for ln in reversed(lines) if _re.fullmatch(r"# -+\s*", ln))


@installer_test
def test_uninstall_leaves_gitattributes_alone_when_the_stanza_boundary_is_gone(tmp_path):
    """The stanza's closing line looks decorative; deleting it must not make the
    uninstaller cut through the user's rules that follow.

    Protects: the adopter's own .gitattributes rules. Without it, a cut that
    starts at the opening line and runs to a closing line that no longer exists
    deletes everything after it -- and says the user's rules were kept. The
    shipped stanza-only test keeps the closing line, so it passes either way."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "x\n", ".gitattributes": "*.png binary\n"})
    assert _run_installer(INSTALLER, target).returncode == 0
    attrs = target / ".gitattributes"
    text = attrs.read_text(encoding="utf-8")
    closing = _stanza_closing_line(text)
    kept = "".join(ln for ln in text.splitlines(keepends=True) if ln.rstrip() != closing.rstrip())
    with attrs.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(kept.replace("\r", "") + "*.jpg binary\n*.pdf binary\n")
    before = attrs.read_bytes()
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert attrs.read_bytes() == before, attrs.read_text(encoding="utf-8")
    assert "by hand" in r.stdout and ".gitattributes" in r.stdout, r.stdout
    assert _manifest_path(target).is_file(), "manifest deleted with an entry unprocessed"


@installer_test
def test_uninstall_leaves_gitattributes_alone_when_the_stanza_was_edited(tmp_path):
    """A stanza whose text differs from what was installed is not Docket's any
    more; the uninstaller compares it to the hash stored at install time.

    Protects: rules the user wrote INSIDE the stanza. Without it, the markers
    alone would be trusted and a hand-edited stanza removed wholesale."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "x\n", ".gitattributes": "*.png binary\n"})
    assert _run_installer(INSTALLER, target).returncode == 0
    attrs = target / ".gitattributes"
    edited = attrs.read_text(encoding="utf-8").replace(
        "DOCKET.md text eol=lf", "DOCKET.md text eol=lf\n*.csv text eol=lf")
    with attrs.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(edited.replace("\r", ""))
    before = attrs.read_bytes()
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert attrs.read_bytes() == before
    assert "by hand" in r.stdout, r.stdout


@installer_test
def test_install_refuses_a_subdirectory_target(tmp_path):
    """Installing into a subdirectory of a repository is refused, nothing written.

    The installer validated the path with --show-toplevel but then wrote under
    the subdirectory, while the hook and the manifest assume the top level.

    Protects: a user who runs the installer with `.` from inside a project
    subfolder. Without it, 30 files land in the wrong place, the hook looks for
    checks/ at the top level, and the uninstaller cannot find them."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "x\n", "sub/keep.txt": "keep\n"})
    before = _tree(target)
    r = _run_installer(INSTALLER, target / "sub")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "top level" in (r.stdout + r.stderr), r.stdout + r.stderr
    assert _tree(target) == before


@installer_test
def test_uninstall_from_a_subdirectory_uses_the_top_level(tmp_path):
    """Uninstall resolves the top level and says so; it never reports success
    over files it did not look for.

    Protects: the install record. Without it, a subdirectory target joined every
    manifest path to the wrong directory, found nothing, deleted the hook and
    the manifest anyway and printed "uninstalled" with all the files in place."""
    target = _adopter_with_user_files(tmp_path)
    (target / "sub").mkdir()
    with (target / "sub/note.txt").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("n\n")
    assert _run_installer(INSTALLER, target).returncode == 0
    r = _run_installer(UNINSTALLER, target / "sub")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "top level" in r.stdout, r.stdout
    for rel in DOCKET_FILES:
        assert not (target / rel).exists(), f"{rel} still present"
    assert (target / "sub/note.txt").is_file()
    assert not _manifest_path(target).exists()


@installer_test
def test_uninstall_ignores_tampered_manifest_entries(tmp_path):
    """Manifest file and directory entries that point outside the repository are
    ignored and kept in the manifest.

    Protects: files outside the working tree. Without it, a hand-edited or
    mis-merged manifest line such as `file <hash> ../x` deletes a file one
    directory above the repository, and `dir ..` reaches for the parent. The manifest is also
    not deleted while an entry is unprocessed."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    outside = tmp_path / "outside.txt"
    with outside.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("not yours to delete\n")
    outside_hash = _g(target, "hash-object", "--no-filters", str(outside)).stdout.strip()
    manifest = _manifest_path(target)
    with manifest.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"file\t{outside_hash}\t../outside.txt\n")
        fh.write(f"file\t{outside_hash}\t{outside.as_posix()}\n")
        fh.write("dir\t..\n")
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert outside.read_text(encoding="utf-8") == "not yours to delete\n"
    assert tmp_path.is_dir() and target.is_dir()
    assert "ignored" in r.stdout, r.stdout
    for rel in DOCKET_FILES:  # the genuine entries were still honoured
        assert not (target / rel).exists(), f"{rel} still present"
    assert manifest.is_file(), "manifest deleted with entries unprocessed"
    left = manifest.read_text(encoding="utf-8")
    assert "../outside.txt" in left


@installer_test
def test_a_directory_where_a_file_goes_aborts_before_writing(tmp_path):
    """NEGATIVE CONTROL FOR the preflight (existing but not a regular file).
    DO NOT DELETE AS REDUNDANT.

    Protects: the promise that a refusal leaves the repository exactly as it
    was. Without it, the preflight (which only looked for a differing regular
    file) lets a directory at a Docket file's path through; the copy then lands
    inside that directory, hashing fails, and the repository is left half
    written with no manifest for the uninstaller to use."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "x\n",
                                "checks/_ledger.py/mine.txt": "user file\n"})
    before = _tree(target)
    r = _run_installer(INSTALLER, target)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "nothing was written" in (r.stdout + r.stderr).lower()
    assert _tree(target) == before


@installer_test
def test_a_file_where_a_directory_goes_aborts_before_writing(tmp_path):
    """NEGATIVE CONTROL FOR the preflight (a file where a directory is needed).
    DO NOT DELETE AS REDUNDANT.

    Protects: the same promise for the other direction. Without it, a regular
    file named `tests` makes mkdir fail part-way through the copy, after the
    checks/ files were already written."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "x\n", "tests": "i am a file\n"})
    before = _tree(target)
    r = _run_installer(INSTALLER, target)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "nothing was written" in (r.stdout + r.stderr).lower()
    assert _tree(target) == before


@installer_test
def test_a_comment_mentioning_the_marker_is_not_the_hook_block(tmp_path):
    """The installer decides "already installed" by Docket's exact start-marker
    line, not by the word `docket-checks` appearing anywhere in the hook.

    Protects: the checks actually running. Without it, a user comment such as
    `# TODO: evaluate docket-checks someday` makes the installer report the
    hook as installed, write no block, and end with OK while nothing runs."""
    target = _adopter_with_user_files(tmp_path)
    hook = _hook_path(target)
    hook.parent.mkdir(parents=True, exist_ok=True)
    mine = "#!/bin/sh\n# TODO: evaluate docket-checks someday\n"
    with hook.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(mine)
    r = _run_installer(INSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "already installed" not in r.stdout, r.stdout
    assert "\n# --- docket-checks (installed by" in hook.read_text(encoding="utf-8")
    assert _run_installer(UNINSTALLER, target).returncode == 0
    assert hook.read_text(encoding="utf-8") == mine


@installer_test
def test_the_hook_leaves_no_bytecode_in_the_working_tree(tmp_path):
    """Running the hook on a commit must not create checks/__pycache__.

    Protects: the adopter's `git add -A`. Without it, the first commit after
    install leaves untracked bytecode that a later `git add -A` commits, and
    no .gitignore is shipped to hide it."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    _commit(target, "after install", {"notes.txt": "n\n"})
    assert not (target / "checks/__pycache__").exists()


# ----------------------- moved repository, one-block cut, mid-install failure

def _files_outside_git(repo: Path):
    return sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(repo).parts)


@installer_test
def test_uninstall_finds_the_hook_after_the_repository_was_moved(tmp_path):
    """The hook is found by asking Git where it is NOW and recognised by Docket's
    exact marker lines -- not by the absolute path recorded at install time.

    Protects: commits after a project folder is renamed or moved. Without it, a
    recorded path that no longer matches makes the uninstaller refuse to touch
    the live hook, tell the user to clean a path that no longer exists, keep the
    hook entry forever, and leave a hook that calls deleted checks, so that
    every commit fails once the ledger (kept because it has rows) is present."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    with (target / "DOCKET.md").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("| UB-104 | OPEN | my row | symptom | - | - | filed |\n")
    moved = tmp_path / "moved-adopter"
    target.rename(moved)
    r = _run_installer(UNINSTALLER, moved)
    assert r.returncode == 0, r.stdout + r.stderr
    hook = _hook_path(moved)
    assert not hook.exists() or "docket-checks" not in hook.read_text(encoding="utf-8")
    assert "by hand" not in r.stdout, r.stdout  # no instruction naming a dead path
    manifest = _manifest_path(moved).read_text(encoding="utf-8") \
        if _manifest_path(moved).exists() else ""
    assert "hook\t" not in manifest, manifest  # the entry is clearable
    _commit(moved, "after move and uninstall", {"notes.txt": "n\n"})


@installer_test
def test_gitattributes_cut_stops_after_the_one_block_it_verified(tmp_path):
    """Exactly the hashed block is removed; a later line that merely looks like
    Docket's opening line starts nothing.

    Protects: the user's own rules written under a comment that copies Docket's
    opening prefix. Without it, the cutter re-arms on that line and deletes the
    user's rules up to the next dashed line, while saying they were kept."""
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "x\n", ".gitattributes": "*.png binary\n"})
    assert _run_installer(INSTALLER, target).returncode == 0
    with (target / ".gitattributes").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("# --- Docket ledger: my own note about the ledger\n"
                 "*.jpg binary\n# -----\n*.pdf binary\n")
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    attrs = (target / ".gitattributes").read_text(encoding="utf-8")
    assert attrs.splitlines() == [
        "*.png binary", "# --- Docket ledger: my own note about the ledger",
        "*.jpg binary", "# -----", "*.pdf binary"], attrs


@installer_test
def test_a_failure_part_way_leaves_a_manifest_that_undoes_it(tmp_path):
    """A failure after some files were written still leaves a manifest naming
    exactly those files, and the uninstaller restores the tree.

    Protects: the "a failure part-way still leaves a manifest" promise. Without
    it, the flush from the EXIT trap could be removed (the manifest then being
    written only at the end of a successful run) and every other test would
    stay green; a half-written install would be unrecoverable by the script.
    The failure is injected into a copy of the installer, after the fifth copy."""
    src = _source_copy(tmp_path)
    script = src / "templates" / "install.sh"
    text = script.read_text(encoding="utf-8")
    anchor = '  note_file "$rel"\ndone < "$LIST"'
    assert text.count(anchor) == 1, "copy loop not found; update this injection"
    script.write_text(text.replace(
        anchor,
        '  note_file "$rel"\n  COUNT=$((${COUNT:-0} + 1))\n'
        '  if [ "$COUNT" -ge 5 ]; then exit 7; fi\ndone < "$LIST"'),
        encoding="utf-8", newline="\n")
    target = _adopter_with_user_files(tmp_path)
    before = _files_outside_git(target)
    r = _run_installer(script, target)
    assert r.returncode == 7, r.stdout + r.stderr
    written = sorted(set(_files_outside_git(target)) - set(before))
    assert len(written) == 5, written
    manifest = _manifest_path(target)
    assert manifest.is_file(), "no manifest after a failure part-way"
    listed = sorted(ln.split("\t")[2] for ln in
                    manifest.read_text(encoding="utf-8").splitlines()
                    if ln.startswith("file\t"))
    assert listed == written, (listed, written)
    u = _run_installer(UNINSTALLER, target)
    assert u.returncode == 0, u.stdout + u.stderr
    assert _files_outside_git(target) == before
    assert not manifest.exists()


# ------------------------------------------- shared hooks: refuse, don't guess

START_MARK = "# --- docket-checks (installed by"
END_MARK = "# --- end docket-checks"


def _shared_hook_repos(tmp_path: Path, names=("alpha", "beta")):
    """Repositories that all use ONE core.hooksPath directory."""
    shared = tmp_path / "shared-hooks"
    shared.mkdir()
    repos = []
    for name in names:
        repo = _init_repo(tmp_path / name)
        _commit(repo, "initial", {"README.md": f"{name}\n"})
        _g(repo, "config", "core.hooksPath", shared.as_posix())
        repos.append(repo)
    return shared / "pre-commit", repos


def _snapshot(*paths: Path):
    return {p.as_posix(): (p.read_bytes() if p.is_file() else None) for p in paths}


def _strip_block(path: Path):
    """What a user does by hand: delete Docket's lines from a hook file."""
    keep, skip = [], False
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        if line.startswith(START_MARK):
            skip = True
        if not skip:
            keep.append(line)
        if line.startswith(END_MARK):
            skip = False
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(keep))


def _add_row(repo: Path):
    with (repo / "DOCKET.md").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("| UB-104 | OPEN | my row | symptom | - | - | filed |\n")


@installer_test
def test_shared_hooks_path_alpha_uninstalls_first_and_is_refused(tmp_path):
    """Two repositories share one hooks directory; the one that wrote the block
    cannot pull it out from under the other.

    Protects: the second repository's commits and its pre-commit check. Without
    it, the first uninstall deletes the shared hook, and the other repository,
    still fully installed, silently loses its check (the old behaviour), or the
    reverse order leaves a hook calling scripts that are gone. Each repository
    ends with a successful commit and no hook pointing at missing scripts."""
    hook, (alpha, beta) = _shared_hook_repos(tmp_path)
    assert _run_installer(INSTALLER, alpha, "--shared-hook").returncode == 0
    assert _run_installer(INSTALLER, beta).returncode == 0
    assert START_MARK in hook.read_text(encoding="utf-8")
    before_tree, before_hook = _tree(alpha), _snapshot(hook)
    r = _run_installer(UNINSTALLER, alpha)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "nothing was changed" in r.stdout.lower() and "--skip-hook" in r.stdout, r.stdout
    assert str(hook.as_posix()).split("/")[-1] in r.stdout
    assert _tree(alpha) == before_tree and _snapshot(hook) == before_hook
    blocked = _run_installer(UNINSTALLER, alpha, "--skip-hook")
    assert blocked.returncode == 2, blocked.stdout + blocked.stderr  # block still there
    assert _snapshot(hook) == before_hook
    _commit(alpha, "alpha commit", {"a.txt": "a\n"})
    _commit(beta, "beta commit", {"b.txt": "b\n"})
    _strip_block(hook)                      # the user's deliberate, manual step
    done = _run_installer(UNINSTALLER, alpha, "--skip-hook")
    assert done.returncode == 0, done.stdout + done.stderr
    assert not (alpha / "checks/check_duplicate_ids.py").exists()
    _commit(alpha, "alpha after uninstall", {"a2.txt": "a\n"})
    _commit(beta, "beta after", {"b2.txt": "b\n"})   # hook has no Docket block now


@installer_test
def test_shared_hooks_path_non_writer_uninstall_is_refused(tmp_path):
    """The repository that did NOT write the shared block is refused too.

    Its uninstall used to remove checks/ and say nothing about the hook, after
    which every commit there failed with a missing script.

    Protects: that repository's ability to commit. Without it, the shared hook
    keeps calling checks/check_duplicate_ids.py in a repository that no longer
    has it, and `git commit` fails (this test ends in a commit that must pass)."""
    hook, (alpha, beta) = _shared_hook_repos(tmp_path)
    assert _run_installer(INSTALLER, alpha, "--shared-hook").returncode == 0
    r = _run_installer(INSTALLER, beta)
    assert r.returncode == 0 and "already installed" in r.stdout, r.stdout
    _add_row(beta)
    before = (_tree(beta), _snapshot(hook))
    u = _run_installer(UNINSTALLER, beta)
    assert u.returncode == 2, u.stdout + u.stderr
    assert (_tree(beta), _snapshot(hook)) == before
    _commit(beta, "beta after refusal", {"b.txt": "b\n"})
    _commit(alpha, "alpha after", {"a.txt": "a\n"})


@installer_test
def test_changing_hooks_path_after_install_does_not_delete_a_shared_hook(tmp_path):
    """A repository that installed with default hooks and later pointed
    core.hooksPath at a directory another repository uses must not have that
    other repository's hook cut or deleted.

    Protects: the other repository's hook file (byte-for-byte) and this one's
    own block. Without it, the uninstaller acts on whatever hook Git resolves
    now, deletes the shared hook, and leaves its own block behind."""
    hook, (alpha, _beta) = _shared_hook_repos(tmp_path, names=("alpha", "beta"))
    gamma = _init_repo(tmp_path / "gamma")
    _commit(gamma, "initial", {"README.md": "gamma\n"})
    assert _run_installer(INSTALLER, alpha, "--shared-hook").returncode == 0
    assert _run_installer(INSTALLER, gamma).returncode == 0   # default hooks
    own = _hook_path(gamma)
    assert START_MARK in own.read_text(encoding="utf-8")
    _g(gamma, "config", "core.hooksPath", hook.parent.as_posix())
    before = (_snapshot(hook, own), _tree(gamma))
    r = _run_installer(UNINSTALLER, gamma)
    assert r.returncode == 2, r.stdout + r.stderr
    assert (_snapshot(hook, own), _tree(gamma)) == before
    _commit(gamma, "gamma after refusal", {"g.txt": "g\n"})
    _commit(alpha, "alpha after", {"a.txt": "a\n"})


@installer_test
def test_linked_worktree_uninstall_is_refused_then_allowed_when_alone(tmp_path):
    """Linked worktrees share one hooks directory, so a worktree's uninstall is
    refused; once the worktree is gone the main checkout can uninstall.

    Protects: commits in every worktree. Without it, uninstalling in the
    worktree leaves a shared hook that calls scripts that are gone (the commit
    in it fails), or removes the hook the main checkout still relies on."""
    main = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, main).returncode == 0
    wt = tmp_path / "wt"
    _g(main, "worktree", "add", "-q", "-b", "feature", str(wt))
    i = _run_installer(INSTALLER, wt)
    assert i.returncode == 0 and "already installed" in i.stdout, i.stdout
    _add_row(wt)
    hook = _hook_path(main)
    before = (_tree(wt), _snapshot(hook))
    r = _run_installer(UNINSTALLER, wt)
    assert r.returncode == 2, r.stdout + r.stderr
    assert (_tree(wt), _snapshot(hook)) == before
    _commit(wt, "worktree commit", {"w.txt": "w\n"})
    _commit(main, "main commit", {"m.txt": "m\n"})
    _g(main, "worktree", "remove", "--force", str(wt))
    done = _run_installer(UNINSTALLER, main)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not hook.exists()
    _commit(main, "main after uninstall", {"m2.txt": "m\n"})


@installer_test
def test_installer_does_not_write_a_shared_hook_unless_asked(tmp_path):
    """With core.hooksPath set, or linked worktrees present, the files are
    installed but the hook is not written without --shared-hook.

    Protects: hooks that other repositories rely on. Without it, the installer
    appends Docket's block to a hook shared with repositories that have no
    checks/, and every commit there fails."""
    hook, (alpha, _beta) = _shared_hook_repos(tmp_path)
    r = _run_installer(INSTALLER, alpha)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NOT written" in r.stdout and "--shared-hook" in r.stdout, r.stdout
    assert not hook.exists()
    assert (alpha / "checks/check_duplicate_ids.py").is_file()
    assert "hook\t" not in _manifest_path(alpha).read_text(encoding="utf-8")
    main = _adopter_with_user_files(tmp_path)
    wt = tmp_path / "wt"
    _g(main, "worktree", "add", "-q", "-b", "feature", str(wt))
    w = _run_installer(INSTALLER, main)
    assert w.returncode == 0 and "NOT written" in w.stdout, w.stdout
    assert not _hook_path(main).exists()
    again = _run_installer(INSTALLER, main, "--shared-hook")
    assert again.returncode == 0, again.stdout + again.stderr
    assert START_MARK in _hook_path(main).read_text(encoding="utf-8")


@installer_test
def test_uninstall_refuses_a_hook_entry_that_is_not_the_resolved_hook(tmp_path):
    """A manifest hook entry that does not resolve to the hook Git resolves now
    makes the whole uninstall refuse and change nothing.

    Protects: files outside this repository's own hook. Without it, a tampered
    or stale entry is acted on or silently dropped, and a hook is cut or left
    calling checks that were removed."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    fake = tmp_path / "other-hook"
    block = (f"#!/bin/sh\necho mine\n{START_MARK} Docket templates/install.sh) ---\n"
             f"echo hi\n{END_MARK} ---\n")
    with fake.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(block)
    with _manifest_path(target).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"hook\t{fake.as_posix()}\n")
    before = (_tree(target), _snapshot(fake))
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 2, r.stdout + r.stderr
    assert (_tree(target), _snapshot(fake)) == before


@installer_test
def test_hook_cut_keeps_crlf_user_lines_byte_for_byte(tmp_path):
    """CRLF lines in the user's hook survive install and uninstall unchanged.

    Protects: the user's bytes. Without BINMODE on the awk that rewrites the
    file, Git for Windows' awk strips every CR, so a hook kept in CRLF is
    silently converted (compare with cmp, not by reading lines)."""
    target = _adopter_with_user_files(tmp_path)
    hook = _hook_path(target)
    hook.parent.mkdir(parents=True, exist_ok=True)
    mine = b"#!/bin/sh\r\necho before\r\n# tail\r\n"
    hook.write_bytes(mine)
    assert _run_installer(INSTALLER, target).returncode == 0
    assert START_MARK in hook.read_text(encoding="utf-8")
    assert _run_installer(UNINSTALLER, target).returncode == 0
    assert hook.read_bytes() == mine


@installer_test
def test_gitattributes_cut_keeps_crlf_user_lines_byte_for_byte(tmp_path):
    """CRLF lines in the user's .gitattributes survive install and uninstall.

    Protects: a .gitattributes stored with CRLF in the repository, whose
    removal commit would otherwise show every line modified."""
    target = _init_repo(tmp_path / "adopter")
    mine = b"*.png binary\r\n*.gif binary\r\n"
    _commit(target, "initial", {"README.md": "x\n"})
    (target / ".gitattributes").write_bytes(mine)
    assert _run_installer(INSTALLER, target).returncode == 0
    assert _run_installer(UNINSTALLER, target).returncode == 0
    assert (target / ".gitattributes").read_bytes() == mine


@installer_test
def test_hook_cut_stops_after_the_one_block_it_wrote(tmp_path):
    """Exactly Docket's block is cut; a later pair of look-alike marker lines
    and the user's lines between them stay.

    Protects: user hook lines written between copies of Docket's marker prefix.
    Without it, the hook cutter re-arms on every later start marker and deletes
    them while saying the other hook lines were kept."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    hook = _hook_path(target)
    user = (f"{START_MARK} me, a line that copies the marker) -------\n"
            'echo "my own precious hook line"\n'
            f"{END_MARK} (mine) -----\necho \"after my block\"\n")
    with hook.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(user)
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 0, r.stdout + r.stderr
    assert hook.read_text(encoding="utf-8") == "#!/bin/sh\n" + user


# ----------------------- a Docket block this checkout did not record writing

@installer_test
def test_block_written_from_a_removed_worktree_is_not_left_behind(tmp_path):
    """The hook was written from a linked worktree (--shared-hook), whose
    per-worktree manifest disappeared with the worktree. The main checkout's
    uninstall must refuse, not remove checks/ and leave a hook that calls them.

    Protects: the main checkout's next commit. Without it, the block has no
    entry in the main manifest and no sharing reason is left once the worktree
    is gone, so the uninstaller removes checks/, keeps the block, says nothing,
    and every later commit fails with a missing script (this test ends in a
    commit that must pass after the printed steps are followed)."""
    main = _adopter_with_user_files(tmp_path)
    wt = tmp_path / "wt"
    _g(main, "worktree", "add", "-q", "-b", "feature", str(wt))
    assert _run_installer(INSTALLER, main).returncode == 0       # hook NOT written
    assert _run_installer(INSTALLER, wt, "--shared-hook").returncode == 0
    hook = _hook_path(main)
    assert START_MARK in hook.read_text(encoding="utf-8")
    assert "hook\t" not in _manifest_path(main).read_text(encoding="utf-8")
    _add_row(main)
    _g(main, "worktree", "remove", "--force", str(wt))
    before = (_tree(main), _snapshot(hook))
    r = _run_installer(UNINSTALLER, main)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "nothing was changed" in r.stdout.lower() and "--skip-hook" in r.stdout, r.stdout
    assert (_tree(main), _snapshot(hook)) == before
    _strip_block(hook)                                  # the printed manual step
    done = _run_installer(UNINSTALLER, main, "--skip-hook")
    assert done.returncode == 0, done.stdout + done.stderr
    _commit(main, "main after uninstall", {"m.txt": "m\n"})


@installer_test
def test_a_block_copied_in_by_hand_is_not_left_behind(tmp_path):
    """A hook that already held Docket's block before the install (copied from
    another repository) leaves this manifest with no hook entry; the uninstall
    must refuse rather than delete checks/ under it.

    Protects: the same consequence as above on a second shape. Without it the
    installer says "already installed", writes no entry, and the uninstaller
    removes checks/ without a word about the block; the next commit fails."""
    donor = _adopter_with_user_files(tmp_path / "donor-root")
    assert _run_installer(INSTALLER, donor).returncode == 0
    block = _hook_path(donor).read_text(encoding="utf-8")
    target = _init_repo(tmp_path / "adopter")
    _commit(target, "initial", {"README.md": "x\n"})
    hook = _hook_path(target)
    hook.parent.mkdir(parents=True, exist_ok=True)
    with hook.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(block)
    i = _run_installer(INSTALLER, target)
    assert i.returncode == 0 and "already installed" in i.stdout, i.stdout
    assert "hook\t" not in _manifest_path(target).read_text(encoding="utf-8")
    before = (_tree(target), _snapshot(hook))
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 2, r.stdout + r.stderr
    assert (_tree(target), _snapshot(hook)) == before
    _strip_block(hook)
    done = _run_installer(UNINSTALLER, target, "--skip-hook")
    assert done.returncode == 0, done.stdout + done.stderr
    _commit(target, "after uninstall", {"n.txt": "n\n"})


@installer_test
def test_refusal_prints_a_backslash_hooks_path_verbatim_under_dash(tmp_path):
    """The refusal text is what the user acts on, so a backslash in
    core.hooksPath must reach them unchanged even where `echo` interprets
    escapes (dash).

    Protects: the manual steps. Without printf in shared_hook_reason, dash turns
    the `\\t` of `C:\\temp\\hooks` into a tab and the user is told to open a
    path that does not exist."""
    dash = _shutil.which("dash")
    if dash is None:
        pytest.skip("dash is not installed here; the escape-sequence case needs it")
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    _g(target, "config", "core.hooksPath", "C:\\temp\\hooks9")
    r = subprocess.run(
        [dash, UNINSTALLER.as_posix(), target.as_posix()],
        capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "core.hooksPath is set (C:\\temp\\hooks9)" in r.stdout, r.stdout


# ------------------- hook the uninstaller cannot cut: detect it before removing

def _edit_hook(path: Path, edit):
    text = path.read_text(encoding="utf-8")
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(edit(text))


@installer_test
def test_installer_notice_prints_a_backslash_hooks_path_verbatim_under_dash(tmp_path):
    """The installer's NOTICE names the hook file the user would write into, so
    a backslash in core.hooksPath must reach them unchanged where `echo`
    interprets escapes (dash).

    Protects: the NOTICE, an action surface. Without printf on those lines,
    dash turns the `\\t` of `C:\\temp\\hooks9` into a tab and the user is told
    to write into a path that does not exist."""
    dash = _shutil.which("dash")
    if dash is None:
        pytest.skip("dash is not installed here; the escape-sequence case needs it")
    target = _adopter_with_user_files(tmp_path)
    _g(target, "config", "core.hooksPath", "C:\\temp\\hooks9")
    r = subprocess.run([dash, INSTALLER.as_posix(), target.as_posix()],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "core.hooksPath is set (C:\\temp\\hooks9)" in r.stdout, r.stdout
    assert "C:\\temp\\hooks9/pre-commit anyway" in r.stdout, r.stdout


@installer_test
def test_a_half_block_is_refused_before_any_file_is_removed(tmp_path):
    """One of Docket's two marker lines was deleted by the user. The uninstaller
    cannot cut the block, so it must say so BEFORE removing checks/.

    Protects: the next commit. Without it, checks/ is removed first and the
    block is found uncuttable afterwards, leaving a hook that calls scripts that
    are gone (this test ends in a commit that must pass after the printed step)."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    hook = _hook_path(target)
    _edit_hook(hook, lambda t: "".join(
        ln for ln in t.splitlines(keepends=True) if not ln.startswith(END_MARK)))
    _add_row(target)
    before = (_tree(target), _snapshot(hook))
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "nothing was changed" in r.stdout.lower() and "marker" in r.stdout, r.stdout
    assert (_tree(target), _snapshot(hook)) == before
    _edit_hook(hook, lambda t: "#!/bin/sh\n")            # the printed manual step
    done = _run_installer(UNINSTALLER, target)
    assert done.returncode == 0, done.stdout + done.stderr
    _commit(target, "after uninstall", {"n.txt": "n\n"})


@installer_test
def test_edited_marker_lines_that_still_run_the_checks_are_refused(tmp_path):
    """Both marker lines were edited, so no block is recognised, but the hook
    still runs Docket's check scripts. The uninstaller must refuse before
    removing them, not report "nothing to remove".

    Protects: the next commit. Without it, the uninstaller finds no block,
    removes checks/ and clears the hook entry, and the hook keeps calling the
    removed scripts with nothing pointing at the hook (this test ends in a
    commit that must pass after the printed step)."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    hook = _hook_path(target)
    _edit_hook(hook, lambda t: t.replace(START_MARK, "# docket checks (installed by")
               .replace(END_MARK, "# end of docket checks"))
    _add_row(target)
    before = (_tree(target), _snapshot(hook))
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "nothing was changed" in r.stdout.lower() and "checks/" in r.stdout, r.stdout
    assert (_tree(target), _snapshot(hook)) == before
    blocked = _run_installer(UNINSTALLER, target, "--skip-hook")
    assert blocked.returncode == 2, blocked.stdout + blocked.stderr  # still runs them
    _edit_hook(hook, lambda t: "#!/bin/sh\n")
    done = _run_installer(UNINSTALLER, target)
    assert done.returncode == 0, done.stdout + done.stderr
    _commit(target, "after uninstall", {"n.txt": "n\n"})


def _printed_text(stdout: str) -> str:
    """The script's lines joined into running text (prefixes dropped), so a
    phrase that wraps across two printed lines can still be asserted."""
    return " ".join(_re.sub(r"^docket:\s*", "", ln).strip() for ln in stdout.splitlines())


def _delete_lines_between(path: Path, first, last):
    """What the printed instruction asks, taken literally: delete everything
    from the line where Docket's block started through the line where it ended."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(i for i, ln in enumerate(lines) if first(ln))
    end = next(i for i in range(start, len(lines)) if last(lines[i]))
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(lines[:start] + lines[end + 1:]))


@installer_test
def test_printed_instruction_followed_literally_leaves_a_working_hook_half_block(tmp_path):
    """The refusal's manual step, followed to the letter for a hook with one
    marker line deleted, leaves a hook that is valid shell and a repo that
    commits.

    Protects: the text users act on. A step that says only "delete the lines
    that run checks/ scripts" leaves the `if ...; then` / `fi` behind, which
    is a shell syntax error on every later commit. Here the user deletes
    everything from where the block started to where it ended (through its
    `fi`), and the text must say to."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    hook = _hook_path(target)
    _edit_hook(hook, lambda t: "".join(
        ln for ln in t.splitlines(keepends=True) if not ln.startswith(END_MARK)))
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 2, r.stdout + r.stderr
    printed = _printed_text(r.stdout)
    for phrase in ("everything from where Docket's block started to where it ended",
                   "if/fi", "before the install"):
        assert phrase in printed, (phrase, r.stdout)
    _delete_lines_between(hook, lambda ln: ln.startswith(START_MARK),
                          lambda ln: ln.strip() == "fi")
    done = _run_installer(UNINSTALLER, target)
    assert done.returncode == 0, done.stdout + done.stderr
    _commit(target, "after the printed step", {"n.txt": "n\n"})


@installer_test
def test_printed_instruction_followed_literally_leaves_a_working_hook_both_edited(tmp_path):
    """The same, for both marker lines edited: the user deletes from the edited
    opening comment through the edited closing comment, `if ... fi` included.

    Protects: the same text and the same commit, on the second shape. Without
    it only the half-block wording is exercised."""
    target = _adopter_with_user_files(tmp_path)
    assert _run_installer(INSTALLER, target).returncode == 0
    hook = _hook_path(target)
    _edit_hook(hook, lambda t: t.replace(START_MARK, "# docket checks (installed by")
               .replace(END_MARK, "# end of docket checks"))
    r = _run_installer(UNINSTALLER, target)
    assert r.returncode == 2, r.stdout + r.stderr
    printed = _printed_text(r.stdout)
    for phrase in ("everything from where Docket's block started to where it ended",
                   "if/fi", "before the install"):
        assert phrase in printed, (phrase, r.stdout)
    _delete_lines_between(hook, lambda ln: ln.startswith("# docket checks (installed by"),
                          lambda ln: ln.startswith("# end of docket checks"))
    done = _run_installer(UNINSTALLER, target)
    assert done.returncode == 0, done.stdout + done.stderr
    _commit(target, "after the printed step", {"n.txt": "n\n"})


# ------------------------------------------- state transitions over a range

def _repo_with_midrange_reopen(tmp_path: Path, reopen_note: str):
    """c1 files a DONE row; c2 flips it to OPEN; c3 flips it back to DONE.
    The ENDPOINTS agree (DONE at c1, DONE at c3) -- only the middle edge
    carries the transition."""
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "seed", {"README.md": "x\n"})
    c1 = _commit(repo, "file and close UB-101", {"DOCKET.md": _ledger(
        "| UB-101 | DONE | a matter | symptom | - | - | closed by commit abc1234 |")})
    _commit(repo, "work on UB-101 again", {"DOCKET.md": _ledger(
        f"| UB-101 | OPEN | a matter | symptom | - | - | closed by commit abc1234{reopen_note} |")})
    c3 = _commit(repo, "close UB-101 again", {"DOCKET.md": _ledger(
        f"| UB-101 | DONE | a matter | symptom | - | - | closed by commit abc1234{reopen_note} |")})
    return repo, c1, c3


def test_state_range_catches_a_silent_reopen_mid_push(tmp_path):
    """RED arm: a DONE->OPEN inside a multi-commit push, with both endpoints
    DONE."""
    repo, c1, c3 = _repo_with_midrange_reopen(tmp_path, reopen_note="")
    r = run_check("check_state_transitions_range.py", "--base", c1,
                  "--head", c3, cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "UB-101: DONE -> OPEN" in r.stdout, r.stdout


def test_endpoint_only_comparison_misses_what_the_range_catches(tmp_path):
    """NEGATIVE CONTROL FOR the range driver. DO NOT DELETE AS REDUNDANT.

    Protects: the claim that RANGE-awareness is what fixes the defect.
    Without it, the RED arm above could be passing for some unrelated reason
    and the driver could be reverted to an endpoint comparison with the suite
    still green. This runs the OLD method -- the two endpoint ledgers
    compared directly, exactly what fetch-depth 2 + HEAD~1 did -- over the
    very same history, and requires it to report CLEAN. The defect is real
    and the old instrument cannot see it."""
    repo, c1, c3 = _repo_with_midrange_reopen(tmp_path, reopen_note="")
    old = tmp_path / "old.md"
    new = tmp_path / "new.md"
    old.write_text(_g(repo, "show", f"{c1}:DOCKET.md").stdout, encoding="utf-8")
    new.write_text(_g(repo, "show", f"{c3}:DOCKET.md").stdout, encoding="utf-8")
    r = run_check("check_state_transitions.py", "--old", str(old), "--new", str(new))
    assert r.returncode == 0, (
        "the endpoint comparison was expected to MISS this; if it now catches "
        "it, the fixture no longer reproduces the defect")
    assert "PASS" in r.stdout


def test_state_range_green_when_the_reopen_is_annotated(tmp_path):
    """GREEN twin. Same history, same middle edge, one dated note added."""
    repo, c1, c3 = _repo_with_midrange_reopen(
        tmp_path, reopen_note="; 2026-08-04 reopened: regression found in prod")
    r = run_check("check_state_transitions_range.py", "--base", c1,
                  "--head", c3, cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    # Non-vacuity: a driver that walked ZERO edges would also exit 0. Both
    # ledger-changing edges in this range must actually have been compared.
    assert "2 ledger-changing edge(s) examined" in r.stdout, r.stdout


def test_state_range_says_not_run_rather_than_pass_on_an_unusable_base(tmp_path):
    """A new branch or force push gives an all-zero base. The driver must say
    it read nothing, never print a PASS over a range it never walked."""
    repo, _c1, c3 = _repo_with_midrange_reopen(tmp_path, reopen_note="")
    r = run_check("check_state_transitions_range.py", "--base", "0" * 40,
                  "--head", c3, cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NOT RUN" in r.stdout and "PASS" not in r.stdout, r.stdout


# ------------------------------------------------------------- commit ids

def test_commit_ids_red_advance_without_citation(tmp_path):
    """PROTOCOL 3.1: a commit that advances a row names it."""
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "seed", {"README.md": "x\n"})
    base = _commit(repo, "file the first matter", {"DOCKET.md": _ledger(
        "| UB-101 | OPEN | a matter | symptom | - | - | filed |")})
    head = _commit(repo, "start working on it", {"DOCKET.md": _ledger(
        "| UB-101 | OPEN | a matter | symptom | session-A | - | filed; claimed |")})
    r = run_check("check_commit_ids.py", "--base", base, "--head", head, cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "advances UB-101" in r.stdout and "no id" in r.stdout, r.stdout


def test_commit_ids_green_advance_with_citation(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "seed", {"README.md": "x\n"})
    base = _commit(repo, "file the first matter", {"DOCKET.md": _ledger(
        "| UB-101 | OPEN | a matter | symptom | - | - | filed |")})
    head = _commit(repo, "UB-101: claim it for session-A", {"DOCKET.md": _ledger(
        "| UB-101 | OPEN | a matter | symptom | session-A | - | filed; claimed |")})
    r = run_check("check_commit_ids.py", "--base", base, "--head", head, cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    # Non-vacuity: a run that examined no ledger-touching commit would also
    # exit 0. Exactly one commit in this range touches the ledger.
    assert "1 ledger-touching commit(s)" in r.stdout, r.stdout


def test_commit_ids_red_message_cites_a_phantom_id(tmp_path):
    """The citation surface check_phantom_ids.py cannot reach: a commit
    MESSAGE is not a tracked file, so a fabricated number in one was the last
    place a phantom could hide."""
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "seed", {"README.md": "x\n"})
    base = _commit(repo, "file the first matter", {"DOCKET.md": _ledger(
        "| UB-101 | OPEN | a matter | symptom | - | - | filed |")})
    head = _commit(repo, "UB-101: claim it, per the decision in UB-999",
                   {"DOCKET.md": _ledger(
                       "| UB-101 | OPEN | a matter | symptom | session-A | - | filed; claimed |")})
    r = run_check("check_commit_ids.py", "--base", base, "--head", head, cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "cites UB-999" in r.stdout and "no such row" in r.stdout, r.stdout


def test_commit_ids_green_filing_a_row_needs_no_citation(tmp_path):
    """GREEN twin, and a rule rather than a convenience: under Mode B a
    session files with UB-ID-PENDING, which has no number to cite. Adding a
    row is not advancing one (PROTOCOL 3.1). Without this carve-out the
    commit that installs the starter ledger would fail every adopter's first
    build -- the very defect class v0.2 exists to close."""
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "seed", {"README.md": "x\n"})
    base = _commit(repo, "add the ledger", {"DOCKET.md": _ledger(
        "| UB-101 | OPEN | a matter | symptom | - | - | filed |")})
    head = _commit(repo, "file two more matters, no numbers yet",
                   {"DOCKET.md": _ledger(
                       "| UB-101 | OPEN | a matter | symptom | - | - | filed |",
                       "| UB-ID-PENDING | OPEN | second | symptom | - | - | filed |",
                       "| UB-ID-PENDING | OPEN | third | symptom | - | - | filed |")})
    r = run_check("check_commit_ids.py", "--base", base, "--head", head, cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 ledger-touching commit(s)" in r.stdout, r.stdout


def test_commit_ids_says_not_run_rather_than_pass_on_an_unusable_base(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "seed", {"README.md": "x\n"})
    head = _commit(repo, "add the ledger", {"DOCKET.md": _ledger(
        "| UB-101 | OPEN | a matter | symptom | - | - | filed |")})
    r = run_check("check_commit_ids.py", "--base", "0" * 40, "--head", head, cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NOT RUN" in r.stdout and "PASS" not in r.stdout, r.stdout


def test_commit_ids_unreadable_head_ledger_is_loud(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "seed", {"README.md": "x\n"})
    base = _commit(repo, "add the ledger", {"DOCKET.md": _ledger(
        "| UB-101 | OPEN | a matter | symptom | - | - | filed |")})
    head = _commit(repo, "UB-101: a hand edit lost a leading pipe",
                   {"DOCKET.md": _ledger(
                       "| UB-101 | OPEN | a matter | symptom | S | - | filed |",
                       "UB-102 | OPEN | mangled | symptom | - | - | filed |")})
    r = run_check("check_commit_ids.py", "--base", base, "--head", head, cwd=repo)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unreadable" in (r.stdout + r.stderr).lower()


# ----------------------------------------------------- closure references

def test_closure_refs_green_real_reachable_commit(tmp_path):
    repo = _init_repo(tmp_path / "r")
    sha = _commit(repo, "do the work", {"work.txt": "done\n"})
    _commit(repo, "close it", {"DOCKET.md": _ledger(
        f"| UB-101 | DONE | a matter | symptom | - | - | closed by commit {sha[:7]} |")})
    r = run_check("check_closure_references.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    # Non-vacuity: a ledger with no DONE rows would also exit 0.
    assert "1 DONE row(s)" in r.stdout, r.stdout


def test_closure_refs_red_no_hash_at_all(tmp_path):
    """PROTOCOL 6.2: "done" is not a closure."""
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "close it", {"DOCKET.md": _ledger(
        "| UB-101 | DONE | a matter | symptom | - | - | done, handled, fixed |")})
    r = run_check("check_closure_references.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "no commit hash" in r.stdout, r.stdout


def test_closure_refs_red_hash_that_does_not_resolve(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "close it", {"DOCKET.md": _ledger(
        "| UB-101 | DONE | a matter | symptom | - | - | closed by commit deadbee |")})
    r = run_check("check_closure_references.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "none resolves" in r.stdout, r.stdout


def test_closure_refs_red_commit_exists_but_is_unreachable(tmp_path):
    """THE reachability arm, and the reason this check does more than
    `cat-file -e`. DO NOT COLLAPSE INTO the not-resolving test above.

    Protects: the half that catches a dangled citation after a history
    rewrite -- this repository's own experience, where closure notes pointed
    at commits that still EXISTED in the object database but had left the
    project's history. Existence alone would have reported every one of them
    fine. The assertions below prove the distinction is real by showing
    `cat-file -e` SUCCEEDING on the very hash the check rejects."""
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "seed", {"README.md": "x\n"})
    _g(repo, "checkout", "-q", "-b", "side")
    orphan = _commit(repo, "work that later left history", {"side.txt": "x\n"})
    _g(repo, "checkout", "-q", "main")
    _g(repo, "branch", "-qD", "side")

    # The object is still there -- existence alone would bless this citation.
    assert _g(repo, "cat-file", "-e", f"{orphan}^{{commit}}",
              check=False).returncode == 0, "fixture no longer reproduces the class"
    assert _g(repo, "merge-base", "--is-ancestor", orphan, "HEAD",
              check=False).returncode != 0, "the orphan is still reachable"

    _commit(repo, "close it", {"DOCKET.md": _ledger(
        f"| UB-101 | DONE | a matter | symptom | - | - | closed by commit {orphan[:7]} |")})
    r = run_check("check_closure_references.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "none resolves to a commit reachable" in r.stdout, r.stdout


def test_closure_refs_wontfix_is_exempt_while_done_is_not(tmp_path):
    """GREEN twin for the WONTFIX exemption, carried in a ledger that ALSO
    holds a properly-cited DONE row -- so the pass cannot come from the
    checker examining nothing. If the exemption were widened to cover DONE,
    test_closure_refs_red_no_hash_at_all goes green and catches it."""
    repo = _init_repo(tmp_path / "r")
    sha = _commit(repo, "do the work", {"work.txt": "done\n"})
    _commit(repo, "close one, decline the other", {"DOCKET.md": _ledger(
        "| UB-101 | WONTFIX | not doing this | symptom | - | - | declined 2026-08-04, no commit to cite |",
        f"| UB-102 | DONE | a matter | symptom | - | - | closed by commit {sha[:7]} |")})
    r = run_check("check_closure_references.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 DONE row(s)" in r.stdout, r.stdout


def test_closure_refs_foreign_hash_plus_one_local_passes(tmp_path):
    """Closure notes legitimately cite commits in OTHER repositories. One
    local reachable commit is the requirement; a sibling project's hash
    beside it is context, not a failure."""
    repo = _init_repo(tmp_path / "r")
    sha = _commit(repo, "do the work", {"work.txt": "done\n"})
    _commit(repo, "close it", {"DOCKET.md": _ledger(
        f"| UB-101 | DONE | cross-link the sibling | symptom | - | - | "
        f"sibling side landed as 31349a2 (their repo); closed here by commit {sha[:7]} |")})
    r = run_check("check_closure_references.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr


def test_closure_refs_unreadable_row_is_loud(tmp_path):
    repo = _init_repo(tmp_path / "r")
    _commit(repo, "close it", {"DOCKET.md": _ledger(
        "| UB-101 | DONE | a matter | symptom | - | - | closed by commit abc1234 |",
        "UB-102 | DONE | mangled, uncited | symptom | - | - | done |")})
    r = run_check("check_closure_references.py", "DOCKET.md", cwd=repo)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "unreadable" in (r.stdout + r.stderr).lower()
