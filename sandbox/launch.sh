#!/usr/bin/env bash
# Start an isolated nested GNOME Shell running Forge built from $FORGE_SRC.
#
# Isolation: the nested shell gets its own D-Bus session bus (dbus-run-session), its own
# extensions directory (XDG_DATA_HOME) and keyfile-backed settings (GSETTINGS_BACKEND=keyfile),
# so the host session's dconf and extensions are never touched.
#
#   sandbox/launch.sh [WxH]     default 1920x1080: the fixed-size virtual monitor (monitor 0)
#                               the scenarios run on. To watch it live: sandbox/watch.py &
#   SANDBOX_BACKEND=devkit sandbox/launch.sh
#                               also open the Mutter devkit viewer (needs mutter-dev-bin). It
#                               shows an extra monitor, not the test monitor; do NOT disable that
#                               monitor (the nested shell exits if you do).
set -euo pipefail
source "$(dirname "$0")/env.sh"
SIZE=${1:-1920x1080}
# SANDBOX_BACKEND=headless (default): no window of its own; watch it with sandbox/watch.py.
# SANDBOX_BACKEND=devkit: also opens the Mutter devkit viewer, which shows a second monitor
# whose size follows the viewer window (the scenarios still run on the fixed-size monitor 0).
BACKEND=${SANDBOX_BACKEND:-headless}
[[ $BACKEND == headless || $BACKEND == devkit ]] || { echo "SANDBOX_BACKEND must be headless or devkit"; exit 1; }

for _ in $(seq 20); do [[ -z $(sandbox_pids) ]] && break; sleep 0.5; done
[[ -z $(sandbox_pids) ]] || { echo "sandbox already running (pid $(sandbox_pids))"; exit 1; }
[[ -e $FORGE_SRC/.git ]] || { echo "FORGE_SRC=$FORGE_SRC is not a git checkout of forge"; exit 1; }

rm -rf "$SANDBOX_DIR"
mkdir -p "$SANDBOX_DIR/data/gnome-shell/extensions/$FORGE_UUID" "$SANDBOX_DIR/config"

# Build. Only `make build` / `make dist`: forge's default target runs `killall -HUP gnome-shell`.
# </dev/null because `make metadata` runs `git shortlog`, which otherwise waits on stdin.
( cd "$FORGE_SRC" && make build </dev/null >/dev/null && make dist </dev/null >/dev/null )
# `make build` regenerates po/*.po as a side effect; keep the checkout clean.
git -C "$FORGE_SRC" checkout -- po/
unzip -q -o "$FORGE_SRC/$FORGE_UUID.zip" -d "$SANDBOX_DIR/data/gnome-shell/extensions/$FORGE_UUID"
# Sandbox-only helper that enables unsafe mode (org.gnome.Shell.Eval) for the test driver.
cp -r "$REPRO_ROOT/sandbox/sandbox-unsafe@local" "$SANDBOX_DIR/data/gnome-shell/extensions/"
git -C "$FORGE_SRC" log -1 --format='forge: %h %s (%D)' > "$SANDBOX_DIR/forge-version"

export XDG_DATA_HOME=$SANDBOX_DIR/data XDG_CONFIG_HOME=$SANDBOX_DIR/config GSETTINGS_BACKEND=keyfile
gsettings set org.gnome.shell enabled-extensions "['$FORGE_UUID', 'sandbox-unsafe@local']"
gsettings set org.gnome.mutter dynamic-workspaces false        # forge: no dynamic workspaces
gsettings set org.gnome.desktop.wm.preferences num-workspaces 4
gsettings set org.gnome.shell welcome-dialog-last-shown-version '999'

setsid dbus-run-session -- bash -c '
  echo "$DBUS_SESSION_BUS_ADDRESS" > "'"$SANDBOX_DIR"'/bus-address"
  exec gnome-shell --wayland --'"$BACKEND"' --virtual-monitor '"$SIZE"' \
       --wayland-display '"$SANDBOX_DISPLAY"'
' > "$SANDBOX_DIR/nested.log" 2>&1 < /dev/null &

for _ in $(seq 60); do
  [[ -s $SANDBOX_DIR/bus-address ]] && grep -q 'GNOME Shell started' "$SANDBOX_DIR/nested.log" 2>/dev/null && break
  sleep 0.5
done
grep -q 'GNOME Shell started' "$SANDBOX_DIR/nested.log" || { echo "sandbox failed to start; see $SANDBOX_DIR/nested.log"; exit 1; }
sleep 2
cat "$SANDBOX_DIR/forge-version"
echo "sandbox ready: bus $(cat "$SANDBOX_DIR/bus-address")"
