#!/bin/sh
# Install the Docket pre-commit checks into a target repo.
# Usage: install-hooks.sh /path/to/your-repo
#
# The hook resolves everything from the COMMITTING worktree at commit time --
# no environment variables, no baked-in absolute paths (PROTOCOL.md section
# 4.4: an env-var root set by one session silently points another session's
# hook at the wrong ledger).
set -eu

TARGET="${1:?usage: install-hooks.sh /path/to/your-repo}"
HOOKS_DIR="$(git -C "$TARGET" rev-parse --git-path hooks)"
CHECKS_SRC="$(cd "$(dirname "$0")/../checks" && pwd)"

mkdir -p "$TARGET/.docket-checks"
cp "$CHECKS_SRC/_ledger.py" \
   "$CHECKS_SRC/check_duplicate_ids.py" \
   "$CHECKS_SRC/check_claim_collision.py" \
   "$TARGET/.docket-checks/"

HOOK="$HOOKS_DIR/pre-commit"
if [ -f "$HOOK" ] && grep -q docket-checks "$HOOK" 2>/dev/null; then
  echo "docket: pre-commit hook already installed at $HOOK"
  exit 0
fi

cat >> "$HOOK" <<'EOF'
# --- docket-checks (installed by Docket templates/install-hooks.sh) ---------
# Root from the COMMITTING worktree, resolved now, at hook time.
DOCKET_ROOT="$(git rev-parse --show-toplevel)"
if [ -f "$DOCKET_ROOT/DOCKET.md" ]; then
  python3 "$DOCKET_ROOT/.docket-checks/check_duplicate_ids.py" "$DOCKET_ROOT/DOCKET.md" || exit 1
  ( cd "$DOCKET_ROOT" && python3 .docket-checks/check_claim_collision.py DOCKET.md ) || exit 1
fi
# --- end docket-checks -------------------------------------------------------
EOF
chmod +x "$HOOK"
echo "docket: installed duplicate-id + claim-collision pre-commit checks -> $HOOK"
