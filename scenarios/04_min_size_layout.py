#!/usr/bin/env python3
"""Issue 4: the layout ignores windows' minimum sizes.

Forge splits space purely by percent. When a window's share is smaller than the minimum size
its app allows, GNOME keeps the window at its minimum and it overlaps its neighbour or extends
off-screen (#117, #271).

Part 1, the windows fit: after a resize has left a window at its minimum, anything that shrinks
the space (here: larger gaps; also a lower display resolution or a panel) squeezes it below
its minimum. Expected: it keeps its minimum and the other windows give up the space.
Part 2, the windows don't fit (6 Text Editors side by side need 6 x 368 px > 1904 px):
setting `min-size-overflow` = tabbed / stacked groups windows until the rest fit.

Run on a fresh sandbox:  sandbox/launch.sh && scenarios/04_min_size_layout.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402

WM = h.WM


def shares():
    return [(w["id"] % 1000, w["x"], w["w"], round(w["percent"], 3)) for w in sorted(h.windows(), key=lambda w: (w["x"], w["y"]))]


def close_all():
    """Close monitor 0's windows one at a time. (Closing all windows of a tabbed container at
    the same moment leaves its tab bar on screen: a separate upstream bug, not tested here.)"""
    while h.windows():
        before = len(h.windows())
        h.js("""(() => { global.display.list_all_windows().find(w => w.get_monitor() === 0)
            .delete(global.get_current_time()); return "ok"; })()""")
        for _ in range(40):
            time.sleep(0.25)
            if len(h.windows()) < before:
                break
        else:
            raise RuntimeError("window did not close")
        time.sleep(0.3)


def overflow(name, policy, split=None):
    """Open windows until 6 editors are side by side (or stacked vertically with split)."""
    close_all()
    h.set_forge_setting("window-gap-size-increment", 1)
    ok_key = h.set_forge_setting("min-size-overflow", policy)
    h.open_editor()
    if split:
        h.js(f'(() => {{ {WM}.command({{name: "Split", orientation: "{split}"}}); return "ok"; }})()')
        time.sleep(0.5)
    for _ in range(5):
        h.open_editor()
    what = f"6 windows {'in a vertical container' if split else 'side by side'}, min-size-overflow={policy}"
    if not ok_key:
        print(f"  FAIL  {name}: {what}: this Forge build has no min-size-overflow setting")
        ok = h.layout_check(name + " (layout)", "6 windows with no overflow handling")
        return False
    ok = h.layout_check(name, what)
    print(f"          tree: {h.tree_summary()}")
    return ok


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    h.set_forge_setting("auto-split-enabled", False)   # new windows join the focused window's split
    r = []

    print("bug: the windows fit, but the space shrinks after a resize left one at its minimum")
    for _ in range(3):
        h.open_editor()
    a = sorted(h.windows(), key=lambda w: w["x"])[0]
    h.drag_edge(a["id"], "right", 600, steps=30)          # B (middle) ends at its minimum width
    time.sleep(1.0)
    print(f"          after drag: {shares()}")
    h.set_forge_setting("window-gap-size-increment", 4)   # gaps 4 -> 16 px
    time.sleep(0.5)
    r.append(h.layout_check("4.1", "gap size 4 -> 16 px with the middle window at its minimum"))
    print(f"          {shares()}")

    print("overflow: more windows than fit at their minimum size")
    r.append(overflow("4.2", "tabbed"))
    r.append(overflow("4.3", "stacked"))
    r.append(overflow("4.4", "tabbed", split="vertical"))
    print("control: default policy keeps today's behaviour (windows overlap), no errors")
    close_all()
    h.set_forge_setting("min-size-overflow", "overlap")
    for _ in range(6):
        h.open_editor()
    probs = h.layout_problems()
    print(f"  {'PASS' if probs else 'FAIL'}  4.5: overlap policy leaves the overflow as it is "
          f"({len(probs)} layout problems, expected > 0)")
    r.append(bool(probs))
    sys.exit(h.summary(r))


main()
