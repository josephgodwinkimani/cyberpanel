#!/bin/bash
# test_prerequisite_package_policy.sh - tests for the prerequisite package handling in cyberpanel_upgrade.sh,
# autoCyberpanel_upgrade.sh and plogical/upgrade.py: only missing packages are installed (an install of an installed
# package upgrades it), gf-release is never fetched from the parked ghettoforge.org domain, the LiteSpeed repository file
# is replaced only when it is missing, and the unguarded lsphp83 and quota installs are guarded.
# Everything runs against fake rpm, dnf, yum and curl programs in a temporary folder: nothing is installed or changed.
#
# Usage: bash CPScripts/test_prerequisite_package_policy.sh   (prints PASS or FAIL for every check)

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
mkdir -p "$BIN"
LOG="$TMP/calls.log"
# rpm: -q --whatprovides NAME succeeds only for the names in $FAKE_INSTALLED (space separated)
cat > "$BIN/rpm" <<'EOF'
#!/bin/bash
echo "rpm $*" >> "$FAKE_LOG"
name=${@: -1}
for p in $FAKE_INSTALLED; do [ "$p" = "$name" ] && exit 0; done
exit 1
EOF
cat > "$BIN/dnf" <<'EOF'
#!/bin/bash
echo "dnf $*" >> "$FAKE_LOG"
exit "${FAKE_DNF_RC:-0}"
EOF
cp "$BIN/dnf" "$BIN/yum"
# curl -o FILE URL: writes $FAKE_CURL_BODY to FILE, exits with $FAKE_CURL_RC
cat > "$BIN/curl" <<'EOF'
#!/bin/bash
echo "curl $*" >> "$FAKE_LOG"
out=""
while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out=$2; shift; done
[ -n "$out" ] && printf '%b' "${FAKE_CURL_BODY:-}" > "$out"
exit "${FAKE_CURL_RC:-0}"
EOF
chmod +x "$BIN"/*

block() { sed -n '/^# BEGIN system package policy/,/^# END system package policy/p;/^# BEGIN prerequisite package policy/,/^# END prerequisite package policy/p' "$REPO/$1"; }
prelude='Debug_Log2() { :; }; Yum_Exclude=(); Server_Country=""'
run() {  # run <script> <body>
  : > "$LOG"
  ( export FAKE_LOG="$LOG" PATH="$BIN:$PATH"; bash -c "$prelude
$(block "$1")
$2" 2>&1 )
}

for S in cyberpanel_upgrade.sh autoCyberpanel_upgrade.sh; do
  echo "== $S"
  # everything installed: nothing is installed, so nothing can be upgraded
  OUT=$(FAKE_INSTALLED="wget curl git gcc" run "$S" 'Install_Missing_Packages wget curl git gcc; echo "rc=$?"')
  contains "$S all installed: nothing to install" "$OUT" "nothing to install"
  contains "$S all installed: returns 0" "$OUT" "rc=0"
  lacks "$S all installed: no install call" "$(cat "$LOG")" "install"
  # one missing: only that package is passed on
  OUT=$(FAKE_INSTALLED="wget curl git" run "$S" 'Install_Missing_Packages wget curl git mariadb-connector-c-devel; echo "rc=$?"')
  contains "$S one missing: installs it" "$(cat "$LOG")" "dnf install -y --skip-broken mariadb-connector-c-devel"
  lacks "$S one missing: does not name installed packages" "$(grep 'dnf install' "$LOG")" "wget"
  lacks "$S one missing: does not name installed packages (git)" "$(grep 'dnf install' "$LOG")" "git"
  # install fails: warns and carries on, as the script did before
  OUT=$(FAKE_INSTALLED="" FAKE_DNF_RC=1 run "$S" 'Install_Missing_Packages foo; echo "rc=$?"')
  contains "$S install failure: warns" "$OUT" "WARNING: could not install: foo"
  contains "$S install failure: upgrade continues" "$OUT" "rc=0"

  # gf-release
  OUT=$(FAKE_INSTALLED="gf-release" run "$S" 'Gf_Release_Setup el9; echo "rc=$?"')
  contains "$S gf-release installed: left alone" "$OUT" "already installed"
  lacks "$S gf-release installed: no dnf call" "$(cat "$LOG")" "dnf"
  OUT=$(FAKE_INSTALLED="" run "$S" 'Gf_Release_Setup el9')
  contains "$S gf-release missing: uses ghettoforge.net" "$(cat "$LOG")" "https://mirror.ghettoforge.net/distributions/gf/gf-release-latest.gf.el9.noarch.rpm"
  lacks "$S gf-release missing: never ghettoforge.org" "$(cat "$LOG")" "ghettoforge.org"
  OUT=$(FAKE_INSTALLED="" run "$S" 'Server_Country=CN; Gf_Release_Setup el8')
  contains "$S gf-release CN: CyberPanel mirror" "$(cat "$LOG")" "https://cyberpanel.sh/mirror.ghettoforge.org/distributions/gf/gf-release-latest.gf.el8.noarch.rpm"

  # LiteSpeed repository file
  R="$TMP/litespeed.repo"
  printf '[litespeed]\nname=x\nbaseurl=http://rpms.litespeedtech.com/centos/$releasever/$basearch/\n' > "$R"
  OUT=$(CP_LITESPEED_REPO_FILE="$R" run "$S" 'Litespeed_Repo_Setup; echo "rc=$?"')
  contains "$S repo file present: left as it is" "$OUT" "leaving it as it is"
  lacks "$S repo file present: no download" "$(cat "$LOG")" "curl"
  check "$S repo file present: unchanged" "$(head -c 12 "$R")" "[litespeed]"
  rm -f "$R"
  OUT=$(CP_LITESPEED_REPO_FILE="$R" FAKE_CURL_BODY='[litespeed]\nname=new\n' run "$S" 'Litespeed_Repo_Setup; echo "rc=$?"')
  contains "$S repo file missing: downloaded" "$OUT" "rc=0"
  contains "$S repo file missing: content installed" "$(cat "$R" 2> /dev/null)" "[litespeed]"
  rm -f "$R"
  OUT=$(CP_LITESPEED_REPO_FILE="$R" FAKE_CURL_BODY='<html>parked</html>' run "$S" 'Litespeed_Repo_Setup; echo "NOT-REACHED"')
  contains "$S repo download is not a repo file: error" "$OUT" "Could not download the LiteSpeed repository file"
  lacks "$S repo download is not a repo file: stops" "$OUT" "NOT-REACHED"
  check "$S repo download is not a repo file: nothing written" "$(ls "$R" 2> /dev/null)" ""
  OUT=$(CP_LITESPEED_REPO_FILE="$R" FAKE_CURL_RC=22 run "$S" 'Litespeed_Repo_Setup; echo "NOT-REACHED"')
  contains "$S repo download fails: error" "$OUT" "Could not download the LiteSpeed repository file"
  printf 'old definition\n' > "$R"
  OUT=$(CP_LITESPEED_REPO_FILE="$R" FAKE_CURL_BODY='<html></html>' run "$S" 'Litespeed_Repo_Setup; echo "NOT-REACHED"')
  check "$S broken old file kept when the download is bad" "$(cat "$R")" "old definition"
  rm -f "$R"
done

echo "== static checks"
for S in cyberpanel_upgrade.sh autoCyberpanel_upgrade.sh; do
  bash -n "$REPO/$S" && ok "$S passes bash -n" || bad "$S fails bash -n"
  BODY=$(awk '/BEGIN (system|prerequisite) package policy/{skip=1} !skip{print} /END (system|prerequisite) package policy/{skip=0}' "$REPO/$S" | grep -v '^\s*#')
  check "$S: no raw dnf/yum install of the prerequisite lists" "$(echo "$BODY" | grep -c -E '^\s*(dnf|yum) install -y wget strace')" "0"
  check "$S: no raw dnf install of epel-release, gpgme-devel or python3" "$(echo "$BODY" | grep -c -E '^\s*dnf install (epel-release|gpgme-devel|python3) -y')" "0"
  check "$S: no download from the parked ghettoforge.org domain" "$(echo "$BODY" | grep -c 'https://mirror.ghettoforge.org')" "0"
  check "$S: five Ubuntu installs use --no-upgrade" "$(echo "$BODY" | grep -c -E 'apt install -y --no-upgrade ')" "5"
  check "$S: no Ubuntu install without --no-upgrade in the pre-upgrade section" "$(echo "$BODY" | grep -c -E 'DEBIAN_FRONTEND=noninterac[a-z]+ apt install -y [^-]')" "0"
  # the EPEL removal must sit inside the System_Update guard
  GUARDED=$(echo "$BODY" | awk '/if \[\[ "\$System_Update" = "1" \]\] ; then/{g=1} g&&/autoremove epel-release/{c++} /^  fi$/{g=0} END{print c+0}')
  check "$S: both EPEL autoremove lines are behind the switch" "$GUARDED" "2"
  check "$S: no litespeed.repo download outside the helper" "$(echo "$BODY" | grep -c 'curl -o /etc/yum.repos.d/litespeed.repo')" "0"
done
A=$(block cyberpanel_upgrade.sh | grep -v '^export CP_UPGRADE_SYSTEM_PACKAGES')
B=$(block autoCyberpanel_upgrade.sh | grep -v '^export CP_UPGRADE_SYSTEM_PACKAGES')
check "both scripts carry the same policy blocks" "$A" "$B"

echo "== plogical/upgrade.py"
PYOUT=$(python3 -I - "$REPO/plogical/upgrade.py" "$BIN" <<'EOF'
import ast, os, subprocess, sys
src = open(sys.argv[1]).read()
binpath = sys.argv[2]
tree = ast.parse(src)
cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Upgrade'][0]
methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}

# package_installed against the fake rpm (nothing installed) and a fake rpm that knows "quota"
node = methods['package_installed']
node.decorator_list = []
class _Shell:
    """upgrade.py runs on Linux where shell=True means /bin/sh. Run it through bash here so that the fake rpm is found
    on any system (on Windows shell=True would use cmd.exe)."""
    DEVNULL = subprocess.DEVNULL

    @staticmethod
    def call(command, shell=True, **kwargs):
        return subprocess.call(['bash', '-c', command], **kwargs)

ns = {'subprocess': _Shell}
exec(compile(ast.Module([node], []), 'upgrade.py', 'exec'), ns)
os.environ['PATH'] = binpath + os.pathsep + os.environ['PATH']
os.environ['FAKE_LOG'] = os.devnull
os.environ['FAKE_INSTALLED'] = 'quota'
print('quota installed', ns['package_installed']('quota'))
print('other installed', ns['package_installed']('definitely-not-installed'))

def under(method, needle, test_fragment, negate=False):
    """True when every string constant starting with `needle` in `method` sits under an If whose test contains test_fragment."""
    parents = {}
    for parent in ast.walk(methods[method]):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    found = guarded = 0
    for n in ast.walk(methods[method]):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith(needle):
            found += 1
            cur = n
            while cur in parents:
                cur = parents[cur]
                if isinstance(cur, ast.If) and test_fragment in ast.unparse(cur.test):
                    guarded += 1
                    break
    return found, guarded

print('lsphp83 install', under('installPHP73', 'yum install lsphp83', "installedOutput.find('lsphp83') == -1"))
print('quota rpm install', under('installQuota', 'yum install quota', "not Upgrade.package_installed('quota')"))
print('quota apt install', under('installQuota', 'apt install quota', "not Upgrade.package_installed('quota')"))
EOF
)
contains "python: package_installed is true for an installed package" "$PYOUT" "quota installed True"
contains "python: package_installed is false for a missing package" "$PYOUT" "other installed False"
contains "python: lsphp83 install is guarded" "$PYOUT" "lsphp83 install (1, 1)"
contains "python: quota rpm install is guarded" "$PYOUT" "quota rpm install (1, 1)"
contains "python: quota apt install is guarded" "$PYOUT" "quota apt install (1, 1)"
python3 -I -c "import sys; compile(open(sys.argv[1]).read(), 'upgrade.py', 'exec')" "$REPO/plogical/upgrade.py" 2> /dev/null && ok "upgrade.py compiles" || bad "upgrade.py does not compile"

echo
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]
