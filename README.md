# forge-repro

Reproductions for bugs in the [Forge](https://github.com/forge-ext/forge) GNOME Shell tiling
extension. Each scenario runs Forge in a **nested, isolated GNOME Shell** and drives it with
virtual input, so the results are exact and repeatable. It never touches your running session.

## Requirements

- GNOME Shell 50 with the devkit (`gnome-shell --devkit`; Debian/Ubuntu: `mutter-dev-bin`)
- `make`, `gettext`, `unzip`, Python 3 with PyGObject, GNOME Text Editor
- A forge checkout next to this repo (`../forge`), or set `FORGE_SRC=/path/to/forge`

## Usage

```sh
sandbox/launch.sh                       # build ../forge and start the nested shell (a devkit window opens)
scenarios/01_cross_container_snapback.py
sandbox/stop.sh
```

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
