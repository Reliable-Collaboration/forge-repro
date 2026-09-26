# Shared settings for the sandbox scripts (sourced, not executed).
REPRO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Forge source checkout to build and test (default: a sibling ../forge clone).
FORGE_SRC="${FORGE_SRC:-$(cd "$REPRO_ROOT/.." && pwd)/forge}"
# Where the throwaway sandbox state lives (extensions dir, keyfile settings, logs, bus address).
SANDBOX_DIR="${SANDBOX_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/forge-repro/sandbox}"
FORGE_UUID=forge@jmmaranan.com
SANDBOX_DISPLAY=wayland-forge
# Print PIDs of sandbox gnome-shell processes only (never matches the real session's shell).
sandbox_pids() { for p in $(pgrep -x gnome-shell); do tr '\0' ' ' < "/proc/$p/cmdline" | grep -q -- "wayland-display $SANDBOX_DISPLAY" && echo "$p"; done; }
