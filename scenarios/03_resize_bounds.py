#!/usr/bin/env python3
"""Issue 3: a resize keeps going after the neighbour has reached its minimum size.

Growing a tiled window (held shortcut or mouse drag) keeps shrinking the neighbour's percent
after the neighbour's app refuses to get any smaller. The neighbour is then pushed partly
off-screen or over other windows, and the percents stop adding up (one goes over 100%).

Expected: the resize stops when the neighbour reaches its minimum size.
Run on a fresh sandbox:  sandbox/launch.sh && scenarios/03_resize_bounds.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402

SHRINK_KEYS = {"right": "0xffe3, 0xffe1, 0xffeb, 0x79"}  # Ctrl+Shift+Super+Y: shrink the right edge
HOLD_MS = 3000   # ~70 repeats of 15 px: far more than the space available


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    h.open_editor()
    h.open_editor()
    a, b = sorted(h.windows(), key=lambda w: w["x"])
    print(f"layout: [A={a['id'] % 1000} | B={b['id'] % 1000}] side by side (Text Editor: min frame 360x200)")
    r = []
    print("bug: growing a window into a neighbour at its minimum size")
    log = h.hold_keys(a["id"], h.GROW_KEYS["right"], HOLD_MS)
    r.append(h.layout_check("3.1", f"hold 'grow right' on A for {HOLD_MS} ms"))
    r.append(h.timeline_check("3.1 (while held)", "no overlap or off-screen while the key repeats", log))
    h.reset_layout()
    log = h.hold_keys(b["id"], h.GROW_KEYS["left"], HOLD_MS)
    r.append(h.layout_check("3.2", f"hold 'grow left' on B for {HOLD_MS} ms"))
    r.append(h.timeline_check("3.2 (while held)", "no overlap or off-screen while the key repeats", log))
    h.reset_layout()
    h.drag_edge(a["id"], "right", 1300, steps=40)
    r.append(h.layout_check("3.3", "drag A's right edge 1300 px to the right"))
    h.reset_layout()

    print("bug: shrinking the focused window past its minimum leaves a gap (shares sum < 100%)")
    h.hold_keys(a["id"], SHRINK_KEYS["right"], HOLD_MS)
    r.append(h.layout_check("3.4", f"hold 'shrink right' on A for {HOLD_MS} ms"))
    h.reset_layout()

    print("bug, vertical: B above C in a container, grow B's bottom edge into C")
    h.open_app("gnome-text-editor", "--standalone")   # opens next to the focused window
    ws = h.windows()
    con = sorted([w for w in ws if w["pid"] == "con"], key=lambda w: w["y"])
    if len(con) == 2 and con[0]["playout"] == "VSPLIT":
        h.reset_layout()
        log = h.hold_keys(con[0]["id"], h.GROW_KEYS["bottom"], HOLD_MS)
        r.append(h.layout_check("3.5", f"hold 'grow bottom' on the upper window for {HOLD_MS} ms"))
        r.append(h.timeline_check("3.5 (while held)", "no overlap or off-screen while the key repeats", log))
        # Cross-container (parent pairs): grow a window in the container toward the top-level
        # window. On builds without the issue 1 fix, the held resize snaps back on release, so
        # this case only exercises the limit once issue 1 is fixed too.
        print("bug, across containers: grow a window in the container into the top-level window")
        h.reset_layout()
        top = next(w for w in h.windows() if w["pid"] == "top")
        side = h.neighbour_side(h.find(h.windows(), con[0]["id"]), top)
        log = h.hold_keys(con[0]["id"], h.GROW_KEYS[side], HOLD_MS)
        r.append(h.layout_check("3.6", f"hold 'grow {side}' on the upper window for {HOLD_MS} ms"))
        r.append(h.timeline_check("3.6 (while held)", "no overlap or off-screen while the key repeats", log))
    else:
        print(f"  SKIP  3.5: third window did not form a vertical container: {ws}")
    sys.exit(h.summary(r))


main()
