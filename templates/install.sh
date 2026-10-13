#!/bin/sh
# Install Docket into a target repository, and prove the install by running it.
#
# Usage: install.sh /path/to/your-repo
#
# Places: checks/ (all six checks) + tests/ (the fixture suite that arms them)
#         + the pre-commit hook + .github/workflows/ledger-ci.yml
#         + a starter DOCKET.md and the .gitattributes stanza, if absent.
# Then runs every check CI runs, against the target, and reports what ran.
#
# It also records exactly what it created, with a content hash per file, in an
# install manifest inside the repository's git directory (not in your working
# tree, so there is nothing to commit or ignore). templates/uninstall.sh reads
# that manifest and removes only those files, only while they are unchanged.
#
# ALL OR NOTHING UP FRONT: every precondition that can be checked before
# writing is checked before writing -- a git worktree, a python, and no
# existing file that differs from the one to be installed. A refusal therefore
# leaves the repository exactly as it was. Once writing starts, the remaining
# steps are verification of the install (the checks run against your ledger);
# a failure there reports on your ledger and does not undo the install.
#
# WHY ONE INSTALLER: the version this replaces copied three files into
# .docket-checks/ while the CI workflow it told you to copy invoked five
# checks under checks/ plus the suite under tests/. An adopter who followed
# the README exactly got a red build on their first push. The installed set
# and the invoked set are now the same set by construction, and
# tests/test_checks.py::test_installed_workflow_paths_all_resolve is the
# control that keeps them the same set -- it reads the INSTALLED workflow,
# extracts every path it invokes, and asserts each one is on disk.
#
# The hook resolves its root from the COMMITTING worktree at commit time --
# no environment variables, no baked-in absolute paths (PROTOCOL.md 4.4: an
# env-var root set by one session silently points another session's hook at
# the wrong ledger).
set -eu

SRC="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:?usage: install.sh /path/to/your-repo}"

if ! git -C "$TARGET" rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "docket: ERROR: $TARGET is not a git worktree" >&2
  exit 2
fi
TARGET="$(cd "$TARGET" && pwd -P)"
# The hook, the manifest and the uninstaller all assume the repository's top
# level, so refuse anything else rather than install into a subdirectory.
TOP="$(cd "$(git -C "$TARGET" rev-parse --show-toplevel)" && pwd -P)"
if [ "$TARGET" != "$TOP" ]; then
  echo "docket: ERROR: $TARGET is not the top level of its repository." >&2
  echo "docket:        Pass the top level instead: $TOP" >&2
  echo "docket:        nothing was written." >&2
  exit 2
fi

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "docket: ERROR: no python3 or python on PATH -- the checks cannot run" >&2
  exit 2
fi

# Files to install: checks/ and tests/ whole, plus the CI workflow.
WORK="$(mktemp -d)"
LIST="$WORK/list"
NEW="$WORK/new-entries"
: > "$NEW"
MANIFEST=""

# Write the manifest from what has been recorded so far, merged with any earlier
# one. Called on the normal path and again from the EXIT trap, so a failure
# half-way through still leaves a manifest the uninstaller can use.
flush_manifest() {
  [ -n "$MANIFEST" ] && [ -s "$NEW" ] || return 0
  mkdir -p "$(dirname "$MANIFEST")"
  {
    printf '# docket install manifest v1\n'
    [ -f "$MANIFEST" ] && cat "$MANIFEST"
    cat "$NEW"
  } | awk '!seen[$0]++' > "$WORK/manifest"
  cat "$WORK/manifest" > "$MANIFEST"
}
trap 'flush_manifest || true; rm -rf "$WORK"' EXIT
( cd "$SRC" && find checks tests -type f ! -path '*__pycache__*' ! -name '*.pyc' ) > "$LIST"
echo ".github/workflows/ledger-ci.yml" >> "$LIST"

# --- paths this install will touch, resolved the way git resolves them -------
abs_git_path() {
  _p="$(git -C "$TARGET" rev-parse --git-path "$1")"
  case "$_p" in
    /*|[A-Za-z]:*) printf '%s\n' "$_p" ;;
    *) printf '%s\n' "$TARGET/$_p" ;;
  esac
}
MANIFEST="$(abs_git_path docket-install.manifest)"
HOOKS_DIR="$(abs_git_path hooks)"
# How Git itself spells the hooks directory ('.git/hooks' or '.githooks' relative
# to the top level, or an absolute path for a linked worktree). The manifest
# records this spelling, so it stays true when the repository directory is
# renamed or moved; the uninstaller re-asks Git and trusts only the markers.
HOOKS_GIT_SPELLING="$(git -C "$TARGET" rev-parse --git-path hooks)"
HOOK="$HOOKS_DIR/pre-commit"
ATTRS="$TARGET/.gitattributes"

# --- preflight: find every conflict BEFORE writing anything -------------------
# Never clobber a file that exists and differs. An identical file is a no-op,
# which also makes the installer idempotent and lets you run it against a
# clone of Docket itself (`install.sh .`) -- there src and dst are literally
# the same path, and cp refuses that. Anything that exists but is not a regular
# file where a file goes, or is not a directory where a directory goes, is a
# conflict too: writing into it would fail part-way.
CONFLICTS=0
conflict() { echo "docket: ERROR: $1" >&2; CONFLICTS=1; }
want_file() {   # a path that must be absent or a regular file
  if [ -e "$1" ] && [ ! -f "$1" ]; then conflict "$1 exists and is not a regular file -- refusing to write there."; fi
}
want_dir() {    # a path that must be absent or a directory
  if [ -e "$1" ] && [ ! -d "$1" ]; then conflict "$1 exists and is not a directory -- refusing to write under it."; fi
}
while IFS= read -r rel; do
  dst="$TARGET/$rel"
  if [ -f "$dst" ] && ! cmp -s "$SRC/$rel" "$dst"; then
    conflict "$dst exists and differs -- refusing to overwrite."
  else
    want_file "$dst"
  fi
  _d="$(dirname "$rel")"
  while [ "$_d" != "." ] && [ "$_d" != "/" ]; do
    want_dir "$TARGET/$_d"
    _d="$(dirname "$_d")"
  done
done < "$LIST"
want_file "$TARGET/DOCKET.md"
want_file "$ATTRS"
want_file "$HOOK"
want_dir "$HOOKS_DIR"
if [ "$CONFLICTS" -ne 0 ]; then
  echo "docket:        move it aside (or merge by hand) and re-run." >&2
  echo "docket:        nothing was written." >&2
  exit 1
fi

# Record the directories this install is about to create (outermost first), so
# the uninstaller can remove them again if they are empty.
note_new_dirs() {
  _d="$(dirname "$1")"
  _missing=""
  while [ "$_d" != "." ] && [ "$_d" != "/" ] && [ ! -d "$TARGET/$_d" ]; do
    _missing="$_d
$_missing"
    _d="$(dirname "$_d")"
  done
  printf '%s' "$_missing" | while IFS= read -r _m; do
    if [ -n "$_m" ]; then printf 'dir\t%s\n' "$_m" >> "$NEW"; fi
  done
  return 0
}

note_file() {  # note_file <relative path>: hash of what was just written
  _h="$(git -C "$TARGET" hash-object --no-filters -- "$TARGET/$1")"
  printf 'file\t%s\t%s\n' "$_h" "$1" >> "$NEW"
}

# --- the checks and the suite that arms them, and the CI workflow ------------
# Copied whole. A check installed without its fixture pair is a check nobody
# has seen fail, which PROTOCOL.md 8.2 does not accept as installed.
while IFS= read -r rel; do
  dst="$TARGET/$rel"
  if [ -f "$dst" ]; then continue; fi   # identical (preflight): nothing to do
  note_new_dirs "$rel"
  mkdir -p "$(dirname "$dst")"
  cp "$SRC/$rel" "$dst"
  note_file "$rel"
done < "$LIST"

# --- starter ledger (never overwrite a real one) ----------------------------
if [ -f "$TARGET/DOCKET.md" ]; then
  echo "docket: DOCKET.md already present -- left untouched"
else
  cp "$SRC/templates/DOCKET.md" "$TARGET/DOCKET.md"
  note_file "DOCKET.md"
  echo "docket: starter ledger -> $TARGET/DOCKET.md"
fi

# --- .gitattributes stanza --------------------------------------------------
# Idempotence keys on whether the LEDGER already has attributes, not on the
# stanza's own prose. Keying on the prose means a repo that wrote its own
# equivalent rule -- as this one did -- gets the stanza appended anyway, and
# ends up declaring `DOCKET.md text eol=lf` twice. Found by running this
# installer against Docket itself.
# Docket's stanza runs from its opening line to the first closing "# ----" line
# after it. The same awk program is in uninstall.sh; keep the two in step.
extract_stanza() {
  awk '!inb && /^# --- Docket ledger:/ { inb = 1; print; next }
       inb { print }
       inb && /^# -+[ \t\r]*$/ { found = 1; exit }
       END { exit !found }' "$1"
}
STANZA_HASH="$(extract_stanza "$SRC/templates/gitattributes-stanza" | tr -d '\r' | git hash-object --stdin)"
if grep -qE '^[[:space:]]*DOCKET\.md[[:space:]]' "$ATTRS" 2>/dev/null; then
  echo "docket: .gitattributes already configures DOCKET.md -- left untouched"
else
  if [ -f "$ATTRS" ]; then
    printf 'attr\tappended\t%s\n' "$STANZA_HASH" >> "$NEW"
    # Start the stanza on a line of its own even if the file lacks a final newline.
    if [ -s "$ATTRS" ] && [ -n "$(tail -c 1 "$ATTRS")" ]; then printf '\n' >> "$ATTRS"; fi
  else
    printf 'attr\tcreated\t%s\n' "$STANZA_HASH" >> "$NEW"
  fi
  cat "$SRC/templates/gitattributes-stanza" >> "$ATTRS"
  echo "docket: .gitattributes stanza appended"
fi

# --- pre-commit hook --------------------------------------------------------
mkdir -p "$HOOKS_DIR"
if [ -f "$HOOK" ] && grep -q '^# --- docket-checks (installed by' "$HOOK" 2>/dev/null; then
  echo "docket: pre-commit hook already installed at $HOOK"
else
  if [ ! -f "$HOOK" ]; then printf '#!/bin/sh\n' > "$HOOK"; fi
  printf 'hook\t%s/pre-commit\n' "$HOOKS_GIT_SPELLING" >> "$NEW"
  if [ -s "$HOOK" ] && [ -n "$(tail -c 1 "$HOOK")" ]; then printf '\n' >> "$HOOK"; fi
  cat >> "$HOOK" <<EOF
# --- docket-checks (installed by Docket templates/install.sh) ---------------
# Root from the COMMITTING worktree, resolved now, at hook time.
DOCKET_ROOT="\$(git rev-parse --show-toplevel)"
if [ -f "\$DOCKET_ROOT/DOCKET.md" ]; then
  ( cd "\$DOCKET_ROOT" && PYTHONDONTWRITEBYTECODE=1 $PY checks/check_duplicate_ids.py DOCKET.md ) || exit 1
  ( cd "\$DOCKET_ROOT" && PYTHONDONTWRITEBYTECODE=1 $PY checks/check_claim_collision.py DOCKET.md ) || exit 1
fi
# --- end docket-checks ------------------------------------------------------
EOF
  chmod +x "$HOOK"
  echo "docket: pre-commit hook -> $HOOK"
fi

# --- install manifest: merge with any earlier one, so a re-install keeps it --
flush_manifest

# --- self-verification ------------------------------------------------------
# Execute the installed checks, here, now. An installer that reports success
# without running the thing it installed has verified nothing.
#
# Every check that reads a SINGLE ledger runs below. The two range-scoped
# checks (state transitions, commit ids) are deliberately absent: both
# compare a ledger across a commit range, and at install time there is one
# version and no range. CI runs those two; this cannot, and does not pretend
# to. That distinction is the point -- "did not run" is not "passed".
#
# Do not leave bytecode or pytest caches behind in the adopter's tree.
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE
echo "docket: verifying -- running the installed single-ledger checks against $TARGET"
cd "$TARGET"

"$PY" checks/check_duplicate_ids.py DOCKET.md
"$PY" checks/check_merge_driver.py DOCKET.md
"$PY" checks/check_pending_markers.py DOCKET.md

# The closure check reads HEAD, and refuses to decide reachability in a shallow
# clone. It is verification only (the install is complete either way), so where
# it cannot run, say so and carry on.
SKIP_REASON=""
if ! git rev-parse --verify -q HEAD >/dev/null 2>&1; then
  SKIP_REASON="the current branch has no commits yet"
  SKIP_SHORT="no commits yet"
elif [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "true" ]; then
  SKIP_REASON="this is a shallow clone, where commit reachability cannot be decided"
  SKIP_SHORT="shallow clone"
fi
if [ -z "$SKIP_REASON" ]; then
  "$PY" checks/check_closure_references.py DOCKET.md
  CLOSURE_NOTE=""
else
  echo "docket: NOTICE -- closure check SKIPPED: $SKIP_REASON."
  echo "docket:          It runs in CI, and here once there is history to check."
  CLOSURE_NOTE=" (closure check skipped: $SKIP_SHORT)"
fi

# check_phantom_ids.py is NOT run here, on purpose. It reads TRACKED files
# (git ls-files), and nothing this installer just wrote has been committed
# yet -- so it would scan almost nothing and print a PASS that means nothing.
# A vacuous green is worse than an absent one. CI runs it on your first push,
# which is the first moment it has anything to read.

# Nested-run guard: when this installer is itself invoked from the suite, do
# not start a second suite -- the suite installs, and the install would run
# the suite, without end.
if [ -n "${PYTEST_CURRENT_TEST:-}" ]; then
  echo "docket: OK -- checks ran clean$CLOSURE_NOTE; suite skipped (already inside a test run)."
elif "$PY" -m pytest --version >/dev/null 2>&1; then
  # Say this BEFORE the silence starts. The suite spawns a git repository per
  # case, which is slow where git subprocesses are expensive (Windows) -- and
  # a long quiet step is indistinguishable from a hung one, which is how a
  # healthy process gets killed and restarted on top of itself.
  echo "docket: running the fixture suite that arms these checks. It builds a"
  echo "docket:   scratch git repo per case: a few seconds on Linux/macOS, and"
  echo "docket:   noticeably longer on Windows, where git subprocesses are far"
  echo "docket:   more expensive. Be patient; it is not hung."
  "$PY" -m pytest tests/test_checks.py -q -p no:cacheprovider
  echo "docket: OK -- checks ran clean$CLOSURE_NOTE and the fixture suite passed."
else
  echo "docket: NOTICE -- fixture suite NOT RUN (pytest is not installed here)."
  echo "docket:          the checks above DID run and are clean; the suite that"
  echo "docket:          arms them has not been executed on this machine. Run:"
  echo "docket:              $PY -m pip install pytest && $PY -m pytest tests/test_checks.py"
  echo "docket: OK -- checks ran clean$CLOSURE_NOTE; suite pending (see NOTICE above)."
fi
