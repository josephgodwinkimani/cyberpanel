#!/usr/bin/env bash
# test_requirements_in_virtualenvs.sh: tests how cyberpanel_upgrade.sh and autoCyberpanel_upgrade.sh install the Python requirement files.
# The requirement files must go into the virtual environments with the pip of the activated environment. The system pip ($PIP3) must
# only install virtualenv itself: with it a new setuptools was installed into the system Python and broke the build of source
# packages there (the older packaging of the system could not be used by it) and two Django releases ended up in one folder.
# Every environment must also get the current setuptools and packaging before the first requirement file is installed into it.
# The scripts are only read, nothing is run and nothing outside a temp folder is written. Run: bash CPScripts/test_requirements_in_virtualenvs.sh

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
ROOT="$(mktemp -d)" || exit 2
trap 'rm -rf "$ROOT"' EXIT
TOTAL=0; OK=0
ok()  { TOTAL=$((TOTAL + 1)); OK=$((OK + 1)); echo "ok    $1"; }
nok() { TOTAL=$((TOTAL + 1)); echo "NOT OK $1"; [ -n "${2:-}" ] && echo "$2" | sed 's/^/        /'; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else nok "$1" "wanted: $3
got:    $2"; fi; }

# problems FILE: prints one line per problem found in the script, nothing when it is fine
problems() {
  awk '
    /^[[:space:]]*#/ { next }
    /virtualenv -p [^ ]+ .*\/usr\/local\/Cyber/ || /virtualenv -p [^ ]+ \/usr\/local\/Cyber/ { upgraded = 0; next }
    /pip install --upgrade setuptools packaging/ { upgraded = 1; next }
    /install .*-r \/usr\/local\/requirments(-old)?\.txt/ {
      if ($0 ~ /\$PIP3/ || $0 ~ /\/usr\/bin\/pip3/) print NR ": a requirement file is installed with the system pip: " $0
      if (!upgraded) print NR ": a requirement file is installed before setuptools and packaging were upgraded in its environment: " $0
    }
  ' "$1"
}

for s in cyberpanel_upgrade.sh autoCyberpanel_upgrade.sh; do
  f="$REPO/$s"
  [ -f "$f" ] || { echo "missing $f"; exit 2; }
  check "$s has no problem" "$(problems "$f")" ""
  check "$s: the system pip is used for virtualenv only" "$(grep -vE '^[[:space:]]*#' "$f" | grep -E '\$PIP3 install' | grep -vc 'virtualenv$' | tr -d ' ')" "0"
  check "$s: the three environments are CyberPanel, CyberPanelTemp and CyberCP" "$(grep -vE '^[[:space:]]*#' "$f" | grep -E 'virtualenv -p [^ ]+ .*/usr/local/(CyberPanel|CyberPanelTemp|CyberCP)$' | grep -oE '/usr/local/(CyberPanel|CyberPanelTemp|CyberCP)$' | sort -u | paste -sd ' ' -)" "/usr/local/CyberCP /usr/local/CyberPanel /usr/local/CyberPanelTemp"
  check "$s: the temporary environment is upgraded right after it is activated" "$(grep -vE '^[[:space:]]*#' "$f" | awk '/^\. \/usr\/local\/CyberPanelTemp\/bin\/activate$/ {getline n; print n; exit}')" "pip install --upgrade setuptools packaging"
  bash -n "$f" 2> /dev/null && ok "$s passes bash -n" || nok "$s passes bash -n"
  check "$s has no carriage returns" "$(tr -cd '\r' < "$f" | wc -c | tr -d ' ')" "0"

  # controls: the same checks on damaged copies must report a problem
  sed 's#^  pip3 install --default-timeout=3600 --ignore-installed -r /usr/local/requirments.txt#  $PIP3 install --default-timeout=3600 --ignore-installed -r /usr/local/requirments.txt#' "$f" > "$ROOT/c1.sh"
  [ -n "$(problems "$ROOT/c1.sh")" ] && ok "control: $s with the system pip for requirments.txt is reported" || nok "control: $s with the system pip for requirments.txt is reported"
  awk 'BEGIN{skip=0} /^\. \/usr\/local\/CyberPanelTemp\/bin\/activate$/ {print; skip=1; next} skip==1 && /^pip install --upgrade setuptools packaging$/ {skip=0; next} {print}' "$f" > "$ROOT/c2.sh"
  [ -n "$(problems "$ROOT/c2.sh")" ] && ok "control: $s without the upgrade in the temporary environment is reported" || nok "control: $s without the upgrade in the temporary environment is reported"
done

echo "----"
echo "$OK of $TOTAL checks passed"
[ "$OK" = "$TOTAL" ] || exit 1
exit 0
