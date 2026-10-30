#!/bin/bash
# php2shell_check.sh - READ-ONLY exposure check for PHP2Shell (CVE-2026-109618 / CVE-2026-109619) on CyberPanel + LiteSpeed.
#
# Usage: bash php2shell_check.sh
#
# Reports, per installed lsphp: package, version line, build date (and whether it predates the fix release), the
# effective session.upload_progress.enabled value, which vhosts use it, whether the control panel's PHP copy is stale,
# and whether running workers are older than the installed binary. It writes nothing and changes nothing.
#
# The build date is a HEURISTIC: a binary built before the fix release cannot contain the fix, but a newer date does not
# prove the fix is present (vendors may re-package). Compare package releases with your vendor's advisory.
#
# Test overrides: LSWS_ROOT (/usr/local/lsws), LSCP_ROOT (/usr/local/lscp), FIX_DATE (2026-10-21).

set -u

LSWS_ROOT=${LSWS_ROOT:-/usr/local/lsws}
LSCP_ROOT=${LSCP_ROOT:-/usr/local/lscp}
FIX_DATE=${FIX_DATE:-2026-10-21}

REVIEW=0
note()   { echo "  $*"; }
review() { echo "  REVIEW: $*"; REVIEW=$((REVIEW + 1)); }

fix_epoch=$(date -d "$FIX_DATE" +%s 2>/dev/null || echo 0)

echo "== lsphp builds under $LSWS_ROOT (fix released $FIX_DATE)"
for dir in "$LSWS_ROOT"/lsphp*; do
  [ -d "$dir" ] || continue
  b="$dir/bin/lsphp"
  [ -x "$b" ] || continue
  name=$(basename "$dir")
  vline=$("$b" -v 2>/dev/null | head -1)
  pkg=$(rpm -qf "$b" 2>/dev/null | head -1)
  [ -n "$pkg" ] || pkg=$(dpkg -S "$b" 2>/dev/null | head -1)
  echo "$name: ${pkg:-no package} | ${vline:-version unknown}"

  built=$(echo "$vline" | sed -n 's/.*(built: \([^)]*\)).*/\1/p')
  built_epoch=$(date -d "$built" +%s 2>/dev/null || echo 0)
  if [ "$built_epoch" -gt 0 ] && [ "$fix_epoch" -gt 0 ]; then
    if [ "$built_epoch" -lt "$fix_epoch" ]; then
      review "$name was built $built, before the fix release: it cannot contain the fix"
    else
      note "built $built (after the fix release; compare the package release with your vendor's advisory)"
    fi
  else
    note "build date not readable"
  fi

  cgi="$dir/bin/php-cgi"
  if [ -x "$cgi" ]; then
    up=$("$cgi" -i 2>/dev/null | sed -n 's/^session\.upload_progress\.enabled => \([^ ]*\) .*/\1/p' | head -1)
    case "${up:-}" in
      Off|0|"") [ -n "${up:-}" ] && note "session.upload_progress.enabled = $up" || note "session.upload_progress.enabled not readable" ;;
      *)        review "$name session.upload_progress.enabled = $up (interim mitigation not applied)" ;;
    esac
  fi
done

echo "== vhost -> lsphp handler"
grep -H -E '^[[:space:]]*path[[:space:]].*lsphp' "$LSWS_ROOT"/conf/vhosts/*/vhost.conf 2>/dev/null \
  | sed -E "s#$LSWS_ROOT/conf/vhosts/##; s#/vhost.conf:[[:space:]]*path[[:space:]]+# -> #" || note "no vhost configuration found"

echo "== control panel PHP copy"
panel="$LSCP_ROOT/fcgi-bin/lsphp"
src="$LSWS_ROOT/lsphp80/bin/lsphp"
if [ -x "$panel" ]; then
  echo "panel: $("$panel" -v 2>/dev/null | head -1)"
  if [ -x "$src" ] && ! cmp -s "$panel" "$src"; then
    review "$panel differs from $src (the installer copies it once; package updates do not reach it)"
  else
    note "matches $src"
  fi
else
  note "$panel not found"
fi

echo "== running workers"
now=$(date +%s)
for pid in $(pgrep -x lsphp 2>/dev/null); do
  exe=$(readlink "/proc/$pid/exe" 2>/dev/null)
  [ -n "$exe" ] || continue
  case "$exe" in
    *"(deleted)") review "worker $pid runs a replaced binary ($exe): restart lsphp"; continue ;;
  esac
  et=$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d ' ')
  mt=$(stat -c %Y "$exe" 2>/dev/null)
  if [ -n "$et" ] && [ -n "$mt" ] && [ $((now - et)) -lt "$mt" ]; then
    review "worker $pid started before $exe was last modified: restart lsphp"
  fi
done
note "checked $(pgrep -x lsphp 2>/dev/null | wc -l) worker(s)"

echo "== result"
if [ "$REVIEW" -eq 0 ]; then
  echo "no items to review"
else
  echo "$REVIEW item(s) to review"
fi
exit 0
