# Forge test harness

Automated, repeatable tests for the [Forge](https://github.com/forge-ext/forge) GNOME Shell tiling
extension. Each test runs Forge in a **nested, isolated GNOME Shell**, drives it with a virtual
mouse and keyboard, and checks the resulting layout exactly: window positions and sizes, gaps, minimum sizes, and each
container's shares. It never touches the GNOME session you are working in.

It started as the reproduction repository for a set of Forge bug reports, and it is written so
that both **people** and **AI coding agents** can use it:
- reproduce a bug;
- check a fix;
- look for new bugs with the randomized stress test;
- measure performance.

- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Scenarios](#scenarios)
- [Writing a scenario](#writing-a-scenario)
- [Debugging](#debugging)
- [For AI agents](#for-ai-agents)
- [Limitations](#limitations)

## Quick start

Requirements:
- GNOME Shell 50+ (the tests run `gnome-shell --headless` with a virtual monitor);
- `make`, `gettext`, `unzip`;
- Python 3 with PyGObject;
- GNOME Text Editor;
- Pillow (screenshots only);
- to watch the tests live: GStreamer with `pipewiresrc` and `gtksink` (Debian/Ubuntu:
  `gstreamer1.0-pipewire`, `gstreamer1.0-gtk3`).

It finds the Forge checkout it is part of (`tests/` inside Forge) or a sibling `../forge` clone.
Set `FORGE_SRC=/path/to/forge` to test another checkout or a git worktree.

```sh
sandbox/watch.py &                 # optional: a window that shows the test monitor live
sandbox/run-suite.sh               # build Forge, run every scenario, print a summary
sandbox/run-suite.sh 01 03         # just these scenarios
```

Or step by step:

```sh
sandbox/launch.sh                  # build Forge, start the nested shell (1920x1080, headless)
scenarios/03_resize_bounds.py      # PASS/FAIL per check; exit code 0 = all passed
sandbox/stop.sh
```

Each scenario needs a **fresh** sandbox, because it opens its own windows; `run-suite.sh` starts one per
scenario. Output looks like this:

```
bug: growing a window into a neighbour at its minimum size
  PASS  3.1: hold 'grow right' on A for 3304 ms
  FAIL  3.1 (while held): no overlap or off-screen while the key repeats
          - 29 and 30 overlap by 360 px (2804ms holding 2300ms calls=65)
...
sandbox JS errors: 0
RESULT: 8/12 passed
```

### Profiles and screen sizes

- `sandbox/launch.sh 2560x1440` sets the virtual monitor size.
- `SANDBOX_PROFILE=real sandbox/launch.sh` mirrors the machine you run it on as closely as
  possible:
  - its monitor size;
  - the session mode (e.g. `ubuntu`, with the Ubuntu dock and desktop icons);
  - its enabled and disabled extensions;
  - its Forge settings, copied read-only into the sandbox.

  This catches problems that only show up with a real setup. For example, on a wide screen
  Forge's auto-split nests containers in the same direction, and that exposed a bug the default
  profile could not.
- The scenarios adapt to the screen size and read Forge's shortcuts from its settings.

## How it works

- **Isolation.** `sandbox/launch.sh` builds Forge with `make build && make dist` and installs it
  into a throwaway directory (`~/.cache/forge-repro/sandbox`). It then starts
  `gnome-shell --headless --virtual-monitor WxH` with:
  - its **own D-Bus session bus** (`dbus-run-session`);
  - its own extensions directory (`XDG_DATA_HOME`);
  - keyfile settings (`GSETTINGS_BACKEND=keyfile`).

  Your session's dconf, extensions and windows are never touched.

  ⚠️ Only `make build` and `make dist` are used, because Forge's default `make` target runs
  `killall -HUP gnome-shell`.
- **Driving it.** A sandbox-only helper extension (`sandbox/sandbox-unsafe@local`) enables unsafe
  mode in the nested shell. That lets the harness run JavaScript inside it through
  `org.gnome.Shell.Eval` on the sandbox's private bus; `harness.bus()` refuses any other bus.
  Mouse and keyboard input come from Clutter virtual devices created inside the nested shell, so
  the whole path is real: key repeat, grabs, Forge's keybindings and live-resize loop.
- **Checking.** `harness.layout_problems()` checks the layout rules after an action:
  - every window is inside the work area;
  - no two windows overlap, except those sharing a tabbed or stacked container;
  - every window has the size Forge laid it out at;
  - no window is below the minimum size its app allows;
  - each split's shares are in (0, 1] and add up to 1.

  `harness.timeline_problems()` checks the same while a drag or held key is still in progress,
  from samples taken every 100 ms. It allows 30 px for Wayland applying a new position a frame
  before the new size.
- **Watching.** `sandbox/watch.py` screencasts the test monitor (Mutter ScreenCast on the sandbox
  bus → PipeWire → GStreamer) into a window on your desktop, and reconnects to each new sandbox.

## Scenarios

| Scenario | What it checks | Bug / PR |
|---|---|---|
| `01_cross_container_snapback.py` | Mouse drags and held resize shortcuts against a neighbour in **another container** keep their size | #532, \<issue 1\> |
| `02_keyboard_resize_edge.py` | Vertical resize shortcuts move the right edge; a **slow app** is not slid sideways during key repeat | \<issue 2\> |
| `03_resize_bounds.py` | A resize **stops at the neighbour's minimum size**, also while the key is held, with a slow app and with a slow neighbour | \<issue 3\> |
| `04_min_size_layout.py` | The layout respects **minimum sizes** when the space shrinks; the `min-size-overflow` setting groups windows that don't fit | #117, #271 |
| `06_stale_tab_bar.py` | A tab bar goes away when all of its windows close at once | \<issue 6\> |
| `07_real_apps.py` | Checks 01–03 with real apps (Ptyxis, Files, VS Code) in the layout Forge builds by itself | |
| `08_nested_same_direction.py` | Resizing a window's outer edge leaves its sibling alone in `HSPLIT[A, HSPLIT[B, C]]` | \<issue 7\> |
| `09_fuzz.py` | **Randomized stress test**: random actions, the layout rules checked after each one | finds new bugs |
| `10_performance.py` | Timings of Forge's hot paths and the window move requests it sends | \<perf PR\> |

`09_fuzz.py --seed N --steps M` is deterministic for a given seed. When a step breaks a rule, it
stops and prints the steps so far, so the failure can be replayed.

## Writing a scenario

A scenario is a Python script that opens windows, acts, and checks. The harness (`lib/harness.py`)
provides:

| Function | Purpose |
|---|---|
| `windows()` | Tiled/floating windows on the current workspace: `id, x, y, w, h, percent, playout, pid, depth, float` |
| `open_editor()`, `open_app(*argv)` | Open a window in the sandbox and wait until Forge tiles it |
| `nested_layout(openers)` | Three windows as `[A] + CON[B, C]`; returns `(A, B, C)` |
| `ensure_parent_layout(id, "HSPLIT"/"VSPLIT")` | Set the direction of a window's container (auto-split varies with screen size) |
| `drag_edge(id, side, delta, during=f)` | Drag a window edge with the virtual mouse; returns a timeline log |
| `hold_keys(id, keys, ms, during=f)` | Hold a key chord (real key repeat); returns a timeline log |
| `GROW_KEYS[side]`, `SHRINK_KEYS[side]`, `chord(name)` | Key chords read from Forge's keybinding settings |
| `stall_app(id, after_s, for_s)` | For `during=`: freeze the window's app (SIGSTOP) as if it were slow to redraw |
| `layout_check(name, what)` | PASS/FAIL on `layout_problems()` after the layout settles |
| `timeline_check(name, what, log, ignore=id)` | PASS/FAIL on the in-progress samples; prints trajectories on failure |
| `settle_check(name, id, side, nb_id, expected_edge)` | An edge ended where it was released, one gap from its neighbour |
| `set_forge_setting(key, value)`, `reset_layout()`, `tree_summary()`, `monitor_size()` | Settings, equal split, `HSPLIT[w1, VSPLIT[w2, w3]]`, work-area size |
| `summary(results)` | Print `RESULT: n/m` and return the exit code (also fails on new `JS ERROR`s) |

A minimal scenario:

```python
#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h

h.open_editor(); h.open_editor()
a, b = sorted(h.windows(), key=lambda w: w["x"])
log = h.hold_keys(a["id"], h.GROW_KEYS["right"], 2000)        # hold "grow right" for 2 s
r = [h.layout_check("x.1", "layout valid after the hold"),
     h.timeline_check("x.1 (while held)", "valid during the hold", log)]
sys.exit(h.summary(r))
```

Screenshots for issues and PRs (`lib/shots.py`):
- `shot(path)`: the test monitor;
- `later(path, s)`: for `during=`, a screenshot partway through an action;
- `annotate(src, dst, boxes)`: labelled boxes;
- `side_by_side(dst, items)`: before/after panels.

## Debugging

- `sandbox/sb_eval.py 'JS expression'` runs JavaScript in the sandbox shell. Forge's window manager
  is at `Main.extensionManager.lookup("forge@jmmaranan.com").stateObj.extWm`.
- `sandbox/sb_eval.py - < lib/tree.js` prints Forge's tree with rects and percents.
- `lib/trace.js` logs every call of Forge's resize functions with the frame and the baseline;
  `lib/perf.js` times Forge's hot functions and counts window move requests.
- `~/.cache/forge-repro/sandbox/nested.log` is the nested shell's log (`JS ERROR` lines are
  Forge exceptions).
- `sandbox/run-in-sandbox.sh <cmd>` runs a program inside the sandbox session.
- `SANDBOX_BACKEND=devkit sandbox/launch.sh` also opens the Mutter devkit viewer. Its monitor is not the
  test monitor, so use `watch.py` to see the tests.

## For AI agents

This harness is designed to be run end to end by a coding agent without a person at the keyboard.

**Workflow**
1. Reproduce first. Run the relevant scenario on the unmodified code and keep the output. A
   failing check with numbers ("overlap by 360 px") is the bug report.
2. Change Forge. Run `npx prettier@2.7.1 --check` (Forge's CI style check).
3. Run the scenario again, then `sandbox/run-suite.sh` for regressions, then
   `SANDBOX_PROFILE=real sandbox/run-suite.sh` for the machine's real screen size and extensions.
4. Run `scenarios/09_fuzz.py --seed N` with a few seeds. A failure prints its steps: turn them
   into a scenario, or fix the checker if the rule was wrong (e.g. tabbed windows share space).
5. For write-ups, capture evidence with `lib/shots.py`: a screenshot partway through the action
   shows what a person would see.

**Rules**
- Never run plain `make` in the Forge checkout (it restarts your GNOME Shell). Use the sandbox
  scripts.
- Never talk to the host session's bus. `harness.bus()` only accepts the sandbox's private
  `dbus-run-session` bus. Find sandbox processes with `sandbox_pids` (in `sandbox/env.sh`), never
  with `pkill -f`/`pgrep -f` patterns: they match your own command lines.
- Don't disable the sandbox's monitor through DisplayConfig (the nested shell crashes).
- Don't pipe a long-running script into `head` (SIGPIPE kills it); use `tail` or redirect to a
  file.
- In zsh, `$VAR` with spaces is not word-split: use the provided bash scripts, or apps may start on
  the real display.
- Timing matters. Wayland applies a new position before a new size, and apps redraw at their own
  pace. Judge "during the action" with the timeline checks (30 px tolerance), and the final state
  with `layout_check` after it settles.

## Limitations

- GNOME Shell 50+ only. Older versions may work for the checks but lack `get_min_size()`.
- It can't run on GitHub-hosted CI runners, which don't have GNOME Shell 50. Run it locally or on
  a self-hosted runner.
- Mouse drags: GNOME resizes the dragged window with the pointer. Mutter's new external
  constraints could stop it at a limit, but they can't be changed from JavaScript (GJS copies the
  rectangle). So the dragged window itself is exempt from the "while dragging" checks.
