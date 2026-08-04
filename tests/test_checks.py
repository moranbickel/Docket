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


def _run_installer(installer: Path, target: Path):
    # `sh`, matching the script's own shebang, and POSIX-style paths.
    # Measured on Windows: the bare bash.EXE shipped with Git resolves a
    # drive-letter path against its own root and reports "No such file or
    # directory" for a script that is plainly there, while sh.EXE beside it
    # reads the same path fine. Both exist on CI, so the shebang decides.
    shell = _shutil.which("sh") or _shutil.which("bash") or "sh"
    return subprocess.run(
        [shell, Path(installer).as_posix(), Path(target).as_posix()],
        capture_output=True, text=True, encoding="utf-8")


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
