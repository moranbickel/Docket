#!/bin/sh
# Remove what templates/install.sh installed -- and only that.
#
# Usage: uninstall.sh /path/to/your-repo
#
# Reads the install manifest the installer wrote inside the repository's git
# directory (`git rev-parse --git-path docket-install.manifest`), and:
#   * removes each listed file ONLY if its content still matches the hash
#     recorded at install time; a file you have changed is left in place, with
#     a message (this includes DOCKET.md once you have added rows to it);
#   * removes Docket's marked block from the pre-commit hook the installer
#     modified, and deletes that hook only if nothing but a shebang remains;
#   * removes Docket's marked stanza from .gitattributes, and deletes that file
#     only if the installer created it and nothing else remains;
#   * removes Python bytecode of Docket's own scripts, and then any directory
#     the installer created, but only if it is now empty.
# It never deletes a directory wholesale and never touches a file that is not
# in the manifest. Running it twice is harmless.
set -eu

TARGET="${1:?usage: uninstall.sh /path/to/your-repo}"
if ! git -C "$TARGET" rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "docket: ERROR: $TARGET is not a git worktree" >&2
  exit 2
fi
TARGET="$(cd "$TARGET" && pwd)"

_p="$(git -C "$TARGET" rev-parse --git-path docket-install.manifest)"
case "$_p" in
  /*|[A-Za-z]:*) MANIFEST="$_p" ;;
  *) MANIFEST="$TARGET/$_p" ;;
esac

if [ ! -f "$MANIFEST" ]; then
  echo "docket: nothing to uninstall -- no install manifest for this working tree ($MANIFEST)."
  exit 0
fi

TAB="$(printf '\t')"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
KEEP="$WORK/keep"      # manifest entries that still apply after this run
DIRS="$WORK/dirs"
HOOKS="$WORK/hooks"
ATTR="$WORK/attr"
printf '# docket install manifest v1\n' > "$KEEP"
: > "$DIRS"; : > "$HOOKS"; : > "$ATTR"

# --- files: remove only what is unchanged since the install -----------------
while IFS="$TAB" read -r kind a b || [ -n "$kind" ]; do
  case "$kind" in
    file)
      rel="$b"; want="$a"; path="$TARGET/$rel"
      if [ ! -f "$path" ]; then
        continue                                  # already gone
      fi
      have="$(git -C "$TARGET" hash-object --no-filters -- "$path")"
      if [ "$have" = "$want" ]; then
        rm -f "$path"
        echo "docket: removed $rel"
        case "$rel" in
          *.py)   # bytecode of this script only, never a neighbour's
            d="$(dirname "$path")"; stem="$(basename "$rel" .py)"
            for f in "$d/__pycache__/$stem".*.pyc; do
              if [ -f "$f" ]; then rm -f "$f"; fi
            done
            rmdir "$d/__pycache__" 2>/dev/null || true ;;
        esac
      else
        echo "docket: left in place (changed since install): $rel"
        printf 'file\t%s\t%s\n' "$want" "$rel" >> "$KEEP"
      fi ;;
    dir)  printf '%s\n' "$a" >> "$DIRS" ;;
    hook) printf '%s\n' "$a" >> "$HOOKS" ;;
    attr) printf '%s\n' "$a" >> "$ATTR" ;;
  esac
done < "$MANIFEST"

# --- pre-commit hook: take out Docket's block, and only that ----------------
while IFS= read -r hook; do
  [ -n "$hook" ] || continue
  if [ ! -f "$hook" ]; then
    # The directory may have moved (core.hooksPath changed); ask Git now.
    cand="$(git -C "$TARGET" rev-parse --git-path hooks)/pre-commit"
    case "$cand" in /*|[A-Za-z]:*) ;; *) cand="$TARGET/$cand" ;; esac
    if [ -f "$cand" ]; then hook="$cand"; else continue; fi
  fi
  if grep -q '^# --- docket-checks (installed by' "$hook" &&
     grep -q '^# --- end docket-checks' "$hook"; then
    awk '/^# --- docket-checks \(installed by/ { skip = 1 }
         !skip { print }
         /^# --- end docket-checks/ { skip = 0 }' "$hook" > "$WORK/hook.new"
    cat "$WORK/hook.new" > "$hook"
    if awk 'NF && !/^#!/ { n++ } END { exit (n > 0) }' "$hook"; then
      rm -f "$hook"
      echo "docket: removed pre-commit hook $hook (nothing else was in it)"
    else
      echo "docket: removed Docket's block from $hook (your other hook lines are kept)"
    fi
  else
    echo "docket: no Docket block found in $hook -- left as is"
  fi
done < "$HOOKS"

# --- .gitattributes: take out Docket's stanza, and only that ----------------
if [ -s "$ATTR" ] && [ -f "$TARGET/.gitattributes" ]; then
  attrs="$TARGET/.gitattributes"
  if grep -q '^# --- Docket ledger:' "$attrs"; then
    awk '/^# --- Docket ledger:/ { skip = 1 }
         !skip { print }
         skip && /^# -+[ \t\r]*$/ { skip = 0 }' "$attrs" > "$WORK/attrs.new"
    cat "$WORK/attrs.new" > "$attrs"
    if awk 'NF { n++ } END { exit (n > 0) }' "$attrs" && grep -qx created "$ATTR"; then
      rm -f "$attrs"
      echo "docket: removed .gitattributes (Docket created it and nothing else was in it)"
    else
      echo "docket: removed Docket's stanza from .gitattributes (your other rules are kept)"
    fi
  fi
fi

# --- directories the installer created: remove only if now empty ------------
sort -r "$DIRS" | while IFS= read -r d; do
  [ -n "$d" ] || continue
  [ -d "$TARGET/$d" ] || continue
  if rmdir "$TARGET/$d" 2>/dev/null; then
    echo "docket: removed empty directory $d/"
  else
    echo "docket: kept $d/ (it still holds other files)"
    # Keep tracking it if a changed Docket file still lives under it.
    if awk -F "$TAB" -v d="$d/" 'index($3, d) == 1 { f = 1 } END { exit !f }' "$KEEP"; then
      printf 'dir\t%s\n' "$d" >> "$KEEP"
    fi
  fi
done

# --- manifest: keep only what still applies ---------------------------------
if [ "$(wc -l < "$KEEP")" -le 1 ]; then
  rm -f "$MANIFEST"
  echo "docket: uninstalled. Commit the removal if you had committed the install."
else
  cat "$KEEP" > "$MANIFEST"
  echo "docket: uninstalled, except the file(s) listed above that you have changed."
  echo "docket: delete them by hand, or re-run this script after reverting them."
fi
