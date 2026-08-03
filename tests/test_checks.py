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


def test_claim_collision_green_release(tmp_path):
    _, wt2 = _claimed_repo_with_second_worktree(tmp_path)
    text = (wt2 / "DOCKET.md").read_text(encoding="utf-8")
    (wt2 / "DOCKET.md").write_text(
        text.replace("| session-A |", "| - |"), encoding="utf-8")
    subprocess.run(["git", "add", "DOCKET.md"], cwd=wt2, check=True)
    r = run_check("check_claim_collision.py", "DOCKET.md", cwd=wt2)
    assert r.returncode == 0, r.stdout + r.stderr


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
