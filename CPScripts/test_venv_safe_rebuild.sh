#!/usr/bin/env bash
# test_venv_safe_rebuild.sh: tests the venv safety block of cyberpanel_upgrade.sh and autoCyberpanel_upgrade.sh.
# It extracts the real functions (between "# BEGIN venv safety" and "# END venv safety") and the real
# Check_Return, and runs them against throwaway directory trees under a temp folder. Nothing outside the temp
# folder is read or written and no panel or server path is used. Run: bash CPScripts/test_venv_safe_rebuild.sh

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
SCRIPTS=("$REPO/cyberpanel_upgrade.sh" "$REPO/autoCyberpanel_upgrade.sh")
ROOT="$(mktemp -d)" || exit 2
trap 'rm -rf "$ROOT"' EXIT
TOTAL=0; OK=0
ok()  { TOTAL=$((TOTAL + 1)); OK=$((OK + 1)); echo "ok    $1"; }
nok() { TOTAL=$((TOTAL + 1)); echo "NOT OK $1"; [ -n "${2:-}" ] && echo "$2" | sed 's/^/        /'; }
SKIPPED=0
skip() { SKIPPED=$((SKIPPED + 1)); echo "SKIP  $1 (not counted as a pass)"; }
mkdir "$ROOT/symtarget"; probe="$ROOT/symprobe"; ln -s symtarget "$probe" 2> /dev/null; if [ -L "$probe" ]; then SYMLINKS=1; else SYMLINKS=0; fi; rm -rf "$probe" "$ROOT/symtarget"
check() { if [ "$2" = "$3" ]; then ok "$1"; else nok "$1" "wanted: $3
got:    $2"; fi; }

for s in "${SCRIPTS[@]}"; do [ -f "$s" ] || { echo "missing $s"; exit 2; }; done
BLOCK="$ROOT/block.sh"
sed -n '/^# BEGIN venv safety$/,/^# END venv safety$/p' "${SCRIPTS[0]}" > "$BLOCK"
sed -n '/^# BEGIN venv safety$/,/^# END venv safety$/p' "${SCRIPTS[1]}" > "$ROOT/block2.sh"
sed -n '/^Check_Return() {/,/^}/p' "${SCRIPTS[0]}" > "$ROOT/checkreturn.sh"
[ -s "$BLOCK" ] && [ -s "$ROOT/checkreturn.sh" ] || { echo "could not extract the functions"; exit 2; }

T="$ROOT/tree"
HASH() { md5sum | cut -d' ' -f1; }
snap() { (cd "$1" && { find . | LC_ALL=C sort; find . -type f | LC_ALL=C sort | while read -r f; do md5sum "$f"; done; find . -type l | LC_ALL=C sort | while read -r l; do echo "$l -> $(readlink "$l")"; done; } | HASH); }

mk() {
  rm -rf "$T"
  mkdir -p "$T/CyberPanel/bin" "$T/CyberPanel/lib/site" "$T/CyberCP/bin" "$T/CyberCP/lib/site" "$T/CyberCP/share" "$T/CyberCP/websiteFunctions"
  printf '#!/bin/sh\nexit 0\n' > "$T/CyberPanel/bin/python"; chmod +x "$T/CyberPanel/bin/python"
  printf '#!/bin/sh\nexit 0\n' > "$T/CyberCP/bin/python"; chmod +x "$T/CyberCP/bin/python"
  printf '#!/bin/sh
echo old-binary
' > "$T/CyberCP/bin/lswsgi"; chmod +x "$T/CyberCP/bin/lswsgi"
  echo old-module > "$T/CyberPanel/lib/site/mod.py"; echo old-module > "$T/CyberCP/lib/site/mod.py"
  echo old-cfg > "$T/CyberPanel/pyvenv.cfg"; echo old-cfg > "$T/CyberCP/pyvenv.cfg"
  ln -s lib "$T/CyberPanel/lib64"; ln -s lib "$T/CyberCP/lib64"
  echo app > "$T/CyberCP/manage.py"; echo code > "$T/CyberCP/websiteFunctions/x.py"; echo shared > "$T/CyberCP/share/s.txt"
}

# scenario BODY-FILE: runs a scenario in its own bash (own traps, own exit status) with the real functions loaded
run() {
  { echo 'source "'"$BLOCK"'"'; echo 'Debug_Log2() { :; }'; echo 'source "'"$ROOT"'/checkreturn.sh"'; echo 'T="'"$T"'"'; cat; } > "$ROOT/sc.sh"
  bash "$ROOT/sc.sh" 2>&1
}

# 1 identical block in both scripts
if diff -q "$BLOCK" "$ROOT/block2.sh" > /dev/null; then ok "the venv safety block is identical in both upgrade scripts"; else nok "the venv safety block is identical in both upgrade scripts"; fi

# 2 move aside, parts
mk; BEFORE_APP="$(snap "$T/CyberCP/websiteFunctions")"
out="$(printf '%s\n' 'Venv_Move_Aside "$T/CyberCP" bin lib lib64 pyvenv.cfg; echo "rc=$?"; echo "pending=${#Venv_Pending[@]}"; Venv_Commit > /dev/null' | run)"
echo "$out" | grep -q 'rc=0' && echo "$out" | grep -q 'pending=1' && ok "move aside (parts) returns 0 and records one pending entry" || nok "move aside (parts)" "$out"
BK="$(ls -d "$T"/CyberCP-venv-backup-* 2>/dev/null | head -1)"
if [ -n "$BK" ] && [ ! -e "$T/CyberCP/bin" ] && [ ! -e "$T/CyberCP/lib" ] && [ ! -e "$T/CyberCP/pyvenv.cfg" ] && [ -f "$BK/bin/lswsgi" ] && [ -f "$BK/lib/site/mod.py" ] && [ -f "$BK/pyvenv.cfg" ]; then ok "the four venv parts are in the backup folder and gone from the panel folder"; else nok "the four venv parts are in the backup folder"; fi
if [ "$SYMLINKS" = 1 ]; then [ -L "$BK/lib64" ] && ok "the lib64 symlink is preserved in the backup" || nok "the lib64 symlink is preserved in the backup"; else skip "the lib64 symlink is preserved in the backup (this shell cannot create symlinks)"; fi
if [ -f "$T/CyberCP/manage.py" ] && [ -f "$T/CyberCP/share/s.txt" ] && [ "$(snap "$T/CyberCP/websiteFunctions")" = "$BEFORE_APP" ]; then ok "application files and share/ are untouched"; else nok "application files and share/ are untouched"; fi

# 3 move aside, whole directory
mk
out="$(printf '%s\n' 'Venv_Move_Aside "$T/CyberPanel"; echo "rc=$?"; Venv_Commit > /dev/null' | run)"
BK="$(ls -d "$T"/CyberPanel.upgrade-backup-* 2>/dev/null | head -1)"
if echo "$out" | grep -q 'rc=0' && [ -n "$BK" ] && [ ! -e "$T/CyberPanel" ] && [ -f "$BK/lib/site/mod.py" ] && [ -x "$BK/bin/python" ]; then ok "move aside (whole) renames the directory and keeps its content"; else nok "move aside (whole)" "$out"; fi

# 4 a missing path is not an error and records nothing
mk; rm -rf "$T/CyberPanel"
out="$(printf '%s\n' 'Venv_Move_Aside "$T/CyberPanel"; echo "rc=$? pending=${#Venv_Pending[@]}"' | run)"
echo "$out" | grep -q 'rc=0 pending=0' && ok "nothing to move aside: returns 0 and records nothing" || nok "nothing to move aside" "$out"

# 5 failure after the move: the exit trap restores both environments byte for byte, whatever the exit status
mk; B1="$(snap "$T")"
out="$(run <<'EOS'
Venv_Move_Aside "$T/CyberPanel"
Venv_Move_Aside "$T/CyberCP" bin lib lib64 pyvenv.cfg
# the rebuild starts and leaves partial new environments behind
mkdir -p "$T/CyberPanel/bin" "$T/CyberCP/bin" "$T/CyberCP/lib"
echo half-built > "$T/CyberCP/bin/new-file"; echo half-built > "$T/CyberPanel/bin/new-file"
ls /no/such/path 2> /dev/null
Check_Return "rebuilding the environments"
echo "NOT REACHED"
EOS
)"; rc=$?
check "Check_Return ends the script with a non-zero status after a failure" "$([ "$rc" -ne 0 ] && echo yes || echo no)" "yes"
echo "$out" | grep -q 'NOT REACHED' && nok "Check_Return stopped the flow" || ok "Check_Return stopped the flow"
check "after a failed rebuild both environments are restored byte for byte" "$(snap "$T")" "$B1"
if ls "$T"/CyberPanel.upgrade-backup-* "$T"/CyberCP-venv-backup-* > /dev/null 2>&1; then nok "the empty backup folders are cleaned up after a restore"; else ok "the empty backup folders are cleaned up after a restore"; fi

# 6 success: confirmed rebuild keeps the new environment and keeps the old copies
mk
out="$(run <<'EOS'
Venv_Move_Aside "$T/CyberPanel"
Venv_Move_Aside "$T/CyberCP" bin lib lib64 pyvenv.cfg
mkdir -p "$T/CyberPanel/bin" "$T/CyberCP/bin" "$T/CyberCP/lib"
printf '#!/bin/sh\nexit 0\n' > "$T/CyberCP/bin/python"; chmod +x "$T/CyberCP/bin/python"
printf '#!/bin/sh
echo new-binary
' > "$T/CyberCP/bin/lswsgi"; chmod +x "$T/CyberCP/bin/lswsgi"
Venv_Validate_Panel_Runtime "$T/CyberCP" && Venv_Commit
echo "pending=${#Venv_Pending[@]}"
EOS
)"
echo "$out" | grep -q 'pending=0' && ok "Venv_Commit clears the pending list" || nok "Venv_Commit clears the pending list" "$out"
if grep -q new-binary "$T/CyberCP/bin/lswsgi" && [ -f "$(ls -d "$T"/CyberCP-venv-backup-*)/lib/site/mod.py" ] && [ -f "$(ls -d "$T"/CyberPanel.upgrade-backup-*)/lib/site/mod.py" ]; then ok "after a confirmed rebuild the new environment stays and both old copies are kept"; else nok "after a confirmed rebuild the new environment stays and both old copies are kept"; fi
echo "$out" | grep -q 'Previous Python environment kept at' && ok "the kept copies are listed in the output" || nok "the kept copies are listed in the output" "$out"

# 7 validation failures
mk
for missing in "bin/python" "bin/lswsgi"; do
  rm -f "$T/CyberCP/$missing"
  out="$(printf '%s\n' 'Venv_Validate_Panel_Runtime "$T/CyberCP"; echo "rc=$?"' | run)"
  echo "$out" | grep -q 'rc=1' && ok "validation fails when $missing is missing" || nok "validation fails when $missing is missing" "$out"
  mk
done
printf '#!/bin/sh\nexit 1\n' > "$T/CyberCP/bin/python"; chmod +x "$T/CyberCP/bin/python"
out="$(printf '%s\n' 'Venv_Validate_Panel_Runtime "$T/CyberCP"; echo "rc=$?"' | run)"
echo "$out" | grep -q 'rc=1' && ok "validation fails when django cannot be imported" || nok "validation fails when django cannot be imported" "$out"
mk
out="$(printf '%s\n' 'Venv_Validate_Panel_Runtime "$T/CyberCP"; echo "rc=$?"' | run)"
echo "$out" | grep -q 'rc=0' && ok "validation passes for a complete runtime" || nok "validation passes for a complete runtime" "$out"

# 8 a failed validation inside the flow restores the previous environments
mk; B1="$(snap "$T")"
run <<'EOS' > /dev/null
Venv_Move_Aside "$T/CyberPanel"
Venv_Move_Aside "$T/CyberCP" bin lib lib64 pyvenv.cfg
mkdir -p "$T/CyberCP/bin"; printf '#!/bin/sh\nexit 0\n' > "$T/CyberCP/bin/python"; chmod +x "$T/CyberCP/bin/python"
Venv_Validate_Panel_Runtime "$T/CyberCP"
Check_Return "the rebuilt panel runtime did not pass validation"
Venv_Commit
EOS
check "a rebuild with no lswsgi is rolled back and the previous panel runtime returns" "$(snap "$T")" "$B1"

# 9 termination while the rebuild runs
mk; B1="$(snap "$T")"
{ echo 'source "'"$BLOCK"'"'; echo 'T="'"$T"'"'; cat <<'EOS'
Venv_Move_Aside "$T/CyberCP" bin lib lib64 pyvenv.cfg
mkdir -p "$T/CyberCP/bin"; echo half > "$T/CyberCP/bin/x"
echo READY
sleep 30 &
wait $!
EOS
} > "$ROOT/sc_term.sh"
bash "$ROOT/sc_term.sh" > "$ROOT/term.out" 2>&1 &
PID=$!
for i in $(seq 1 100); do grep -q READY "$ROOT/term.out" 2> /dev/null && break; sleep 0.2; done
kill -TERM "$PID" 2> /dev/null; wait "$PID" 2> /dev/null
sleep 1
pkill -f "sleep 30" 2> /dev/null
check "a terminated upgrade restores the previous environment" "$(snap "$T")" "$B1"

# 10 a failing mv in the middle of a multi-part move puts the first parts back
mk; B1="$(snap "$T")"
out="$(run <<'EOS'
mv() { if [[ "${*: -1}" == */lib64 ]]; then return 1; fi; command mv "$@"; }
Venv_Move_Aside "$T/CyberCP" bin lib lib64 pyvenv.cfg
echo "rc=$? pending=${#Venv_Pending[@]}"
EOS
)"
echo "$out" | grep -q 'rc=1 pending=0' && ok "a failed move returns 1 and records nothing" || nok "a failed move returns 1 and records nothing" "$out"
check "a failed multi-part move leaves the environment exactly as it was" "$(snap "$T")" "$B1"

# 11 unsafe paths are refused and nothing is touched
mk; B1="$(snap "$T")"
out="$(run <<'EOS'
for p in "" "/" "/usr" "$T/CyberCP/../CyberCP" "$T/CyberCP/." "relative/path"; do
  Venv_Move_Aside "$p" bin; echo "rc=$?"
done
EOS
)"
n="$(echo "$out" | grep -c 'rc=1')"
check "six unsafe paths are all refused" "$n" "6"
check "refused paths leave the tree untouched" "$(snap "$T")" "$B1"

# 12 a tampered pending entry is refused by the restore and removes nothing
mk; B1="$(snap "$T")"
out="$(run <<'EOS'
Venv_Pending=("parts|$T/CyberCP/../CyberCP|$T/CyberCP-venv-backup-x|bin lib")
Venv_Restore_Pending
echo "rc=$?"
EOS
)"
echo "$out" | grep -q 'rc=1' && ok "the restore refuses an entry with dot segments" || nok "the restore refuses an entry with dot segments" "$out"
check "the refused restore removes nothing" "$(snap "$T")" "$B1"

# 13 names in the restore are limited to the recorded parts: an extra entry in the panel folder survives
mk
run <<'EOS' > /dev/null
Venv_Move_Aside "$T/CyberCP" bin lib lib64 pyvenv.cfg
echo keep > "$T/CyberCP/not-a-venv-part.txt"
exit 0
EOS
[ -f "$T/CyberCP/not-a-venv-part.txt" ] && [ -f "$T/CyberCP/manage.py" ] && ok "the restore touches only the recorded venv parts" || nok "the restore touches only the recorded venv parts"

# 14 static checks on both scripts
for s in "${SCRIPTS[@]}"; do
  b="$(basename "$s")"
  if grep -nE '^[[:space:]]*rm -rf +/usr/local/CyberPanel$|^rm -rf +/usr/local/CyberCP/(bin|lib|lib64|pyvenv\.cfg)$' "$s" > /dev/null; then nok "$b has no direct deletion of the two venvs"; else ok "$b has no direct deletion of the two venvs"; fi
  check "$b moves the venvs aside in three places" "$(grep -cE '^[[:space:]]*Venv_Move_Aside /usr/local/Cyber' "$s")" "3"
  check "$b checks the result of every move" "$(grep -cE '^[[:space:]]*Check_Return "moving the previous Python environment' "$s")" "3"
  v="$(grep -nE '^Venv_Validate_Panel_Runtime /usr/local/CyberCP$' "$s" | cut -d: -f1)"
  c="$(grep -nE '^Venv_Commit$' "$s" | cut -d: -f1)"
  l="$(grep -nE '^cp lswsgi /usr/local/CyberCP/bin/$' "$s" | cut -d: -f1)"
  if [ -n "$v" ] && [ -n "$c" ] && [ -n "$l" ] && [ "$l" -lt "$v" ] && [ "$v" -lt "$c" ]; then ok "$b confirms the rebuild only after lswsgi is copied and validated"; else nok "$b confirms the rebuild only after lswsgi is copied and validated" "lswsgi=$l validate=$v commit=$c"; fi
  bash -n "$s" && ok "$b passes bash -n" || nok "$b passes bash -n"
  check "$b has no carriage returns" "$(tr -cd '\r' < "$s" | wc -c | tr -d ' ')" "0"
  # the exit trap must be installed after the earlier apt-hold trap (if any) is cleared, so the order is checked
  t="$(grep -nE '^\s*trap - EXIT INT TERM' "$s" | head -1 | cut -d: -f1)"; m="$(grep -nE '^\s*Venv_Move_Aside /usr/local/CyberPanel' "$s" | head -1 | cut -d: -f1)"
  if [ -z "$t" ] || [ "$t" -lt "$m" ]; then ok "$b installs the venv exit trap after any earlier trap is cleared"; else nok "$b installs the venv exit trap after any earlier trap is cleared"; fi
done

echo "----"
echo "$OK of $TOTAL checks passed, $SKIPPED skipped"
[ "$OK" = "$TOTAL" ] || exit 1
exit 0
