#!/bin/bash
# test_system_update_policy.sh - tests for the system package policy in cyberpanel_upgrade.sh, autoCyberpanel_upgrade.sh
# and plogical/upgrade.py. Everything runs against fake dnf, yum, apt-get, apt-mark and dpkg-query programs in a temporary
# folder: no package is installed, updated or removed and nothing outside the temporary folder is written.
#
# Usage: bash CPScripts/test_system_update_policy.sh   (from any folder, prints PASS or FAIL for every check)

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

# ---- fake package tools -------------------------------------------------------------------------------------------
BIN="$TMP/bin"
mkdir -p "$BIN"
LOG="$TMP/calls.log"
cat > "$BIN/dnf" <<'EOF'
#!/bin/bash
echo "dnf $*" >> "$FAKE_LOG"
case "$1" in
  check-update) exit "${FAKE_CHECK_RC:-100}" ;;
  update)       exit "${FAKE_UPDATE_RC:-0}" ;;
esac
exit 0
EOF
cp "$BIN/dnf" "$BIN/yum"
cat > "$BIN/apt-get" <<'EOF'
#!/bin/bash
echo "apt-get $*" >> "$FAKE_LOG"
exit "${FAKE_APT_RC:-0}"
EOF
cat > "$BIN/apt-mark" <<'EOF'
#!/bin/bash
echo "apt-mark $*" >> "$FAKE_LOG"
[ "$1" = "showhold" ] && exit 0
exit 0
EOF
cat > "$BIN/dpkg-query" <<'EOF'
#!/bin/bash
# like dpkg-query -W -f='${db:Status-Abbrev} ${Package}\n' <patterns>: print only the packages that match a pattern
shift 2
for entry in "ii openlitespeed" "ii mariadb-server" "ii openssh-server" "ii linux-image-5.15" "ii curl" "rc crowdsec"; do
  name=${entry#* }
  for pattern in "$@"; do
    case "$name" in $pattern) echo "$entry"; break ;; esac
  done
done
EOF
chmod +x "$BIN"/*

# ---- pull the real code out of the scripts -----------------------------------------------------------------------
block() { sed -n '/^# BEGIN system package policy/,/^# END system package policy/p' "$REPO/$1"; }
func()  { sed -n "/^$2() {/,/^}/p" "$REPO/$1"; }

prelude='Debug_Log2() { :; }; Yum_Exclude=(); Server_Country=""; Branch_Check() { echo "BRANCH=$1"; }'

# run <script> <body>: source the real policy block and run a snippet with the fake tools first on PATH
run() {
  : > "$LOG"
  (
    export FAKE_LOG="$LOG" PATH="$BIN:$PATH"
    bash -c "$prelude
$(block "$1")
$2" 2>&1
  )
}

for S in cyberpanel_upgrade.sh autoCyberpanel_upgrade.sh; do
  echo "== $S"
  # default: the system update does not run
  OUT=$(run "$S" 'System_Package_Update; echo "rc=$?"')
  contains "$S default: update skipped" "$OUT" "System package update skipped"
  contains "$S default: returns 0" "$OUT" "rc=0"
  check "$S default: no package manager call" "$(cat "$LOG")" ""

  # opt in: repositories checked first, then updated, with every protection
  OUT=$(run "$S" 'System_Update=1; Yum_Exclude=(--exclude="crowdsec*"); System_Package_Update; echo "rc=$?"')
  contains "$S opt-in: runs" "$OUT" "rc=0"
  check "$S opt-in: check-update comes first" "$(sed -n 1p "$LOG" | cut -d' ' -f1-2)" "dnf check-update"
  UPD=$(grep '^dnf update' "$LOG")
  for P in 'crowdsec*' 'openlitespeed*' 'mariadb*' 'MariaDB*' 'openssh*' 'kernel*'; do
    contains "$S opt-in: holds back $P" "$UPD" "--exclude=$P"
  done

  # opt in with unreadable repositories: stops before changing anything
  OUT=$(FAKE_CHECK_RC=1 run "$S" 'System_Update=1; System_Package_Update; echo "NOT-REACHED"')
  contains "$S broken repo: error shown" "$OUT" "cannot be read"
  contains "$S broken repo: says nothing changed" "$OUT" "Nothing was changed"
  lacks "$S broken repo: stops" "$OUT" "NOT-REACHED"
  lacks "$S broken repo: no update call" "$(cat "$LOG")" "dnf update"

  # opt in, update fails: stops
  OUT=$(FAKE_UPDATE_RC=1 run "$S" 'System_Update=1; System_Package_Update; echo "NOT-REACHED"')
  contains "$S failed update: error shown" "$OUT" "system package update failed"
  lacks "$S failed update: stops" "$OUT" "NOT-REACHED"

  # Ubuntu: default skips, opt-in holds and releases the protected packages, also when the upgrade fails
  OUT=$(run "$S" 'Apt_System_Upgrade apt-get upgrade -y; echo "rc=$?"')
  contains "$S apt default: skipped" "$OUT" "System package update skipped"
  check "$S apt default: no apt call" "$(cat "$LOG")" ""
  OUT=$(run "$S" 'System_Update=1; Apt_System_Upgrade apt-get upgrade -y; echo "rc=$?"')
  contains "$S apt opt-in: runs" "$OUT" "rc=0"
  for P in openlitespeed mariadb-server openssh-server linux-image-5.15; do
    contains "$S apt opt-in: holds $P" "$(grep 'apt-mark hold' "$LOG")" "$P"
  done
  lacks "$S apt opt-in: does not hold a package outside the list" "$(grep 'apt-mark hold' "$LOG")" "curl"
  lacks "$S apt opt-in: does not hold a package that is not installed" "$(grep 'apt-mark hold' "$LOG")" "crowdsec"
  contains "$S apt opt-in: releases the holds" "$(grep 'apt-mark unhold' "$LOG")" "openlitespeed"
  OUT=$(FAKE_APT_RC=1 run "$S" 'System_Update=1; Apt_System_Upgrade apt-get upgrade -y; echo "NOT-REACHED"')
  contains "$S apt failed upgrade: error shown" "$OUT" "system package update failed"
  contains "$S apt failed upgrade: holds released anyway" "$(grep 'apt-mark unhold' "$LOG")" "mariadb-server"
done

echo "== argument handling and export"
ARGFN=$(func cyberpanel_upgrade.sh Check_Argument)
runarg() { (bash -c "$prelude
$(block cyberpanel_upgrade.sh)
$ARGFN
Check_Argument $1
echo \"System_Update=\$System_Update export=\$CP_UPGRADE_SYSTEM_PACKAGES\"" 2>&1); }
OUT=$(runarg "--branch 2.3.9 --update-system-packages")
contains "flag turns the update on" "$OUT" "System_Update=1 export=1"
contains "flag does not leak into the branch name" "$OUT" "BRANCH=2.3.9"
lacks "flag is not part of the branch name" "$OUT" "BRANCH=2.3.9 "
OUT=$(runarg "--branch 2.3.9")
contains "no flag: update off" "$OUT" "System_Update=0 export=0"
contains "no flag: branch unchanged" "$OUT" "BRANCH=2.3.9"
OUT=$(runarg "")
contains "no arguments: update off" "$OUT" "System_Update=0 export=0"
OUT=$(CP_UPGRADE_SYSTEM_PACKAGES=1 runarg "")
contains "environment variable turns it on" "$OUT" "System_Update=1 export=1"

echo "== the unattended script has no flag, only the environment"
OUT=$(bash -c "$prelude
$(block autoCyberpanel_upgrade.sh)
echo \"System_Update=\$System_Update export=\$CP_UPGRADE_SYSTEM_PACKAGES\"" 2>&1)
contains "unattended default: off and exported" "$OUT" "System_Update=0 export=0"
OUT=$(CP_UPGRADE_SYSTEM_PACKAGES=1 bash -c "$prelude
$(block autoCyberpanel_upgrade.sh)
echo \"System_Update=\$System_Update export=\$CP_UPGRADE_SYSTEM_PACKAGES\"" 2>&1)
contains "unattended with the variable: on" "$OUT" "System_Update=1 export=1"

echo "== static checks"
for S in cyberpanel_upgrade.sh autoCyberpanel_upgrade.sh; do
  bash -n "$REPO/$S" && ok "$S passes bash -n" || bad "$S fails bash -n"
  OUTSIDE=$(grep -v '^\s*#' "$REPO/$S" | awk '/BEGIN system package policy/{skip=1} !skip{print} /END system package policy/{skip=0}' | grep -n -E '(yum|dnf) (-y )?update|apt(-get)? .*upgrade -y' | grep -v -E 'System_Package_Update|Apt_System_Upgrade' || true)
  check "$S has no system update outside the policy functions" "$OUTSIDE" ""
done
A=$(block cyberpanel_upgrade.sh | grep -v '^export CP_UPGRADE_SYSTEM_PACKAGES')
B=$(block autoCyberpanel_upgrade.sh | grep -v '^export CP_UPGRADE_SYSTEM_PACKAGES')
check "both scripts carry the same policy block" "$A" "$B"

echo "== plogical/upgrade.py"
PYOUT=$(python3 -I - "$REPO/plogical/upgrade.py" <<'EOF'
import ast, os, sys
src = open(sys.argv[1]).read()
tree = ast.parse(src)
cls = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Upgrade'][0]
methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
ns = {'os': os}
for name in ('system_update_enabled', 'protected_exclude_option'):
    node = methods[name]
    node.decorator_list = []
    exec(compile(ast.Module([node], []), 'upgrade.py', 'exec'), ns)
os.environ.pop('CP_UPGRADE_SYSTEM_PACKAGES', None)
print('default', ns['system_update_enabled']())
os.environ['CP_UPGRADE_SYSTEM_PACKAGES'] = '1'
print('enabled', ns['system_update_enabled']())
os.environ['CP_UPGRADE_SYSTEM_PACKAGES'] = '0'
print('zero', ns['system_update_enabled']())
opt = ns['protected_exclude_option']()
for p in ('openlitespeed*', 'mariadb*', 'MariaDB*', 'openssh*', 'kernel*'):
    print('protects', p, p in opt)
# the yum update inside upgradeDovecot must sit under "if Upgrade.system_update_enabled():"
parents = {}
for parent in ast.walk(methods['upgradeDovecot']):
    for child in ast.iter_child_nodes(parent):
        parents[child] = parent
found = guarded = 0
for node in ast.walk(methods['upgradeDovecot']):
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith('yum update -y'):
        found += 1
        cur = node
        while cur in parents:
            cur = parents[cur]
            if isinstance(cur, ast.If) and 'system_update_enabled' in ast.dump(cur.test):
                guarded += 1
                break
print('yum update lines in upgradeDovecot', found, 'guarded', guarded)
EOF
)
contains "python: off by default" "$PYOUT" "default False"
contains "python: on when set to 1" "$PYOUT" "enabled True"
contains "python: 0 is off" "$PYOUT" "zero False"
for P in 'openlitespeed*' 'mariadb*' 'MariaDB*' 'openssh*' 'kernel*'; do contains "python: holds back $P" "$PYOUT" "protects $P True"; done
contains "python: upgradeDovecot update is behind the switch" "$PYOUT" "yum update lines in upgradeDovecot 1 guarded 1"
python3 -I -c "import sys; compile(open(sys.argv[1]).read(), 'upgrade.py', 'exec')" "$REPO/plogical/upgrade.py" 2> /dev/null && ok "upgrade.py compiles" || bad "upgrade.py does not compile"

echo
echo "passed=$PASS failed=$FAIL"
[ "$FAIL" -eq 0 ]
