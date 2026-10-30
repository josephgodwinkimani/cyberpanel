#!/bin/bash
# php2shell_mitigate.sh - PHP2Shell (CVE-2026-109618 / CVE-2026-109619) hardening for CyberPanel + LiteSpeed (lsphp) servers.
#
# Usage: bash php2shell_mitigate.sh [--update-lsphp 74,80] [--refresh-panel] [--restart] [--strict]
#
#   (always)               write a php.d drop-in that sets session.upload_progress.enabled = 0 for every installed lsphp.
#                          This is a PARTIAL mitigation (CVE-2026-109619 only). The fix is a patched lsphp package.
#   --update-lsphp 74,80   upgrade those lsphp branches from the configured package repository (dnf, yum or apt-get).
#   --refresh-panel        re-copy lsphp80's lsphp binary to /usr/local/lscp/fcgi-bin/lsphp (the installer copies it only
#                          once, so package updates never reach the control panel's PHP) and restart lscpd.
#   --restart              stop running lsphp workers so new packages and settings are used (they respawn on the next
#                          request; in-flight requests fail once).
#   --strict               exit 1 if any step reported a problem (default: always exit 0 so a caller such as the upgrade
#                          script is never aborted).
#
# Every step is idempotent. Test overrides: LSWS_ROOT (/usr/local/lsws), LSCP_ROOT (/usr/local/lscp),
# PANEL_SRC_BRANCH (80), PHP2SHELL_NO_SERVICE=1 (never restart services or kill workers).

set -u

LSWS_ROOT=${LSWS_ROOT:-/usr/local/lsws}
LSCP_ROOT=${LSCP_ROOT:-/usr/local/lscp}
PANEL_SRC_BRANCH=${PANEL_SRC_BRANCH:-80}
NO_SERVICE=${PHP2SHELL_NO_SERVICE:-0}

REFRESH=0; RESTART=0; STRICT=0; UPDATE=""; FAILS=0; PANEL_REFRESHED=0

log()  { echo "[php2shell] $*"; }
warn() { echo "[php2shell] WARNING: $*" >&2; FAILS=$((FAILS + 1)); }

while [ $# -gt 0 ]; do
  case "$1" in
    --refresh-panel) REFRESH=1 ;;
    --restart)       RESTART=1 ;;
    --strict)        STRICT=1 ;;
    --update-lsphp)  shift; UPDATE=${1:-} ;;
    -h|--help)       sed -n '2,19p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -n "$UPDATE" ] && ! [[ "$UPDATE" =~ ^[0-9]{2}(,[0-9]{2})*$ ]]; then
  echo "--update-lsphp expects branch numbers like 74,80" >&2
  exit 2
fi

write_dropin() {
  local want d f found=0
  want=$'; PHP2Shell interim mitigation (CVE-2026-109619). Partial: the fix is a patched lsphp package.\n; Managed by CPScripts/php2shell_mitigate.sh\nsession.upload_progress.enabled = 0\n'
  for d in "$LSWS_ROOT"/lsphp*; do
    [ -d "$d" ] || continue
    found=1
    if [ ! -d "$d/etc/php.d" ]; then
      warn "$d has no etc/php.d: set session.upload_progress.enabled = 0 in its php.ini by hand"
      continue
    fi
    f="$d/etc/php.d/99-php2shell.ini"
    if [ -f "$f" ] && printf '%s' "$want" | cmp -s - "$f"; then
      log "unchanged $f"
      continue
    fi
    if printf '%s' "$want" > "$f" && chmod 644 "$f"; then
      log "wrote $f"
    else
      warn "could not write $f"
    fi
  done
  [ "$found" = 1 ] || log "no lsphp installation found under $LSWS_ROOT"
}

update_lsphp() {
  local b pm globs=() branches
  IFS=',' read -ra branches <<< "$UPDATE"
  for b in "${branches[@]}"; do globs+=("lsphp${b}*"); done
  if   command -v dnf     >/dev/null 2>&1; then pm=dnf
  elif command -v yum     >/dev/null 2>&1; then pm=yum
  elif command -v apt-get >/dev/null 2>&1; then pm=apt-get
  else warn "no package manager found (dnf, yum, apt-get)"; return
  fi
  log "upgrading ${globs[*]} with $pm"
  case "$pm" in
    dnf|yum) "$pm" -y upgrade "${globs[@]}" || warn "$pm upgrade failed; nothing was forced, review the output above" ;;
    apt-get) DEBIAN_FRONTEND=noninteractive apt-get install --only-upgrade -y "${globs[@]}" || warn "apt-get upgrade failed; review the output above" ;;
  esac
}

refresh_panel() {
  local src="$LSWS_ROOT/lsphp${PANEL_SRC_BRANCH}/bin/lsphp" dst="$LSCP_ROOT/fcgi-bin/lsphp" bak
  if [ ! -x "$src" ]; then log "panel: $src not found, skipped"; return; fi
  if [ ! -e "$dst" ]; then log "panel: $dst not found, skipped"; return; fi
  if cmp -s "$src" "$dst"; then log "panel lsphp already matches $src"; return; fi
  bak="$dst.bak-$(date +%Y%m%d%H%M%S)"
  if ! cp -p "$dst" "$bak"; then warn "could not back up $dst; panel PHP not refreshed"; return; fi
  # copy to a temporary name and rename: overwriting a running binary fails with "Text file busy"
  if cp "$src" "$dst.new" && chmod 755 "$dst.new" && mv -f "$dst.new" "$dst"; then
    log "panel lsphp refreshed from $src (backup: $bak)"
    PANEL_REFRESHED=1
  else
    rm -f "$dst.new"
    warn "could not replace $dst; the backup is $bak"
  fi
}

restart_services() {
  if [ "$NO_SERVICE" = 1 ]; then log "service actions disabled (PHP2SHELL_NO_SERVICE=1)"; return; fi
  if [ "$PANEL_REFRESHED" = 1 ]; then
    if   command -v systemctl >/dev/null 2>&1; then systemctl restart lscpd || warn "could not restart lscpd"
    elif command -v service   >/dev/null 2>&1; then service lscpd restart   || warn "could not restart lscpd"
    fi
  fi
  if [ "$RESTART" = 1 ]; then
    [ -d "$LSWS_ROOT/admin/tmp" ] && touch "$LSWS_ROOT/admin/tmp/.lsphp_restart.txt" && log "requested a graceful lsphp restart"
    if command -v pkill >/dev/null 2>&1; then
      pkill -x lsphp 2>/dev/null
      log "stopped running lsphp workers (they respawn on the next request)"
    else
      warn "pkill not found: restart lsphp workers by hand"
    fi
  fi
}

summary() {
  local b v p
  log "--- summary (package, version line)"
  for b in "$LSWS_ROOT"/lsphp*/bin/lsphp; do
    [ -x "$b" ] || continue
    v=$("$b" -v 2>/dev/null | head -1)
    p=$(rpm -qf "$b" 2>/dev/null | head -1)
    [ -n "$p" ] || p=$(dpkg -S "$b" 2>/dev/null | head -1)
    log "$b | ${p:-no package} | ${v:-version unknown}"
  done
  if [ -x "$LSCP_ROOT/fcgi-bin/lsphp" ]; then
    log "panel $LSCP_ROOT/fcgi-bin/lsphp | $("$LSCP_ROOT/fcgi-bin/lsphp" -v 2>/dev/null | head -1)"
  fi
  [ "$FAILS" -eq 0 ] || log "$FAILS step(s) reported a problem, see WARNING lines above"
}

write_dropin
[ -n "$UPDATE" ]     && update_lsphp
[ "$REFRESH" = 1 ]   && refresh_panel
restart_services
summary

if [ "$STRICT" = 1 ] && [ "$FAILS" -gt 0 ]; then exit 1; fi
exit 0
