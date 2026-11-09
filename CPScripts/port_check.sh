#!/usr/bin/env bash
# port_check.sh: read-only checks for a branch that is about to become a pull request.
#
# The fork has no CI, so this script is the common check every change runs before it is pushed.
# It never changes the repository, never touches the network and never runs on a server as part
# of an upgrade. Nothing calls it. It only reads git objects and writes to a private temp folder.
#
# Usage: CPScripts/port_check.sh [--base REF]      (default base: origin/v2.3.9)
#        Run it with the branch to check checked out. It compares HEAD with the merge base of REF.
# Exit:  0 no check failed (SKIP lines are listed and are NOT proof)   1 a check failed   2 bad usage
#
# What it checks (added lines and changed files only, never the whole tree):
#   branch          HEAD is not on a production branch (v2.3.9 or main)
#   commit-rules    no co-author or "Generated with" trailer, no em dash, no AI author or committer
#   stray-files     no *.bak *.orig *.rej *.swp, no file ending in ~, no file called nul
#   modes           no mode change of an existing file and no new symlink
#   line-endings    no file gains carriage returns
#   python          every changed *.py parses with Python 3.9 grammar (the server runs 3.9.21).
#                   This is a syntax check only: it does not detect newer library calls
#   shell           every changed shell script passes bash -n
#   ols-guard       added lines do not install, replace or configure OpenLiteSpeed
#                   (autoSSL, acmeEmail, httpd_config, lsws/bin/, installCustomOLSBinaries, the
#                   custom installer URL). A line that names openlitespeed fails only when it
#                   also looks like an install, upgrade, download or replace action and does not
#                   hold the package back (exclude, hold, held, protect or a read-only query)
#   paid-addons     added lines do not name the paid add-ons (heuristic list, see PAID below)
#   secrets         added lines hold no private key header, token prefix or webhook URL
#
# This script and its test are excluded from the content checks, because they must name the
# patterns they look for. The environment variable PORT_CHECK_PYTHON overrides the Python used.

BASE="origin/v2.3.9"
while [ $# -gt 0 ]; do
  case "$1" in
    --base) BASE="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$BASE" ] || { echo "--base needs a ref" >&2; exit 2; }

git rev-parse --git-dir >/dev/null 2>&1 || { echo "not inside a git repository" >&2; exit 2; }
git rev-parse --verify --quiet "$BASE^{commit}" >/dev/null || { echo "base ref not found: $BASE" >&2; exit 2; }
MB="$(git merge-base "$BASE" HEAD 2>/dev/null)" || { echo "no merge base between $BASE and HEAD" >&2; exit 2; }

TMP="$(mktemp -d 2>/dev/null)" || { echo "cannot create a temp folder" >&2; exit 2; }
trap 'rm -rf "$TMP"' EXIT

FAILS=0; SKIPS=0; PASSES=0
pass() { PASSES=$((PASSES + 1)); echo "PASS  $1"; }
fail() { FAILS=$((FAILS + 1)); echo "FAIL  $1"; shift; for l in "$@"; do echo "        $l"; done; }
skip() { SKIPS=$((SKIPS + 1)); echo "SKIP  $1: $2"; }

SELF_RE='^CPScripts/(port_check|test_port_check)\.sh$'
PAID='rspamd|root[ _-]?file[ _-]?manager|email[ _-]?debugger|backup[ _-]?v2|wordpress[ _-]?manager[ _-]?pro|wp[ _-]?manager[ _-]?pro|ssl[ _-]?v2'
# A bare mention of openlitespeed fails only when the line also looks like an install, upgrade,
# download or replace action, and does not hold the package back. This is a heuristic, not proof.
OLS_ACTION='install|upgrade|update|downgrade|reinstall|remove|erase|purge|(wget|curl) .*http|rpm -[iU]|dpkg -i|\<cp\>|\<mv\>|\<rm\>'
OLS_HOLD='exclude|apt-mark|hold|held|protect|dpkg-query|rpm -q|dpkg -s|disablerepo'

# Changed files: status<TAB>path (renames shown as delete plus add).
git diff --name-status --no-renames "$MB" HEAD > "$TMP/changed.txt"
CHANGED_N="$(wc -l < "$TMP/changed.txt" | tr -d ' ')"
echo "base: $BASE ($(git rev-parse --short "$MB"))   head: $(git rev-parse --short HEAD)   commits: $(git rev-list --count "$MB..HEAD")   files changed: $CHANGED_N"
if [ "$CHANGED_N" = "0" ]; then
  echo "nothing to check: HEAD has no changes against the base"; exit 0
fi

# Added lines as path:line:text, without this script and its test.
git diff -U0 --no-color --no-renames "$MB" HEAD | awk '
  /^\+\+\+ /{ f = substr($0, 7); next }
  /^@@/{ match($0, /\+[0-9]+/); n = substr($0, RSTART + 1, RLENGTH - 1) + 0; next }
  /^\+/{ print f ":" n ":" substr($0, 2); n++ }' > "$TMP/added_all.txt"
grep -Ev "^CPScripts/(port_check|test_port_check)\.sh:" "$TMP/added_all.txt" > "$TMP/added.txt" || true

# branch -------------------------------------------------------------------------------------
BR="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
case "$BR" in
  v2.3.9|main) fail "branch" "HEAD is on '$BR': a change must have its own branch" ;;
  HEAD)        pass "branch (detached HEAD, nothing to compare)" ;;
  *)           pass "branch ($BR)" ;;
esac

# commit-rules -------------------------------------------------------------------------------
git log --format='%H%x09%B%x1e' "$MB..HEAD" > "$TMP/msgs.txt"
EMDASH="$(printf '\342\200\224')"
bad=()
# a trailer or footer is a line that starts with the text (an emoji or symbol may come first)
grep -qiE '^co-authored-by:' "$TMP/msgs.txt" && bad+=("a commit message holds a Co-Authored-By trailer")
grep -qiE '^[^A-Za-z]*generated with' "$TMP/msgs.txt" && bad+=("a commit message holds a 'Generated with' line")
grep -q "$EMDASH" "$TMP/msgs.txt" && bad+=("a commit message holds an em dash")
if git log --format='%an %ae %cn %ce' "$MB..HEAD" | grep -qiE 'anthropic|noreply@anthropic\.com'; then
  bad+=("a commit author or committer is an AI identity")
fi
if [ ${#bad[@]} -eq 0 ]; then pass "commit-rules"; else fail "commit-rules" "${bad[@]}"; fi

# stray-files --------------------------------------------------------------------------------
stray="$(awk -F'\t' '$1 != "D" {print $2}' "$TMP/changed.txt" | grep -E '\.(bak|orig|rej|swp)$|~$|(^|/)nul$' || true)"
if [ -z "$stray" ]; then pass "stray-files"; else fail "stray-files" $stray; fi

# modes --------------------------------------------------------------------------------------
git diff --summary --no-renames "$MB" HEAD > "$TMP/summary.txt"
modebad="$(grep -E 'mode change|create mode 120000|delete mode 120000' "$TMP/summary.txt" || true)"
if [ -z "$modebad" ]; then
  pass "modes"
  grep -E 'create mode 100755' "$TMP/summary.txt" | sed 's/^ */  INFO new executable file: /' || true
else
  fail "modes" "$modebad"
fi

# line-endings -------------------------------------------------------------------------------
# numstat prints "-<TAB>-<TAB>path" for a binary file, which has no line endings to check
git diff --numstat --no-renames "$MB" HEAD | awk -F'\t' '$1 == "-" && $2 == "-" {print $3}' > "$TMP/binary.txt"
crbad=()
while IFS=$'\t' read -r st path; do
  [ "$st" = "D" ] && continue
  grep -Fxq -- "$path" "$TMP/binary.txt" && continue
  head_cr="$(git cat-file -p "HEAD:$path" 2>/dev/null | tr -cd '\r' | wc -c | tr -d ' ')"
  if [ "$st" = "A" ]; then base_cr=0; else base_cr="$(git cat-file -p "$MB:$path" 2>/dev/null | tr -cd '\r' | wc -c | tr -d ' ')"; fi
  [ "${head_cr:-0}" -gt "${base_cr:-0}" ] && crbad+=("$path: carriage returns $base_cr -> $head_cr")
done < "$TMP/changed.txt"
if [ ${#crbad[@]} -eq 0 ]; then pass "line-endings"; else fail "line-endings" "${crbad[@]}"; fi

# python -------------------------------------------------------------------------------------
PY=""
if [ -n "${PORT_CHECK_PYTHON:-}" ]; then PYCANDS=("$PORT_CHECK_PYTHON"); else PYCANDS=(python3 python); fi
for c in "${PYCANDS[@]}"; do
  if "$c" -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then PY="$c"; break; fi
done
pyfiles="$(awk -F'\t' '$1 != "D" && $2 ~ /\.py$/ {print $2}' "$TMP/changed.txt")"
if [ -z "$pyfiles" ]; then
  pass "python (no Python files changed)"
elif [ -z "$PY" ]; then
  skip "python" "no Python 3.8 or newer found, so the Python 3.9 grammar was NOT checked"
else
  pybad=()
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    out="$(git cat-file -p "HEAD:$f" | "$PY" -I -c 'import ast, sys
src = sys.stdin.buffer.read()
try:
    ast.parse(src, feature_version=(3, 9))
except SyntaxError as e:
    print("line %s: %s" % (e.lineno, e.msg)); sys.exit(1)' 2>&1)" || pybad+=("$f: $out")
  done <<< "$pyfiles"
  if [ ${#pybad[@]} -eq 0 ]; then pass "python (Python 3.9 grammar, $(echo "$pyfiles" | wc -l | tr -d ' ') file(s))"; else fail "python" "${pybad[@]}"; fi
fi

# shell --------------------------------------------------------------------------------------
shbad=(); shn=0
while IFS=$'\t' read -r st path; do
  [ "$st" = "D" ] && continue
  isr=0
  case "$path" in *.sh) isr=1 ;; esac
  if [ $isr -eq 0 ]; then git cat-file -p "HEAD:$path" 2>/dev/null | head -n1 | grep -qE '^#!.*\b(ba)?sh\b' && isr=1; fi
  [ $isr -eq 1 ] || continue
  shn=$((shn + 1))
  git cat-file -p "HEAD:$path" > "$TMP/sh_check.sh"
  out="$(bash -n "$TMP/sh_check.sh" 2>&1)" || shbad+=("$path: $out")
done < "$TMP/changed.txt"
if [ $shn -eq 0 ]; then pass "shell (no shell scripts changed)"
elif [ ${#shbad[@]} -eq 0 ]; then pass "shell (bash -n, $shn file(s))"
else fail "shell" "${shbad[@]}"; fi

# ols-guard ----------------------------------------------------------------------------------
olsbad=()
while IFS= read -r l; do olsbad+=("$l"); done < <(grep -Ei 'autoSSL|acmeEmail|httpd_config|lsws/bin/|installCustomOLSBinaries|cyberpanel\.net/openlitespeed' "$TMP/added.txt" | cut -c1-200)
# (the action and hold-back words are looked for in the line text only, never in the file name)
while IFS= read -r l; do
  txt="${l#*:}"; txt="${txt#*:}"
  if printf '%s\n' "$txt" | grep -Eiq "$OLS_ACTION" && ! printf '%s\n' "$txt" | grep -Eiq "$OLS_HOLD"; then olsbad+=("$(printf '%s' "$l" | cut -c1-200)"); fi
done < <(grep -Ei 'openlitespeed' "$TMP/added.txt" | grep -Eiv 'autoSSL|acmeEmail|httpd_config|lsws/bin/|installCustomOLSBinaries|cyberpanel\.net/openlitespeed')
if [ ${#olsbad[@]} -eq 0 ]; then pass "ols-guard"; else fail "ols-guard" "${olsbad[@]}"; fi

# paid-addons --------------------------------------------------------------------------------
paidbad=()
while IFS= read -r l; do paidbad+=("$l"); done < <(grep -Ei "$PAID" "$TMP/added.txt" | cut -c1-200)
if [ ${#paidbad[@]} -eq 0 ]; then pass "paid-addons"; else fail "paid-addons" "${paidbad[@]}"; fi

# secrets (the matching text is never printed) -----------------------------------------------
secbad=()
while IFS= read -r l; do secbad+=("${l%%:*}:$(echo "$l" | cut -d: -f2): matches a secret pattern (text not shown)"); done < <(grep -E 'BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|discord(app)?\.com/api/webhooks/|hooks\.slack\.com/services/' "$TMP/added.txt")
if [ ${#secbad[@]} -eq 0 ]; then pass "secrets"; else fail "secrets" "${secbad[@]}"; fi

echo "----"
echo "passed: $PASSES   failed: $FAILS   skipped: $SKIPS"
[ $SKIPS -gt 0 ] && echo "NOTE: a SKIP is not a pass. The skipped check did not run."
[ $FAILS -eq 0 ] || exit 1
exit 0
