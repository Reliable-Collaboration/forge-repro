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


def overlaps():
    """Overlapping regions between windows on this workspace: [(x, y, w, h)]."""
    ws = h.windows()
    out = []
    for i, a in enumerate(ws):
        for b in ws[i + 1:]:
            x0, y0 = max(a["x"], b["x"]), max(a["y"], b["y"])
            x1, y1 = min(a["x"] + a["w"], b["x"] + b["w"]), min(a["y"] + a["h"], b["y"] + b["h"])
            if x1 - x0 > 2 and y1 - y0 > 2:
                out.append((x0, y0, x1 - x0, y1 - y0))
    return out


def min_size_fits(name):
    """Issue 4: the middle window is at its minimum, then the gaps grow: it must keep its minimum
    and its neighbours give up the space, instead of it overlapping them."""
    h.set_forge_setting("auto-split-enabled", False)
    for _ in range(3):
        h.open_editor()
    a, b, c = sorted(h.windows(), key=lambda w: w["x"])
    h.drag_edge(a["id"], "right", h.monitor_size()[0] // 3, steps=30)
    time.sleep(1.0)
    h.set_forge_setting("window-gap-size-increment", 6)
    time.sleep(1.5)
    raw = shots.shot(path("4", name, "after-raw"))
    # Mark where a window sticks out of the place Forge laid it out at
    places = h.js(f"""JSON.stringify(({h.HERE}?.getNodeByType("WINDOW") ?? []).map(n => {{
        const f = n.nodeValue.get_frame_rect(), r = n.renderRect;
        return r ? [f.x, f.y, f.width, f.height, r.x, r.y, r.width, r.height] : null; }}).filter(Boolean))""")
    boxes = []
    for fx, fy, fw, fh, rx, ry, rw, rh in __import__("json").loads(places):
        if fx + fw > rx + rw + 2:
            boxes.append((rx + rw, fy, fx + fw - rx - rw, fh, RED, "outside its place"))
        if fx < rx - 2:
            boxes.append((fx, fy, rx - fx, fh, RED, "outside its place"))
    shots.annotate(raw, path("4", name, "after"), boxes)


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
         "4": min_size_fits, "6": stale_tab_bar, "7": nested_same_direction, "9": slow_app}

# Captions for the composed before/after images: (moment, caption on main, caption with the fix)
COMPOSE = {
    "1": [("during", "main: dragging - Ptyxis doesn't follow", "fix: Ptyxis follows the drag"),
          ("after", "main: after release - snapped back", "fix: after release - stays")],
    "532": [("during", "main: key held", "fix: key held"),
            ("after", "main: after release - snapped back", "fix: after release - stays")],
    "2": [("during", "main: 'grow bottom' moves the TOP edge", "fix: the bottom edge moves")],
    "3": [("during", "main: still held - pushed off-screen", "fix: stops at the minimum"),
          ("after", "main: after release", "fix: after release")],
    "4": [("after", "main: the middle window sticks out of its place", "fix: it keeps its minimum, the others give way")],
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
