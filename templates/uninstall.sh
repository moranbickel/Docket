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
#   * removes Docket's marked block from the pre-commit hook Git resolves for
#     this repository now (so a renamed or moved repository is still found) --
#     only if both of its marker lines are still there -- and deletes that hook
#     only if nothing but a shebang remains;
#   * removes Docket's stanza from .gitattributes only if it is still exactly
#     what was installed (opening line, closing line and text, by hash); if it
#     is not, the file is left untouched and you are told what to remove;
#   * removes Python bytecode of Docket's own scripts, and then any directory
#     the installer created, but only if it is now empty.
# It never deletes a directory wholesale and never touches a file that is not
# in the manifest. A manifest entry it cannot safely act on (a path that is
# absolute, climbs out of the repository, or a hook that is not this
# repository's) is ignored with a message and stays in the manifest, and the
# manifest is deleted only when every entry has been dealt with. If you give a
# subdirectory of the repository it uses the repository's top level and says
# so. Running it twice is harmless.
set -eu

TARGET="${1:?usage: uninstall.sh /path/to/your-repo}"
if ! git -C "$TARGET" rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "docket: ERROR: $TARGET is not a git worktree" >&2
  exit 2
fi
GIVEN="$(cd "$TARGET" && pwd -P)"
TARGET="$(cd "$(git -C "$GIVEN" rev-parse --show-toplevel)" && pwd -P)"
if [ "$GIVEN" != "$TARGET" ]; then
  echo "docket: note: $GIVEN is inside the repository whose top level is $TARGET; using the top level."
fi

abs_git_path() {
  _p="$(git -C "$TARGET" rev-parse --git-path "$1")"
  case "$_p" in
    /*|[A-Za-z]:*) printf '%s\n' "$_p" ;;
    *) printf '%s\n' "$TARGET/$_p" ;;
  esac
}
MANIFEST="$(abs_git_path docket-install.manifest)"
EXPECTED_HOOK="$(abs_git_path hooks)/pre-commit"

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

# A manifest path is usable only if it is relative, has no ".." component, and
# its parent directory really lives inside the top level (symlinks resolved).
safe_rel() {
  case "$1" in
    ""|/*|[A-Za-z]:*|..|../*|*/..|*/../*) return 1 ;;
  esac
  _par="$(dirname "$TARGET/$1")"
  [ -d "$_par" ] || return 0            # parent absent: nothing there to touch
  _phys="$(cd "$_par" && pwd -P)"
  case "$_phys/" in "$TARGET"/*) return 0 ;; esac
  return 1
}

# --- files: remove only what is unchanged since the install -----------------
while IFS="$TAB" read -r kind a b || [ -n "$kind" ]; do
  case "$kind" in
    file)
      rel="$b"; want="$a"; path="$TARGET/$rel"
      if ! safe_rel "$rel"; then
        echo "docket: ignored manifest entry (path is outside this repository): $rel"
        printf 'file\t%s\t%s\n' "$want" "$rel" >> "$KEEP"
        continue
      fi
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
    dir)
      if safe_rel "$a" && [ "$a" != "." ]; then
        printf '%s\n' "$a" >> "$DIRS"
      else
        echo "docket: ignored manifest entry (directory is outside this repository): $a"
        printf 'dir\t%s\n' "$a" >> "$KEEP"
      fi ;;
    hook) printf '%s\n' "$a" >> "$HOOKS" ;;
    attr) printf '%s\t%s\n' "$a" "$b" >> "$ATTR" ;;
  esac
done < "$MANIFEST"

# --- pre-commit hook: take out Docket's block, and only that ----------------
# The hook is the one Git resolves for this repository NOW (so a repository that
# has been renamed or moved is still found), and Docket's block is recognised by
# its exact marker lines. The path recorded in the manifest is advisory: it only
# says that the installer wrote a block.
HOOK_SPELLING="$(git -C "$TARGET" rev-parse --git-path hooks)/pre-commit"

remove_hook_block() {   # remove_hook_block <hook file>; returns 1 if left as is
  hook="$1"
  [ -f "$hook" ] || return 0                      # already gone
  has_start=0; has_end=0
  if grep -q '^# --- docket-checks (installed by' "$hook"; then has_start=1; fi
  if grep -q '^# --- end docket-checks' "$hook"; then has_end=1; fi
  if [ "$has_start" = 1 ] && [ "$has_end" = 1 ]; then
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
  elif [ "$has_start" = 0 ] && [ "$has_end" = 0 ]; then
    echo "docket: no Docket block found in $hook -- nothing to remove"
  else
    echo "docket: Docket's block in $hook is missing one of its marker lines -- left as is."
    echo "docket:   remove the lines from '# --- docket-checks' to '# --- end docket-checks' by hand."
    return 1
  fi
}

if [ -s "$HOOKS" ]; then
  if ! remove_hook_block "$EXPECTED_HOOK"; then
    printf 'hook\t%s\n' "$HOOK_SPELLING" >> "$KEEP"
  fi
  # A recorded path that is a different file from today's hook, yet still holds
  # Docket-looking lines, is not touched; it is named only if it exists.
  while IFS= read -r rec; do
    [ -n "$rec" ] || continue
    case "$rec" in /*|[A-Za-z]:*) rec_abs="$rec" ;; *) rec_abs="$TARGET/$rec" ;; esac
    if [ "$rec_abs" != "$EXPECTED_HOOK" ] && [ -f "$rec_abs" ] &&
       grep -q '^# --- docket-checks (installed by' "$rec_abs"; then
      echo "docket: ignored manifest entry: $rec_abs is not this repository's hook ($EXPECTED_HOOK)"
      echo "docket:   it holds lines that look like Docket's block; left as is. Remove them by hand if they are yours."
      printf 'hook\t%s\n' "$rec" >> "$KEEP"
    fi
  done < "$HOOKS"
fi

# --- .gitattributes: take out Docket's stanza, and only that ----------------
# Docket's stanza runs from its opening line to the first closing "# ----" line
# after it. The same awk program is in install.sh; keep the two in step.
extract_stanza() {
  awk '!inb && /^# --- Docket ledger:/ { inb = 1; print; next }
       inb { print }
       inb && /^# -+[ \t\r]*$/ { found = 1; exit }
       END { exit !found }' "$1"
}
while IFS="$TAB" read -r how want || [ -n "$how" ]; do
  [ -n "$how" ] || continue
  attrs="$TARGET/.gitattributes"
  [ -f "$attrs" ] || continue                     # already gone
  if ! grep -q '^# --- Docket ledger:' "$attrs"; then
    echo "docket: no Docket stanza found in .gitattributes -- nothing to remove"
    continue
  fi
  if [ -n "$want" ] && extract_stanza "$attrs" > "$WORK/stanza" &&
     [ "$(tr -d '\r' < "$WORK/stanza" | git hash-object --stdin)" = "$want" ]; then
    # Exactly one block -- the one whose hash was just verified -- and then stop:
    # a later line that merely looks like the opening line starts nothing.
    awk '!done && !skip && /^# --- Docket ledger:/ { skip = 1 }
         !skip { print }
         skip && /^# -+[ \t\r]*$/ { skip = 0; done = 1 }' "$attrs" > "$WORK/attrs.new"
    cat "$WORK/attrs.new" > "$attrs"
    if awk 'NF { n++ } END { exit (n > 0) }' "$attrs" && [ "$how" = created ]; then
      rm -f "$attrs"
      echo "docket: removed .gitattributes (Docket created it and nothing else was in it)"
    else
      echo "docket: removed Docket's stanza from .gitattributes (your other rules are kept)"
    fi
  else
    echo "docket: .gitattributes left untouched: Docket's stanza is not exactly as installed"
    echo "docket:   (a marker line is missing or its text was edited), so it was not cut."
    echo "docket:   Remove by hand the comment block starting '# --- Docket ledger:' and the"
    echo "docket:   rule 'DOCKET.md text eol=lf', if you no longer want them."
    printf 'attr\t%s\t%s\n' "$how" "$want" >> "$KEEP"
  fi
done < "$ATTR"

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

# --- manifest: delete only when every entry has been dealt with --------------
if [ "$(wc -l < "$KEEP")" -le 1 ]; then
  rm -f "$MANIFEST"
  echo "docket: uninstalled. Commit the removal if you had committed the install."
else
  cat "$KEEP" > "$MANIFEST"
  echo "docket: uninstalled, except what is listed above. Those entries stay in the"
  echo "docket: manifest; re-run this script after you have dealt with them."
fi
