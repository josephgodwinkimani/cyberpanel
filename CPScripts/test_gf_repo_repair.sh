#!/bin/bash
# test_gf_repo_repair.sh - tests for Gf_Repo_Repair in cyberpanel_upgrade.sh and autoCyberpanel_upgrade.sh: an installed
# gf-release whose repository file points its mirror list at the parked ghettoforge.org domain is repaired (the host becomes
# ghettoforge.net, a copy of the file is made first), and every other repository file is left exactly as it is.
# The real function is cut out of each script. Everything runs against fake files, rpm, dnf and cp programs in a temporary
# folder: nothing is installed and no real repository file is read or changed.
#
# Usage: bash CPScripts/test_gf_repo_repair.sh   (prints PASS or FAIL for every check)

set -u
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
PASS=0
FAIL=0

ok()   { PASS=$((PASS + 1)); echo "PASS: $1"; }
bad()  { FAIL=$((FAIL + 1)); echo "FAIL: $1"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected '$3', got '$2')"; fi; }
contains() { case "$2" in *"$3"*) ok "$1" ;; *) bad "$1 (missing '$3' in: $2)" ;; esac; }
lacks()    { case "$2" in *"$3"*) bad "$1 (found '$3' in: $2)" ;; *) ok "$1" ;; esac; }

BIN="$TMP/bin"
FAILBIN="$TMP/failbin"
mkdir -p "$BIN" "$FAILBIN"
LOG="$TMP/calls.log"
# rpm -q gf-release succeeds only when $FAKE_INSTALLED lists it
cat > "$BIN/rpm" <<'EOF'
#!/bin/bash
echo "rpm $*" >> "$FAKE_LOG"
for p in $FAKE_INSTALLED; do [ "$p" = "${@: -1}" ] && exit 0; done
exit 1
EOF
cat > "$BIN/dnf" <<'EOF'
#!/bin/bash
echo "dnf $*" >> "$FAKE_LOG"
exit 0
EOF
printf '#!/bin/bash\nexit 1\n' > "$FAILBIN/cp"
chmod +x "$BIN"/* "$FAILBIN"/*

block() { sed -n '/^# BEGIN prerequisite package policy/,/^# END prerequisite package policy/p' "$REPO/$1"; }
run() {  # run <script> <body>
  : > "$LOG"
  ( export FAKE_LOG="$LOG" PATH="${EXTRA_PATH:-}$BIN:$PATH"; bash -c "Debug_Log2() { :; }; Yum_Exclude=(); Server_Country=\"\"
$(block "$1")
$2" 2>&1 )
}

DEAD='[gf]
name=Gf Repository for Enterprise Linux 9 - $basearch
mirrorlist=http://mirrorlist.ghettoforge.org/el/9/gf/$basearch/mirrorlist
#baseurl=http://mirror.ghettoforge.org/distributions/gf/el/9/gf/$basearch/
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-gf.el9

[gf-plus]
name=Gf Plus Repository for Enterprise Linux 9 - $basearch
mirrorlist=http://mirrorlist.ghettoforge.org/el/9/plus/$basearch/mirrorlist
enabled=0
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-gf.el9
'

for S in cyberpanel_upgrade.sh autoCyberpanel_upgrade.sh; do
  echo "== $S"
  R="$TMP/gf.repo"
  rm -f "$TMP"/gf.repo*

  # a dead file is repaired
  printf '%s' "$DEAD" > "$R"
  chmod 644 "$R"
  OUT=$(FAKE_INSTALLED="gf-release" CP_GF_REPO_FILE="$R" run "$S" 'Gf_Release_Setup el9; echo "rc=$?"')
  contains "$S dead file: reports the repair" "$OUT" "now uses ghettoforge.net"
  contains "$S dead file: returns 0" "$OUT" "rc=0"
  lacks "$S dead file: does not say it left the files alone" "$OUT" "leaving the GhettoForge repository files alone"
  check "$S dead file: both mirror lists moved to the new host over https" "$(grep -c '^mirrorlist=https://mirrorlist.ghettoforge.net/el/9/' "$R")" "2"
  contains "$S dead file: path and basearch kept" "$(cat "$R")" 'mirrorlist=https://mirrorlist.ghettoforge.net/el/9/gf/$basearch/mirrorlist'
  contains "$S dead file: plus repository path kept" "$(cat "$R")" 'mirrorlist=https://mirrorlist.ghettoforge.net/el/9/plus/$basearch/mirrorlist'
  lacks "$S dead file: no active old mirror list left" "$(grep '^mirrorlist' "$R")" "ghettoforge.org"
  contains "$S dead file: the commented baseurl line is not touched" "$(cat "$R")" '#baseurl=http://mirror.ghettoforge.org/distributions/gf/el/9/gf/$basearch/'
  check "$S dead file: only the two mirror list lines changed" "$(diff <(printf '%s' "$DEAD") "$R" | grep -c '^>')" "2"
  check "$S dead file: file mode kept" "$(stat -c %a "$R")" "644"
  BK=$(ls "$TMP"/gf.repo.before-ghettoforge-net.* 2> /dev/null | head -1)
  check "$S dead file: exactly one copy was made" "$(ls "$TMP"/gf.repo.before-ghettoforge-net.* 2> /dev/null | wc -l | tr -d ' ')" "1"
  check "$S dead file: the copy holds the old content byte for byte" "$(cmp -s <(printf '%s' "$DEAD") "$BK" && echo same)" "same"
  case "$BK" in *.repo) bad "$S dead file: the copy must not end in .repo (dnf would read it)" ;; *) ok "$S dead file: the copy does not end in .repo" ;; esac
  lacks "$S dead file: no dnf call" "$(cat "$LOG")" "dnf"

  # a second run has nothing to do and makes no second copy
  OUT=$(FAKE_INSTALLED="gf-release" CP_GF_REPO_FILE="$R" run "$S" 'Gf_Release_Setup el9')
  contains "$S second run: leaves the files alone" "$OUT" "leaving the GhettoForge repository files alone"
  check "$S second run: still one copy" "$(ls "$TMP"/gf.repo.before-ghettoforge-net.* | wc -l | tr -d ' ')" "1"

  # the https spelling of the old host is repaired as well
  rm -f "$TMP"/gf.repo*
  printf '%s' "${DEAD//http:\/\/mirrorlist/https://mirrorlist}" > "$R"
  OUT=$(FAKE_INSTALLED="gf-release" CP_GF_REPO_FILE="$R" run "$S" 'Gf_Repo_Repair; echo "rc=$?"')
  check "$S https spelling of the old host: repaired" "$(grep -c '^mirrorlist=https://mirrorlist.ghettoforge.net/' "$R")" "2"

  # a file that already uses the new host is not touched and gets no copy
  rm -f "$TMP"/gf.repo*
  printf '%s' "${DEAD//mirrorlist.ghettoforge.org/mirrorlist.ghettoforge.net}" > "$R"
  BEFORE=$(cksum < "$R")
  OUT=$(FAKE_INSTALLED="gf-release" CP_GF_REPO_FILE="$R" run "$S" 'Gf_Release_Setup el9')
  contains "$S healthy file: left alone" "$OUT" "leaving the GhettoForge repository files alone"
  check "$S healthy file: unchanged" "$(cksum < "$R")" "$BEFORE"
  check "$S healthy file: no copy" "$(ls "$TMP"/gf.repo.before-* 2> /dev/null | wc -l | tr -d ' ')" "0"

  # a customised file without the old mirror list is not touched
  rm -f "$TMP"/gf.repo*
  printf '[gf]\nname=local mirror\nbaseurl=http://repo.example.internal/gf/el9/\nenabled=1\n' > "$R"
  BEFORE=$(cksum < "$R")
  OUT=$(FAKE_INSTALLED="gf-release" CP_GF_REPO_FILE="$R" run "$S" 'Gf_Release_Setup el9')
  check "$S customised file: unchanged" "$(cksum < "$R")" "$BEFORE"
  check "$S customised file: no copy" "$(ls "$TMP"/gf.repo.before-* 2> /dev/null | wc -l | tr -d ' ')" "0"

  # a commented out old mirror list is not an active line and is not touched
  rm -f "$TMP"/gf.repo*
  printf '[gf]\n#mirrorlist=http://mirrorlist.ghettoforge.org/el/9/gf/$basearch/mirrorlist\nbaseurl=http://repo.example.internal/gf/el9/\nenabled=1\n' > "$R"
  BEFORE=$(cksum < "$R")
  OUT=$(FAKE_INSTALLED="gf-release" CP_GF_REPO_FILE="$R" run "$S" 'Gf_Release_Setup el9')
  check "$S commented old line: unchanged" "$(cksum < "$R")" "$BEFORE"
  check "$S commented old line: no copy" "$(ls "$TMP"/gf.repo.before-* 2> /dev/null | wc -l | tr -d ' ')" "0"

  # no repository file at all
  rm -f "$TMP"/gf.repo*
  OUT=$(FAKE_INSTALLED="gf-release" CP_GF_REPO_FILE="$R" run "$S" 'Gf_Release_Setup el9; echo "rc=$?"')
  contains "$S no file: leaves the files alone" "$OUT" "leaving the GhettoForge repository files alone"
  contains "$S no file: returns 0" "$OUT" "rc=0"
  check "$S no file: nothing was created" "$(ls "$TMP"/gf.repo* 2> /dev/null | wc -l | tr -d ' ')" "0"

  # the copy cannot be made: the file stays as it was and the upgrade carries on
  rm -f "$TMP"/gf.repo*
  printf '%s' "$DEAD" > "$R"
  OUT=$(EXTRA_PATH="$FAILBIN:" FAKE_INSTALLED="gf-release" CP_GF_REPO_FILE="$R" run "$S" 'Gf_Release_Setup el9; echo "rc=$?"')
  contains "$S copy fails: warns" "$OUT" "WARNING: could not make a copy"
  contains "$S copy fails: the upgrade carries on (rc 0)" "$OUT" "rc=0"
  check "$S copy fails: file unchanged" "$(cmp -s <(printf '%s' "$DEAD") "$R" && echo same)" "same"

  # gf-release not installed: the repair is not used, the release package is installed as before
  rm -f "$TMP"/gf.repo*
  printf '%s' "$DEAD" > "$R"
  OUT=$(FAKE_INSTALLED="" CP_GF_REPO_FILE="$R" run "$S" 'Gf_Release_Setup el9')
  contains "$S gf-release missing: installs it from the new host" "$(cat "$LOG")" "https://mirror.ghettoforge.net/distributions/gf/gf-release-latest.gf.el9.noarch.rpm"
  check "$S gf-release missing: the file is not edited by the repair" "$(cmp -s <(printf '%s' "$DEAD") "$R" && echo same)" "same"
done

echo "== both scripts"
check "the function is identical in both scripts" "$(diff <(sed -n '/^Gf_Repo_Repair() {/,/^}/p' "$REPO/cyberpanel_upgrade.sh") <(sed -n '/^Gf_Repo_Repair() {/,/^}/p' "$REPO/autoCyberpanel_upgrade.sh") | wc -l | tr -d ' ')" "0"
for S in cyberpanel_upgrade.sh autoCyberpanel_upgrade.sh; do
  bash -n "$REPO/$S" 2> /dev/null && ok "$S passes bash -n" || bad "$S passes bash -n"
  check "$S has no carriage returns" "$(tr -cd '\r' < "$REPO/$S" | wc -c | tr -d ' ')" "0"
  # the repair has to run before the first package install that follows each gf-release step, or dnf aborts first
  while read -r L; do
    NEXT=$(awk -v s="$L" 'NR > s && /Install_Missing_Packages|dnf |yum install/ {print NR; exit}' "$REPO/$S")
    [ -n "$NEXT" ] && [ "$NEXT" -gt "$L" ] && ok "$S line $L: Gf_Release_Setup runs before the next package install (line $NEXT)" || bad "$S line $L: Gf_Release_Setup is not before the next package install"
  done < <(grep -n '^  Gf_Release_Setup el' "$REPO/$S" | cut -d: -f1)
done
check "the existing prerequisite policy test never reads a real repository file" "$(grep -c '^export CP_GF_REPO_FILE=' "$REPO/CPScripts/test_prerequisite_package_policy.sh")" "1"

echo
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]
