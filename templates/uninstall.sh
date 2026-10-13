#!/bin/sh
# Remove what templates/install.sh installed -- and only that.
#
# Usage: uninstall.sh [--skip-hook] /path/to/your-repo
#
# Reads the install manifest the installer wrote inside the repository's git
# directory (`git rev-parse --git-path docket-install.manifest`), and:
#   * removes each listed file ONLY if its content still matches the hash
#     recorded at install time; a file you have changed is left in place, with
#     a message (this includes DOCKET.md once you have added rows to it);
#   * removes Docket's marked block from the pre-commit hook -- but only when
#     that hook is this checkout's own and can be cut: if core.hooksPath is set,
#     the repository has linked worktrees, the recorded hook is not the one Git
#     resolves now, the hook carries a Docket block this checkout did not record
#     writing, one of the block's two marker lines is missing, or both were edited
#     while the hook still runs the installed checks/ scripts, the whole uninstall
#     is REFUSED before any file is removed (exit 2, nothing changed) with the
#     manual steps; delete the block by hand, then re-run (with --skip-hook where
#     the reason is sharing), which is allowed only once no Docket block remains
#     in the hook and it no longer runs the installed checks/ scripts;
#   * removes Docket's stanza from .gitattributes only if it is still exactly
#     what was installed (opening line, closing line and text, by hash); if it
#     is not, the file is left untouched and you are told what to remove;
#   * removes Python bytecode of Docket's own scripts, and then any directory
#     the installer created, but only if it is now empty.
# It never deletes a directory wholesale and never touches a file that is not
# in the manifest. A manifest file or directory entry it cannot safely act on
# (absolute, or climbing out of the repository) is ignored with a message and
# stays in the manifest, and the manifest is deleted only when every entry has
# been dealt with. If you give a subdirectory of the repository it uses the
# repository's top level and says so. Running it twice is harmless.
set -eu

# Print data verbatim: plain echo interprets backslashes in some shells (dash).
say() { printf '%s\n' "$*"; }

SKIP_HOOK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-hook) SKIP_HOOK=1; shift ;;
    --) shift; break ;;
    -*) echo "docket: ERROR: unknown option $1 (usage: uninstall.sh [--skip-hook] /path/to/your-repo)" >&2; exit 2 ;;
    *) break ;;
  esac
done
TARGET="${1:?usage: uninstall.sh [--skip-hook] /path/to/your-repo}"
if ! git -C "$TARGET" rev-parse --show-toplevel >/dev/null 2>&1; then
  say "docket: ERROR: $TARGET is not a git worktree" >&2
  exit 2
fi
GIVEN="$(cd "$TARGET" && pwd -P)"
TARGET="$(cd "$(git -C "$GIVEN" rev-parse --show-toplevel)" && pwd -P)"
if [ "$GIVEN" != "$TARGET" ]; then
  say "docket: note: $GIVEN is inside the repository whose top level is $TARGET; using the top level."
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
  say "docket: nothing to uninstall -- no install manifest for this working tree ($MANIFEST)."
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

# --- shared hooks: refuse rather than guess ----------------------------------
# A hook is shared when core.hooksPath is set (any scope) or the repository has
# linked worktrees: one hook file then serves several checkouts, and Docket's
# block calls checks/ in whichever one commits. Removing this checkout's files
# would break the others' commits; cutting the block disarms their check. So
# when there is a hook to deal with and it may be shared, or the recorded hook
# is not the one Git resolves now, NOTHING is changed (exit 2) and the manual
# steps are printed. --skip-hook continues once no Docket block is left in it.
# (shared_hook_reason is the same function as in install.sh; keep them in step.)
shared_hook_reason() {
  _hp="$(git -C "$TARGET" config --get core.hooksPath 2>/dev/null || true)"
  if [ -n "$_hp" ]; then say "core.hooksPath is set ($_hp)"; fi
  _wt="$(git -C "$TARGET" worktree list --porcelain 2>/dev/null | grep -c '^worktree ' || true)"
  if [ "${_wt:-1}" -gt 1 ]; then say "the repository has linked worktrees ($_wt checkouts share one hooks directory)"; fi
}
has_block() {
  [ -f "$1" ] || return 1
  if grep -q '^# --- docket-checks (installed by' "$1"; then return 0; fi
  grep -q '^# --- end docket-checks' "$1"
}
hook_abs() {
  case "$1" in
    /*|[A-Za-z]:*) say "$1" ;;
    *) say "$TARGET/$1" ;;
  esac
}
refuse() {   # refuse <headline>; prints the manual steps and exits 2
  echo "docket: REFUSING to uninstall -- nothing was changed."
  say "docket:   $1"
  if [ -n "$REASONS" ]; then
    say "$REASONS" | while IFS= read -r _r; do
      if [ -n "$_r" ]; then say "docket:   - $_r"; fi
    done
  fi
  say "docket:   The hook Git resolves for this repository is: $EXPECTED_HOOK"
  echo "docket:   Docket's block there calls checks/ in whichever checkout commits, so removing this"
  echo "docket:   checkout's files first would break commits, and removing the block disarms Docket's"
  echo "docket:   pre-commit check for every checkout that uses that hook file. If you accept that:"
  echo "docket:     1. open that hook file and delete the lines from '# --- docket-checks (installed by'"
  echo "docket:        through '# --- end docket-checks'. If one of those two marker lines is missing or"
  echo "docket:        was edited, delete every remaining Docket line instead: everything from where Docket's"
  echo "docket:        block started to where it ended, including any if/fi lines around it. If unsure,"
  echo "docket:        restore the hook to the content it had before the install;"
  say "docket:     2. re-run: sh uninstall.sh --skip-hook $TARGET"
  echo "docket:   Otherwise leave Docket installed here."
  exit 2
}
HOOK_RECORDED="$(awk -F "$TAB" '$1 == "hook" { print $2 }' "$MANIFEST")"
REASONS="$(shared_hook_reason)"
RECORDED_BLOCKS=""
while IFS= read -r _rec; do
  [ -n "$_rec" ] || continue
  _abs="$(hook_abs "$_rec")"
  if [ "$_abs" != "$EXPECTED_HOOK" ]; then
    REASONS="$REASONS
the manifest recorded the hook $_abs, but Git resolves $EXPECTED_HOOK now"
    if has_block "$_abs"; then RECORDED_BLOCKS="$RECORDED_BLOCKS $_abs"; fi
  fi
done <<EOF
$HOOK_RECORDED
EOF
if [ -z "$HOOK_RECORDED" ] && has_block "$EXPECTED_HOOK"; then
  REASONS="$REASONS
the hook Git resolves carries a Docket block that this checkout's manifest did not record writing"
fi
# A block the cutter cannot recognise: one marker line missing, or both edited
# while the hook still runs Docket's installed check scripts. Either way, removing
# checks/ first would leave a hook calling scripts that are gone.
CHECK_SCRIPTS="$(awk -F "$TAB" '$1 == "file" && $3 ~ "^checks/.*[.]py$" { print $3 }' "$MANIFEST")"
hook_runs_docket_checks() {
  [ -f "$1" ] || return 1
  while IFS= read -r _c; do
    [ -n "$_c" ] || continue
    if grep -qF -- "$_c" "$1"; then return 0; fi
  done <<EOF
$CHECK_SCRIPTS
EOF
  return 1
}
if [ -f "$EXPECTED_HOOK" ]; then
  _s=0; _e=0
  if grep -q '^# --- docket-checks (installed by' "$EXPECTED_HOOK"; then _s=1; fi
  if grep -q '^# --- end docket-checks' "$EXPECTED_HOOK"; then _e=1; fi
  if [ "$_s" != "$_e" ]; then
    REASONS="$REASONS
the hook Git resolves carries a Docket block with one of its marker lines missing"
  elif [ "$_s" = 0 ] && hook_runs_docket_checks "$EXPECTED_HOOK"; then
    REASONS="$REASONS
the hook Git resolves runs Docket's installed check scripts, but no Docket marker lines are left to cut"
  fi
fi
NEEDS_HOOK=0
if [ -n "$HOOK_RECORDED" ] || has_block "$EXPECTED_HOOK" || hook_runs_docket_checks "$EXPECTED_HOOK"; then NEEDS_HOOK=1; fi
HOOK_MODE=normal
if [ "$SKIP_HOOK" = 1 ]; then
  if has_block "$EXPECTED_HOOK" || [ -n "$RECORDED_BLOCKS" ]; then
    refuse "--skip-hook is only allowed once no Docket block remains in the hook, and one does (${RECORDED_BLOCKS:-$EXPECTED_HOOK})."
  fi
  if hook_runs_docket_checks "$EXPECTED_HOOK"; then
    refuse "--skip-hook is only allowed once the hook no longer runs Docket's check scripts, and it still does ($EXPECTED_HOOK)."
  fi
  HOOK_MODE=skip
elif [ "$NEEDS_HOOK" = 1 ] && [ -n "$(say "$REASONS" | tr -d '[:space:]')" ]; then
  refuse "There is a Docket hook to deal with, and it may be shared, is not the one recorded, was not recorded by this checkout, or cannot be cut."
fi

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
        say "docket: ignored manifest entry (path is outside this repository): $rel"
        printf 'file\t%s\t%s\n' "$want" "$rel" >> "$KEEP"
        continue
      fi
      if [ ! -f "$path" ]; then
        continue                                  # already gone
      fi
      have="$(git -C "$TARGET" hash-object --no-filters -- "$path")"
      if [ "$have" = "$want" ]; then
        rm -f "$path"
        say "docket: removed $rel"
        case "$rel" in
          *.py)   # bytecode of this script only, never a neighbour's
            d="$(dirname "$path")"; stem="$(basename "$rel" .py)"
            for f in "$d/__pycache__/$stem".*.pyc; do
              if [ -f "$f" ]; then rm -f "$f"; fi
            done
            rmdir "$d/__pycache__" 2>/dev/null || true ;;
        esac
      else
        say "docket: left in place (changed since install): $rel"
        printf 'file\t%s\t%s\n' "$want" "$rel" >> "$KEEP"
      fi ;;
    dir)
      if safe_rel "$a" && [ "$a" != "." ]; then
        printf '%s\n' "$a" >> "$DIRS"
      else
        say "docket: ignored manifest entry (directory is outside this repository): $a"
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
    # Exactly one block, then stop (a later look-alike marker starts nothing).
    # BINMODE=3 keeps the user's CR bytes on Git for Windows' awk; any other awk
    # treats it as an ordinary variable.
    awk -v BINMODE=3 \
        '!done && !skip && /^# --- docket-checks \(installed by/ { skip = 1 }
         !skip { print }
         skip && /^# --- end docket-checks/ { skip = 0; done = 1 }' "$hook" > "$WORK/hook.new"
    cat "$WORK/hook.new" > "$hook"
    if awk 'NF && !/^#!/ { n++ } END { exit (n > 0) }' "$hook"; then
      rm -f "$hook"
      say "docket: removed pre-commit hook $hook (nothing else was in it)"
    else
      say "docket: removed Docket's block from $hook (your other hook lines are kept)"
    fi
  elif [ "$has_start" = 0 ] && [ "$has_end" = 0 ]; then
    say "docket: no Docket block found in $hook -- nothing to remove"
  else
    say "docket: Docket's block in $hook is missing one of its marker lines -- left as is."
    echo "docket:   remove the lines from '# --- docket-checks' to '# --- end docket-checks' by hand."
    return 1
  fi
}

if [ "$HOOK_MODE" = normal ] && [ -s "$HOOKS" ]; then
  if ! remove_hook_block "$EXPECTED_HOOK"; then
    printf 'hook\t%s\n' "$HOOK_SPELLING" >> "$KEEP"
  fi
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
    awk -v BINMODE=3 \
        '!done && !skip && /^# --- Docket ledger:/ { skip = 1 }
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
    say "docket: removed empty directory $d/"
  else
    say "docket: kept $d/ (it still holds other files)"
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
