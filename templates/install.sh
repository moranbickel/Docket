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
TARGET="$(cd "$TARGET" && pwd)"

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "docket: ERROR: no python3 or python on PATH -- the checks cannot run" >&2
  exit 2
fi

# Never clobber a file that exists and differs: say which one, and stop.
# An identical file is a no-op, which also makes the installer idempotent and
# lets you run it against a clone of Docket itself (`install.sh .`) -- there
# src and dst are literally the same path, and cp refuses that.
copy_file() {
  _src="$1"; _dst="$2"
  if [ -f "$_dst" ]; then
    if cmp -s "$_src" "$_dst"; then
      return 0
    fi
    echo "docket: ERROR: $_dst exists and differs -- refusing to overwrite." >&2
    echo "docket:        move it aside (or merge by hand) and re-run." >&2
    exit 1
  fi
  mkdir -p "$(dirname "$_dst")"
  cp "$_src" "$_dst"
}

# --- the checks and the suite that arms them --------------------------------
# Copied whole. A check installed without its fixture pair is a check nobody
# has seen fail, which PROTOCOL.md 8.2 does not accept as installed.
( cd "$SRC" && find checks tests -type f ! -path '*__pycache__*' ! -name '*.pyc' ) |
while IFS= read -r rel; do
  copy_file "$SRC/$rel" "$TARGET/$rel"
done

# --- CI workflow ------------------------------------------------------------
copy_file "$SRC/.github/workflows/ledger-ci.yml" \
          "$TARGET/.github/workflows/ledger-ci.yml"

# --- starter ledger (never overwrite a real one) ----------------------------
if [ -f "$TARGET/DOCKET.md" ]; then
  echo "docket: DOCKET.md already present -- left untouched"
else
  cp "$SRC/templates/DOCKET.md" "$TARGET/DOCKET.md"
  echo "docket: starter ledger -> $TARGET/DOCKET.md"
fi

# --- .gitattributes stanza --------------------------------------------------
# Idempotence keys on whether the LEDGER already has attributes, not on the
# stanza's own prose. Keying on the prose means a repo that wrote its own
# equivalent rule -- as this one did -- gets the stanza appended anyway, and
# ends up declaring `DOCKET.md text eol=lf` twice. Found by running this
# installer against Docket itself.
if grep -qE '^[[:space:]]*DOCKET\.md[[:space:]]' "$TARGET/.gitattributes" 2>/dev/null; then
  echo "docket: .gitattributes already configures DOCKET.md -- left untouched"
else
  cat "$SRC/templates/gitattributes-stanza" >> "$TARGET/.gitattributes"
  echo "docket: .gitattributes stanza appended"
fi

# --- pre-commit hook --------------------------------------------------------
HOOKS_DIR="$(git -C "$TARGET" rev-parse --git-path hooks)"
case "$HOOKS_DIR" in
  /*|[A-Za-z]:*) ;;
  *) HOOKS_DIR="$TARGET/$HOOKS_DIR" ;;
esac
mkdir -p "$HOOKS_DIR"
HOOK="$HOOKS_DIR/pre-commit"

if [ -f "$HOOK" ] && grep -q 'docket-checks' "$HOOK" 2>/dev/null; then
  echo "docket: pre-commit hook already installed at $HOOK"
else
  if [ ! -f "$HOOK" ]; then printf '#!/bin/sh\n' > "$HOOK"; fi
  cat >> "$HOOK" <<EOF
# --- docket-checks (installed by Docket templates/install.sh) ---------------
# Root from the COMMITTING worktree, resolved now, at hook time.
DOCKET_ROOT="\$(git rev-parse --show-toplevel)"
if [ -f "\$DOCKET_ROOT/DOCKET.md" ]; then
  ( cd "\$DOCKET_ROOT" && $PY checks/check_duplicate_ids.py DOCKET.md ) || exit 1
  ( cd "\$DOCKET_ROOT" && $PY checks/check_claim_collision.py DOCKET.md ) || exit 1
fi
# --- end docket-checks ------------------------------------------------------
EOF
  chmod +x "$HOOK"
  echo "docket: pre-commit hook -> $HOOK"
fi

# --- self-verification ------------------------------------------------------
# Execute the installed checks, here, now. An installer that reports success
# without running the thing it installed has verified nothing.
#
# Every check that reads a SINGLE ledger runs below. The two range-scoped
# checks (state transitions, commit ids) are deliberately absent: both
# compare a ledger across a commit range, and at install time there is one
# version and no range. CI runs those two; this cannot, and does not pretend
# to. That distinction is the point -- "did not run" is not "passed".
echo "docket: verifying -- running the installed single-ledger checks against $TARGET"
cd "$TARGET"

"$PY" checks/check_duplicate_ids.py DOCKET.md
"$PY" checks/check_merge_driver.py DOCKET.md
"$PY" checks/check_pending_markers.py DOCKET.md
"$PY" checks/check_closure_references.py DOCKET.md

# check_phantom_ids.py is NOT run here, on purpose. It reads TRACKED files
# (git ls-files), and nothing this installer just wrote has been committed
# yet -- so it would scan almost nothing and print a PASS that means nothing.
# A vacuous green is worse than an absent one. CI runs it on your first push,
# which is the first moment it has anything to read.

# Nested-run guard: when this installer is itself invoked from the suite, do
# not start a second suite -- the suite installs, and the install would run
# the suite, without end.
if [ -n "${PYTEST_CURRENT_TEST:-}" ]; then
  echo "docket: OK -- checks ran clean; suite skipped (already inside a test run)."
elif "$PY" -m pytest --version >/dev/null 2>&1; then
  # Say this BEFORE the silence starts. The suite spawns a git repository per
  # case and takes minutes, most of them on Windows -- and a long quiet step
  # is indistinguishable from a hung one, which is how a healthy process gets
  # killed and restarted on top of itself.
  echo "docket: running the fixture suite that arms these checks -- this"
  echo "docket:   builds a scratch git repo per case and takes a few minutes."
  "$PY" -m pytest tests/test_checks.py -q
  echo "docket: OK -- checks ran clean and the fixture suite passed."
else
  echo "docket: NOTICE -- fixture suite NOT RUN (pytest is not installed here)."
  echo "docket:          the checks above DID run and are clean; the suite that"
  echo "docket:          arms them has not been executed on this machine. Run:"
  echo "docket:              $PY -m pip install pytest && $PY -m pytest tests/test_checks.py"
  echo "docket: OK -- checks ran clean; suite pending (see NOTICE above)."
fi
