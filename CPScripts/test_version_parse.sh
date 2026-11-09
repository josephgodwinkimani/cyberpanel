#!/usr/bin/env bash
# test_version_parse.sh: tests the Parse_Panel_Version helper of cyberpanel_upgrade.sh and autoCyberpanel_upgrade.sh.
# The real helper (between "# BEGIN version parse" and "# END version parse") is extracted and run over a set of
# version.txt values. Nothing outside the temp folder is touched. Run: bash CPScripts/test_version_parse.sh

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
SCRIPTS=("$REPO/cyberpanel_upgrade.sh" "$REPO/autoCyberpanel_upgrade.sh")
ROOT="$(mktemp -d)" || exit 2
trap 'rm -rf "$ROOT"' EXIT
TOTAL=0; OK=0
ok()  { TOTAL=$((TOTAL + 1)); OK=$((OK + 1)); echo "ok    $1"; }
nok() { TOTAL=$((TOTAL + 1)); echo "NOT OK $1"; [ -n "${2:-}" ] && echo "$2" | sed 's/^/        /'; }

for s in "${SCRIPTS[@]}"; do [ -f "$s" ] || { echo "missing $s"; exit 2; }; done
sed -n '/^# BEGIN version parse$/,/^# END version parse$/p' "${SCRIPTS[0]}" > "$ROOT/block1.sh"
sed -n '/^# BEGIN version parse$/,/^# END version parse$/p' "${SCRIPTS[1]}" > "$ROOT/block2.sh"
[ -s "$ROOT/block1.sh" ] || { echo "could not extract the helper"; exit 2; }

# parse VALUE: prints "rc|version|build" for the helper applied to VALUE
parse() {
  VALUE="$1" bash -c 'source "'"$ROOT"'/block1.sh"; Parse_Panel_Version "$VALUE"; echo "$?|$Panel_Version|$Panel_Build"'
}
# the old slicing, for comparison
slice() {
  VALUE="$1" bash -c 'Temp_Value="$VALUE"; echo "${Temp_Value:12:3}|${Temp_Value:25:1}"'
}
expect() { # name value want
  got="$(parse "$2")"
  if [ "$got" = "$3" ]; then ok "$1"; else nok "$1" "value: $2
wanted: $3
got:    $got"; fi
}

if diff -q "$ROOT/block1.sh" "$ROOT/block2.sh" > /dev/null; then ok "the helper is identical in both upgrade scripts"; else nok "the helper is identical in both upgrade scripts"; fi

CURRENT='{"version":"2.3","build":9}'
expect "the current value gives 2.3 and 9" "$CURRENT" "0|2.3|9"
check_same="$(slice "$CURRENT")"
if [ "$check_same" = "2.3|9" ]; then ok "the old slicing gives the same fields for the current value"; else nok "the old slicing gives the same fields for the current value" "$check_same"; fi

expect "build 10 is read in full" '{"version":"2.3","build":10}' "0|2.3|10"
check_old="$(slice '{"version":"2.3","build":10}')"
if [ "$check_old" = "2.3|1" ]; then ok "the old slicing read build 10 as 1 (the defect)"; else nok "the old slicing read build 10 as 1 (the defect)" "$check_old"; fi
expect "build 123 is read in full" '{"version":"2.3","build":123}' "0|2.3|123"
expect "a two digit minor version is read in full" '{"version":"2.10","build":1}' "0|2.10|1"
expect "spaces around the colons are accepted" '{"version": "2.3", "build": 9}' "0|2.3|9"
expect "a quoted build number is accepted" '{"version":"2.3","build":"9"}' "0|2.3|9"
expect "key order does not matter" '{"build":9,"version":"2.3"}' "0|2.3|9"
expect "a trailing newline is harmless" "$(printf '{"version":"2.3","build":9}\n')" "0|2.3|9"

expect "an empty value is rejected" '' "1||"
expect "an HTML error page is rejected" '<html><body>404 Not Found</body></html>' "1||"
expect "a missing build is rejected" '{"version":"2.3"}' "1|2.3|"
expect "a missing version is rejected" '{"build":9}' "1||9"
expect "a non numeric build is rejected" '{"version":"2.3","build":"x"}' "1|2.3|"
expect "a version with letters is rejected" '{"version":"v2.3","build":9}' "1||9"
expect "a three part version is rejected" '{"version":"2.3.1","build":9}' "1|2.3.1|9"
expect "a version without a dot is rejected" '{"version":"23","build":9}' "1|23|9"

# a value that carries shell metacharacters is only read, never executed
marker="$ROOT/should-not-exist"
expect "shell metacharacters in the value are inert" '{"version":"2.3$(touch '"$marker"')","build":9}' "1||9"
[ ! -e "$marker" ] && ok "nothing was executed from the value" || nok "nothing was executed from the value"

# static checks on both scripts
for s in "${SCRIPTS[@]}"; do
  b="$(basename "$s")"
  [ "$(grep -cE 'Temp_Value:(12:3|25:1)' "$s")" = "0" ] && ok "$b no longer slices version.txt by position" || nok "$b no longer slices version.txt by position"
  [ "$(grep -c '^if ! Parse_Panel_Version "\$Temp_Value"; then$' "$s")" = "1" ] && ok "$b stops when the version is not valid" || nok "$b stops when the version is not valid"
  p="$(grep -n '^Parse_Panel_Version() {$' "$s" | cut -d: -f1)"; u="$(grep -n 'Parse_Panel_Version "\$Temp_Value"' "$s" | cut -d: -f1)"; w="$(grep -n '^Branch_Name="v\${Panel_Version}.\${Panel_Build}"$' "$s" | cut -d: -f1)"
  if [ -n "$p" ] && [ -n "$u" ] && [ -n "$w" ] && [ "$p" -lt "$u" ] && [ "$u" -lt "$w" ]; then ok "$b defines the helper, then checks the value, then builds the branch name"; else nok "$b order" "helper=$p check=$u branch=$w"; fi
  bash -n "$s" && ok "$b passes bash -n" || nok "$b passes bash -n"
  [ "$(tr -cd '\r' < "$s" | wc -c | tr -d ' ')" = "0" ] && ok "$b has no carriage returns" || nok "$b has no carriage returns"
done

echo "----"
echo "$OK of $TOTAL checks passed"
[ "$OK" = "$TOTAL" ] || exit 1
exit 0
