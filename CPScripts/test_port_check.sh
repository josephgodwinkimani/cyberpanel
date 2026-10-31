#!/usr/bin/env bash
# test_port_check.sh: tests CPScripts/port_check.sh against throwaway git repositories.
# It builds a temp repository, makes one deliberately bad change per case and checks the exit code
# and the report. Nothing outside the temp folder is read or written. Run: bash CPScripts/test_port_check.sh

HERE="$(cd "$(dirname "$0")" && pwd)"
CHECK="$HERE/port_check.sh"
[ -f "$CHECK" ] || { echo "port_check.sh not found next to this test"; exit 2; }

ROOT="$(mktemp -d)" || exit 2
trap 'rm -rf "$ROOT"' EXIT
REPO="$ROOT/repo"
TOTAL=0; OK=0

ok()   { TOTAL=$((TOTAL + 1)); OK=$((OK + 1)); echo "ok    $1"; }
nok()  { TOTAL=$((TOTAL + 1)); echo "NOT OK $1"; [ -n "${2:-}" ] && echo "$2" | sed 's/^/        /'; }

mkdir -p "$REPO" && cd "$REPO" || exit 2
git init -q . && git config user.name "Test Developer" && git config user.email "dev@example.invalid"
git config core.autocrlf false && git config core.safecrlf false
git checkout -q -b base
printf 'import os\n\n\ndef f(x):\n    return os.path.join(x, "a")\n' > a.py
printf '#!/bin/bash\necho hello\n' > b.sh
printf 'plain text\nsecond line\n' > c.txt
printf 'old\n' > old.txt
git add -A && git commit -q -m "base"

# run NAME EXPECTED_EXIT PATTERN [env assignments...]: runs the checker on the current branch and compares
run() {
  local name="$1" want="$2" pat="$3"; shift 3
  local out rc
  out="$(env "$@" bash "$CHECK" --base base 2>&1)"; rc=$?
  if [ "$rc" = "$want" ] && echo "$out" | grep -Eq -- "$pat"; then ok "$name"; else nok "$name (exit $rc, wanted $want, pattern: $pat)" "$out"; fi
}
# branch_from_base: start a fresh feature branch from base
branch() { git checkout -q -B "${1:-feat}" base; }
commit() { git add -A && git commit -q -m "${1:-change}"; }

# 1 clean change passes everything
branch; printf 'import sys\n\n\ndef g():\n    return sys.version\n' >> a.py; printf 'echo two\n' >> b.sh; commit "Add a function"
run "clean change passes" 0 'failed: 0'

# 2 empty diff
branch
run "empty diff reports nothing to check" 0 'nothing to check'

# 3 bad base ref
branch; printf 'x\n' >> c.txt; commit
out="$(bash "$CHECK" --base no-such-ref 2>&1)"; rc=$?
if [ "$rc" = 2 ]; then ok "unknown base ref exits 2"; else nok "unknown base ref exits 2 (exit $rc)" "$out"; fi

# 4 python syntax error
branch; printf 'def broken(:\n    pass\n' > bad.py; commit
run "python syntax error fails" 1 'FAIL  python'

# 5 python newer than 3.9 grammar (match statement)
branch; printf 'def h(x):\n    match x:\n        case 1:\n            return 1\n    return 0\n' > new.py; commit
run "python 3.10 grammar fails the 3.9 check" 1 'FAIL  python'

# 6 shell syntax error
branch; printf '#!/bin/bash\nif [ 1 = 1 ]; then\necho x\n' > broken.sh; commit
run "shell syntax error fails" 1 'FAIL  shell'

# 7 shell script found by its shebang
branch; printf '#!/bin/bash\nif [ 1 = 1 ]; then\necho x\n' > tool; commit
run "shell script without .sh is found by its shebang" 1 'FAIL  shell'

# 8 OLS guard: autoSSL
branch; printf 'echo "autoSSL 1" >> /usr/local/lsws/conf/x\n' >> b.sh; commit
run "ols-guard blocks autoSSL" 1 'FAIL  ols-guard'

# 9 OLS guard: httpd_config
branch; printf 'sed -i s/a/b/ /usr/local/lsws/conf/httpd_config.conf\n' >> b.sh; commit
run "ols-guard blocks httpd_config" 1 'FAIL  ols-guard'

# 10 OLS guard: lsws/bin
branch; printf 'cp new /usr/local/lsws/bin/openlitespeed\n' >> b.sh; commit
run "ols-guard blocks lsws/bin and an openlitespeed copy" 1 'FAIL  ols-guard'

# 11 OLS guard: a line naming openlitespeed without a hold-back word
branch; printf 'dnf install -y openlitespeed\n' >> b.sh; commit
run "ols-guard blocks installing openlitespeed" 1 'FAIL  ols-guard'

# 12 OLS guard: a hold-back line passes
branch; printf "dnf update -y --exclude='openlitespeed*'\n" >> b.sh; commit
run "ols-guard allows an exclude line" 0 'PASS  ols-guard'

# 12b lines that only name openlitespeed to protect or list it pass (taken from real lines of the fork)
branch
printf '%s\n' 'for P in "crowdsec*" "openlitespeed*" "mariadb*"; do echo "$P"; done' \
  'echo -e "Running the update (OpenLiteSpeed packages are held back)..."' \
  "dpkg-query -W -f='\${Package}\\n' 'openlitespeed' 'mariadb*'" >> b.sh
commit
run "ols-guard allows hold-back lists, held-back messages and dpkg-query" 0 'PASS  ols-guard'

# 12b2 an action word in the FILE NAME must not count (the real test file is called test_system_update_policy.sh)
branch; printf '%s\n' "for P in 'openlitespeed*' 'mariadb*'; do echo \"\$P\"; done" > test_system_update_policy.sh; commit
run "ols-guard ignores action words in the file name" 0 'PASS  ols-guard'

# 12c a download of an openlitespeed package is blocked
branch; printf 'wget https://example.invalid/openlitespeed-1.0.tgz\n' >> b.sh; commit
run "ols-guard blocks downloading openlitespeed" 1 'FAIL  ols-guard'

# 12d rpm -U of an openlitespeed package is blocked
branch; printf 'rpm -U /tmp/openlitespeed.rpm\n' >> b.sh; commit
run "ols-guard blocks rpm -U of openlitespeed" 1 'FAIL  ols-guard'

# 13 paid add-on term
branch; printf 'RSPAMD_ENABLE=1\n' >> c.txt; commit
run "paid-addons blocks a paid add-on name" 1 'FAIL  paid-addons'

# 13b more paid add-on spellings
branch; printf 'plogical/Backupsv2.py\n' >> c.txt; commit
run "paid-addons blocks Backupsv2" 1 'FAIL  paid-addons'
branch; printf 'url(OneClickBackups)\n' >> c.txt; commit
run "paid-addons blocks OneClickBackups" 1 'FAIL  paid-addons'

# 13c the licence service and the add-on store
branch; printf 'ACLManager.CheckForPremFeature("all")\n' >> a.py; commit
run "licence-calls blocks CheckForPremFeature" 1 'FAIL  licence-calls'
branch; printf 'url = "https://example.invalid/CyberpanelAdOns/Adonpermission"\n' >> a.py; commit
run "licence-calls blocks the Adonpermission endpoint" 1 'FAIL  licence-calls'
branch; printf 'requests.post("https://platform.cyberpersons.com/servers/RecvData")\n' >> a.py; commit
run "licence-calls blocks the platform host" 1 'FAIL  licence-calls'
branch; printf 'redirect("https://cyberpanel.net/cyberpanel-addons")\n' >> a.py; commit
run "licence-calls blocks the add-on store redirect" 1 'FAIL  licence-calls'
branch; printf 'ADONPERMISSION = 1\n' >> c.txt; commit
run "licence-calls ignores letter case" 1 'FAIL  licence-calls'
branch; printf 'see https://cyberpanel.net/KnowledgeBase/home/upgrading-cyberpanel/\nlicence text and premium words are fine\n' >> c.txt; commit
run "licence-calls and paid-addons leave other cyberpanel.net links and plain words alone" 0 'PASS  licence-calls'
git checkout -q -B removal base; printf 'CheckForPremFeature\nplatform.cyberpersons.com\n' > gone.txt; git add -A; git commit -q -m "base2"; git branch -f base2 HEAD
git checkout -q -B remove-it base2; git rm -q gone.txt; commit "Remove the markers"
out="$(bash "$CHECK" --base base2 2>&1)"; rc=$?
if [ "$rc" = 0 ] && echo "$out" | grep -q 'PASS  licence-calls'; then ok "licence-calls allows a change that only removes the markers"; else nok "licence-calls allows a change that only removes the markers (exit $rc)" "$out"; fi

# 14 secrets: token prefix (built at run time so this file holds no token)
branch; printf 'TOKEN=ghp_%s\n' "$(printf 'a%.0s' $(seq 1 25))" >> c.txt; commit
out="$(bash "$CHECK" --base base 2>&1)"; rc=$?
if [ "$rc" = 1 ] && echo "$out" | grep -q 'FAIL  secrets' && ! echo "$out" | grep -q 'ghp_a'; then ok "secrets fails and never prints the value"; else nok "secrets fails and never prints the value (exit $rc)" "$out"; fi

# 15 secrets: webhook URL
branch; printf 'URL=https://discord.com/api/webhooks/123/abc\n' >> c.txt; commit
run "secrets blocks a webhook URL" 1 'FAIL  secrets'

# 16 stray .bak file
branch; printf 'x\n' > a.py.bak; commit
run "stray-files blocks a .bak file" 1 'FAIL  stray-files'

# 17 mode change on an existing file
branch; git update-index --chmod=+x b.sh; git commit -q -m "mode"
run "modes blocks a mode change" 1 'FAIL  modes'

# 18 new symlink
branch; blob="$(printf 'a.py' | git hash-object -w --stdin)"; git update-index --add --cacheinfo "120000,$blob,link"; git commit -q -m "link"
run "modes blocks a new symlink" 1 'FAIL  modes'

# 19 new executable file is reported but allowed
branch; printf '#!/bin/bash\necho new\n' > new.sh; git add new.sh; git update-index --chmod=+x new.sh; git commit -q -m "new script"
run "new executable file passes and is reported" 0 'INFO new executable file'

# 20 carriage returns added to an existing file
branch; printf 'third\r\nfourth\r\n' >> c.txt; commit
run "line-endings blocks added carriage returns" 1 'FAIL  line-endings'

# 21 a new file with carriage returns
branch; printf 'one\r\n' > crlf.txt; commit
run "line-endings blocks a new CRLF file" 1 'FAIL  line-endings'

# 22 existing CRLF content is not blamed when the change adds none
git checkout -q -B crlfbase base; printf 'keep\r\ncr\r\n' > legacy.txt; git add -A; git commit -q -m "legacy crlf"
git checkout -q -B feat crlfbase; printf 'new line\n' > other.txt; git add -A; git commit -q -m "other"
out="$(bash "$CHECK" --base crlfbase 2>&1)"; rc=$?
if [ "$rc" = 0 ] && echo "$out" | grep -q 'PASS  line-endings'; then ok "line-endings does not blame untouched CRLF files"; else nok "line-endings does not blame untouched CRLF files (exit $rc)" "$out"; fi

# 23 co-author trailer
branch; printf 'x\n' >> c.txt; git add -A; git commit -q -m "change" -m "Co-Authored-By: Someone <someone@example.invalid>"
run "commit-rules blocks a co-author trailer" 1 'FAIL  commit-rules'

# 24 Generated with line
branch; printf 'x\n' >> c.txt; git add -A; git commit -q -m "change" -m "Generated with a tool"
run "commit-rules blocks a Generated with line" 1 'FAIL  commit-rules'

# 24b a footer that starts with a symbol before the words is still caught
branch; printf 'x\n' >> c.txt; git add -A; git commit -q -m "change" -m "$(printf '\360\237\244\226') Generated with a tool"
run "commit-rules blocks a Generated with footer that follows a symbol" 1 'FAIL  commit-rules'

# 24c prose that mentions the words is allowed
branch; printf 'x\n' >> c.txt; git add -A; git commit -q -m "Describe the rule" -m "The check rejects a Co-Authored-By trailer and a Generated with footer in a message."
run "commit-rules allows prose that mentions the words" 0 'PASS  commit-rules'

# 25 em dash in a commit message
branch; printf 'x\n' >> c.txt; git add -A; git commit -q -m "change $(printf '\342\200\224') text"
run "commit-rules blocks an em dash" 1 'FAIL  commit-rules'

# 26 AI author identity
branch; printf 'x\n' >> c.txt; git add -A; GIT_AUTHOR_EMAIL="noreply@anthropic.com" git commit -q -m "change"
run "commit-rules blocks an AI author" 1 'FAIL  commit-rules'

# 27 production branch name
git checkout -q -B v2.3.9 base; printf 'x\n' >> c.txt; commit
run "branch blocks HEAD on v2.3.9" 1 'FAIL  branch'

# 28 deleting a file is fine
branch; git rm -q old.txt; git commit -q -m "remove"
run "deleting a file passes" 0 'failed: 0'

# 29 this script and its test are not blamed for the patterns they name
branch; mkdir -p CPScripts; printf '# autoSSL acmeEmail httpd_config rspamd\n' > CPScripts/port_check.sh; commit
run "the checker's own files are excluded from content checks" 0 'failed: 0'

# 30 no Python available: SKIP, not PASS
branch; printf 'import os\n' > ok.py; commit
run "missing Python gives SKIP and is not a pass" 0 'SKIP  python' PORT_CHECK_PYTHON=/no/such/python

# 31 the checker changes nothing
branch; printf 'import os\n' > ok2.py; commit
before="$( (git status --porcelain; git rev-parse HEAD; git for-each-ref; find . -path ./.git -prune -o -type f -print | sort | xargs -r md5sum 2>/dev/null) | md5sum)"
bash "$CHECK" --base base >/dev/null 2>&1
after="$( (git status --porcelain; git rev-parse HEAD; git for-each-ref; find . -path ./.git -prune -o -type f -print | sort | xargs -r md5sum 2>/dev/null) | md5sum)"
if [ "$before" = "$after" ]; then ok "the checker leaves the repository unchanged"; else nok "the checker leaves the repository unchanged"; fi

echo "----"
echo "$OK of $TOTAL checks passed"
[ "$OK" = "$TOTAL" ] || exit 1
exit 0
