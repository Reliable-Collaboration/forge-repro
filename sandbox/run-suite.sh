#!/usr/bin/env bash
# Run scenarios on one Forge build, each on a fresh sandbox, and print a summary.
#
#   sandbox/run-suite.sh [scenario ...]            default: all scenarios/*.py
#   FORGE_SRC=/path/to/forge SANDBOX_PROFILE=real sandbox/run-suite.sh 03 07
#
# Scenarios can be given by number (03) or file name. Full output of each scenario goes to
# $SUITE_OUT (default ~/.cache/forge-repro/suite/<build>-<profile>/<scenario>.txt).
# Watch it live with sandbox/watch.py &.
set -uo pipefail
source "$(dirname "$0")/env.sh"
cd "$REPRO_ROOT"

PROFILE=${SANDBOX_PROFILE:-plain}
BUILD=$(git -C "$FORGE_SRC" rev-parse --short HEAD)
OUT=${SUITE_OUT:-$HOME/.cache/forge-repro/suite/$BUILD-$PROFILE}
mkdir -p "$OUT"

if [[ $# -eq 0 ]]; then
  set -- scenarios/[0-9]*.py
fi

declare -a SUMMARY
for arg in "$@"; do
  scenario=$(ls scenarios/"$arg"*.py 2>/dev/null | head -1)
  [[ -n $scenario ]] || scenario=$arg
  name=$(basename "$scenario" .py)
  sandbox/stop.sh >/dev/null
  if ! sandbox/launch.sh > "$OUT/$name.launch.txt" 2>&1; then
    SUMMARY+=("$name: sandbox failed to start (see $OUT/$name.launch.txt)")
    continue
  fi
  echo "== $name on $(cat "$SANDBOX_DIR/forge-version") [$PROFILE]"
  timeout 1200 "$scenario" > "$OUT/$name.txt" 2>&1
  grep -E "PASS|FAIL|SKIP|^ +- |RESULT|errors: [1-9]|Traceback|Error" "$OUT/$name.txt"
  SUMMARY+=("$name: $(grep -oE 'RESULT: [0-9]+/[0-9]+' "$OUT/$name.txt" || echo 'no result (see output)')")
done
sandbox/stop.sh >/dev/null

echo
echo "== summary: $BUILD [$PROFILE], outputs in $OUT"
printf '  %s\n' "${SUMMARY[@]}"
