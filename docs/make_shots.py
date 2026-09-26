#!/usr/bin/env python3
"""Screenshots for the issue and PR write-ups: each bug on one build, captured at the moment that
shows it (partway through a drag or a held key, or after it settles).

    docs/make_shots.py BUG NAME        run on a fresh sandbox (sandbox/launch.sh) with the build to
                                       capture; writes docs/images/<BUG>-<NAME>-*.png
    docs/make_shots.py --compose BUG   before/after images from the main/fix captures

BUG is one of the keys of SHOTS below.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402
import shots  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
RED, GREEN, AMBER = shots.RED, shots.GREEN, shots.AMBER


def path(bug, name, moment):
    return os.path.join(OUT, f"{bug}-{name}-{moment}.png")


def boxes_for(ids, colour, labels):
    ws = {w["id"]: w for w in h.windows()}
    out = []
    for wid, label in zip(ids, labels):
        w = ws.get(wid)
        if w:
            out.append((w["x"], w["y"], w["w"], w["h"], colour, label))
    return out


def ptyxis():
    h.open_app("ptyxis", "--new-window")


def files():
    h.open_app("nautilus", "--new-window")


def editor():
    h.open_editor()


# --- one function per bug: set up, act, capture ---------------------------------------------

def cross_container_drag(name):
    """Issue 1: drag the border between Files (in a container) and Ptyxis (outside it)."""
    a, b, c = h.nested_layout((ptyxis, files, editor))
    h.ensure_parent_layout(c["id"], "VSPLIT")
    side = h.neighbour_side(h.find(h.windows(), b["id"]), h.find(h.windows(), a["id"]))
    delta = -300 if side in ("left", "top") else 300
    h.drag_edge(b["id"], side, delta, steps=30, step_ms=60,
                during=shots.later(path("1", name, "during"), 1.8))
    time.sleep(1.5)
    shots.shot(path("1", name, "after"))


def held_key_cross_container(name):
    """#532: hold 'grow' on Files toward Ptyxis (different containers), then release."""
    a, b, c = h.nested_layout((ptyxis, files, editor))
    h.ensure_parent_layout(c["id"], "VSPLIT")
    side = h.neighbour_side(h.find(h.windows(), b["id"]), h.find(h.windows(), a["id"]))
    h.hold_keys(b["id"], h.GROW_KEYS[side], 1200, during=shots.later(path("532", name, "during"), 1.5))
    time.sleep(1.5)
    shots.shot(path("532", name, "after"))


def wrong_edge(name):
    """Issue 2: hold 'grow bottom' on the upper window of a stack: the top edge moves instead."""
    a, b, c = h.nested_layout((ptyxis, files, editor))
    h.ensure_parent_layout(c["id"], "VSPLIT")
    b, c = sorted((h.find(h.windows(), b["id"]), h.find(h.windows(), c["id"])), key=lambda w: w["y"])
    h.hold_keys(b["id"], h.GROW_KEYS["bottom"], 900, during=shots.later(path("2", name, "during"), 1.3))


def past_minimum(name):
    """Issue 3: hold 'grow right' on A until B can't shrink any further, and keep holding."""
    h.open_editor()
    h.open_editor()
    a, b = sorted(h.windows(), key=lambda w: w["x"])
    h.hold_keys(a["id"], h.GROW_KEYS["right"], 3500, during=shots.later(path("3", name, "during"), 3.2))
    time.sleep(1.5)
    shots.shot(path("3", name, "after"))


def overflow(name):
    """Issue 4: one more window than fits side by side (tabbed setting on the fixed build)."""
    h.set_forge_setting("auto-split-enabled", False)
    h.set_forge_setting("min-size-overflow", "tabbed")
    width = h.monitor_size()[0]
    for _ in range(width // 368 + 1):
        h.open_editor()
    time.sleep(1.5)
    shots.shot(path("4", name, "after"))


def stale_tab_bar(name):
    """Issue 6: a tab group whose windows all close at once."""
    h.set_forge_setting("auto-split-enabled", False)
    h.open_app("ptyxis", "--new-window")
    h.open_editor()
    h.js(f'(() => {{ {h.WM}.command({{name: "Split", orientation: "vertical"}}); return "ok"; }})()')
    time.sleep(0.5)
    h.open_editor()
    h.open_editor()
    h.js(f'(() => {{ {h.WM}.command({{name: "LayoutTabbedToggle"}}); return "ok"; }})()')
    time.sleep(1.0)
    shots.shot(path("6", name, "before"))
    editors = [w["id"] for w in h.windows()][1:]
    ids = ", ".join(str(i) for i in editors)
    h.js(f"""(() => {{ global.display.list_all_windows().filter(w => [{ids}].includes(w.get_id()))
        .forEach(w => w.delete(global.get_current_time())); return "ok"; }})()""")
    time.sleep(2.0)
    shots.shot(path("6", name, "after"))


def nested_same_direction(name):
    """Issue 7: HSPLIT[A, HSPLIT[B, C]]: drag B's left edge; C should keep its size."""
    a, b, c = h.nested_layout((ptyxis, files, editor))
    h.ensure_parent_layout(a["id"], "HSPLIT")
    h.ensure_parent_layout(c["id"], "HSPLIT")
    shots.shot(path("7", name, "before"))
    h.drag_edge(b["id"], "left", -300, steps=30, step_ms=50)
    time.sleep(1.5)
    shots.shot(path("7", name, "after"))


def slow_app(name):
    """Slow app: hold 'grow left' on B while its app is frozen for 0.8 s; capture after it resumes."""
    a, b, c = h.nested_layout()
    h.ensure_parent_layout(c["id"], "VSPLIT")
    stall = h.stall_app(b["id"], 0.7, 0.8)

    def during():
        stall()
        time.sleep(0.4)
        shots.shot(path("9", name, "after-resume"))
    h.hold_keys(b["id"], h.GROW_KEYS["left"], 2400, during=during)


SHOTS = {"1": cross_container_drag, "532": held_key_cross_container, "2": wrong_edge, "3": past_minimum,
         "4": overflow, "6": stale_tab_bar, "7": nested_same_direction, "9": slow_app}

# Captions for the composed before/after images: (moment, caption on main, caption with the fix)
COMPOSE = {
    "1": [("during", "main: dragging - Ptyxis doesn't follow", "fix: Ptyxis follows the drag"),
          ("after", "main: after release - snapped back", "fix: after release - stays")],
    "532": [("during", "main: key held", "fix: key held"),
            ("after", "main: after release - snapped back", "fix: after release - stays")],
    "2": [("during", "main: 'grow bottom' moves the TOP edge", "fix: the bottom edge moves")],
    "3": [("during", "main: still held - pushed off-screen", "fix: stops at the minimum"),
          ("after", "main: after release", "fix: after release")],
    "4": [("after", "main: 6 windows overlap / off-screen", "fix (Tabbed): extra windows as tabs")],
    "6": [("after", "main: tab bar left behind", "fix: gone")],
    "7": [("after", "without fix: the right window grew too", "fix: only the dragged edge moved")],
    "9": [("after-resume", "main: app resumed, window still shifted", "fix: app resumed, window in place")],
}


def compose(bug):
    for moment, cap_main, cap_fix in COMPOSE[bug]:
        before, after = path(bug, "main", moment), path(bug, "fix", moment)
        if os.path.exists(before) and os.path.exists(after):
            dst = os.path.join(OUT, f"{bug}-{moment}-before-after.png")
            shots.side_by_side(dst, [(before, cap_main), (after, cap_fix)])
            print("wrote", dst)


def main():
    if sys.argv[1:2] == ["--compose"]:
        compose(sys.argv[2])
        return
    bug, name = sys.argv[1], sys.argv[2]
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    os.makedirs(OUT, exist_ok=True)
    SHOTS[bug](name)
    print("captured", bug, name)


main()
