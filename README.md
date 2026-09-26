# forge-repro

Reproductions for bugs in the [Forge](https://github.com/forge-ext/forge) GNOME Shell tiling
extension. Each scenario runs Forge in a **nested, isolated GNOME Shell** and drives it with
virtual input, so the results are exact and repeatable. It never touches your running session.

## Requirements

- GNOME Shell 50 (the sandbox runs `gnome-shell --headless`)
- `make`, `gettext`, `unzip`, Python 3 with PyGObject, GNOME Text Editor
- To watch the tests live (optional): GStreamer with `pipewiresrc` and `gtksink`
  (Debian/Ubuntu: `gstreamer1.0-pipewire`, `gstreamer1.0-gtk3`)
- A forge checkout next to this repo (`../forge`), or set `FORGE_SRC=/path/to/forge`

## Usage

```sh
sandbox/watch.py &                      # optional: a window that shows the test monitor live
sandbox/launch.sh                       # build ../forge and start the nested shell (headless)
scenarios/01_cross_container_snapback.py
sandbox/stop.sh
```

The scenarios run on a fixed 1920x1080 virtual monitor. `sandbox/watch.py` screencasts that
monitor (Mutter ScreenCast on the sandbox's own bus) into a window on your desktop; it stays open
and reconnects each time a new sandbox starts. `SANDBOX_BACKEND=devkit sandbox/launch.sh` also
opens the Mutter devkit viewer (`mutter-dev-bin`), but that shows a separate monitor, not the
test monitor.

Each scenario prints PASS/FAIL per check and exits non-zero on failure. Launch a fresh sandbox
before each scenario, because they create their own windows.

## How it stays isolated

- The nested shell gets its own D-Bus session bus (`dbus-run-session`), extensions directory
  (`XDG_DATA_HOME`) and keyfile-backed settings (`GSETTINGS_BACKEND=keyfile`) under
  `~/.cache/forge-repro/sandbox`.
- `sandbox/sandbox-unsafe@local` is loaded **only in the nested shell**. It enables unsafe mode
  so the driver can call `org.gnome.Shell.Eval` on the nested shell's private bus.
- Mouse and keyboard input are Clutter virtual devices created *inside* the nested shell.
- ⚠️ Only `make build` / `make dist` are used. Forge's default `make` target runs
  `killall -HUP gnome-shell`.

## Scenarios

| Scenario | Bug | Result on `main` @ `07498ab` |
|---|---|---|
| `01_cross_container_snapback.py` | A continuous resize (mouse drag / held shortcut, #532) against a neighbour in a **different container** snaps back on release | 6/10 (fails 1.3, 1.4, 1.6, 1.9) |
| `02_keyboard_resize_edge.py` | Holding/tapping a top/bottom `window-resize-*` shortcut moves the **opposite** edge during the key repeat | 2/6 (fails 2.1–2.4) |
| `03_resize_bounds.py` | A held resize keeps going after the neighbour reaches its **minimum size**: it is pushed off-screen, shares go over 100% (or under, leaving a gap) | 2/6 (fails 3.1, 3.2, 3.4, 3.5; 3.6 only fails once 01 is fixed) |
| `04_min_size_layout.py` | The layout ignores windows' **minimum sizes**: overlap/off-screen when the space shrinks, or when there are more windows than fit (#117, #271) | 1/5 (fails 4.1–4.4) |
| `06_stale_tab_bar.py` | A **tab bar stays on screen** after all windows of a tabbed container close at once | 1/3 (fails 6.2, 6.3) |

`spikes/overflow-clip/` is a feasibility check (not a bug): cropping an overflowing window to its
tile.
