#!/usr/bin/env bash
# Capture one screenshot set on one Forge build, in a fresh sandbox:
#   docs/shoot.sh BUG NAME FORGE_CHECKOUT      e.g. docs/shoot.sh 20 main ~/src/forge-main
# (SANDBOX_DIR / SANDBOX_DISPLAY / SANDBOX_PROFILE as for sandbox/launch.sh; see docs/make_shots.py)
set -euo pipefail
cd "$(dirname "$0")/.."
bug=$1 name=$2
export FORGE_SRC=$3
sandbox/stop.sh >/dev/null
sandbox/launch.sh >/dev/null
echo "shots $bug $name" > "${SANDBOX_DIR:-$HOME/.cache/forge-repro/sandbox}/scenario"
status=0
docs/make_shots.py "$bug" "$name" || status=$?
sandbox/stop.sh >/dev/null
exit $status
