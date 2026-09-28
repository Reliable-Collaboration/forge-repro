#!/usr/bin/env python3
"""Stacked and tabbed groups: toggling them, and seeing and reaching their windows.

Driven with Forge's own shortcuts (Super+Shift+S stacked, Super+Shift+T tabbed, Super+H/J/K/L focus).

  17.1  stacking a container and toggling it back keeps its split direction (VSPLIT stays VSPLIT)
  17.2  the same for tabs
  17.3  in a stack, every window can be seen: with focus on the first window, each other window
        still shows a strip (i3-style stacks show every title); none is hidden entirely
  17.4  switching from a stack to a tab group and back leaves no empty tab bar behind
  17.5  moving focus into a stack from outside returns to the window last used there (#230)

Run on a fresh sandbox:  sandbox/launch.sh && scenarios/17_stack_tab_switching.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402


def activate(wid):
    h.js(f"""(() => {{ global.display.list_all_windows().find(w => w.get_id() === {wid})
        .activate(global.get_current_time()); return "ok"; }})()""")
    time.sleep(0.8)
    h.settle()


def focus():
    return h.js("global.display.focus_window.get_id()")


def key(binding):
    h.hold_keys(focus(), h.chord(binding), 0)
    time.sleep(1.0)
    h.settle()


def new_window():
    known = {w["id"] for w in h.windows()}
    h.open_editor()
    return next(w for w in h.windows() if w["id"] not in known)


def command(wid, cmd):
    activate(wid)
    h.js(f'(() => {{ {h.WM}.command({cmd}); return "ok"; }})()')
    time.sleep(1.0)
    h.settle()


def group_of(wid):
    """The layout of a window's container and its windows, in order."""
    return json.loads(h.js(f"""JSON.stringify((() => {{
        const n = {h.WM}.tree.getNodeByType("WINDOW").find(n => n.nodeValue.get_id() === {wid});
        return [n.parentNode.layout, n.parentNode.childNodes.filter(c => c.isWindow()).map(c => c.nodeValue.get_id())];
    }})())"""))


def column(n):
    """A | CON[w1..wn], the container split vertically. Returns (A, [w1..wn])."""
    a = new_window()
    first = new_window()
    h.ensure_parent_layout(a["id"], "HSPLIT")
    command(first["id"], '{name: "Split", orientation: "vertical"}')
    ws = [first]
    for _ in range(n - 1):
        activate(ws[-1]["id"])
        ws.append(new_window())
    h.ensure_parent_layout(first["id"], "VSPLIT")
    return a, ws


def visible_strip(wid):
    """Rows of the window that no other window covers (px): 0 means hidden entirely."""
    return h.js(f"""(() => {{
        const ws = global.workspace_manager.get_active_workspace();
        const wins = global.display.sort_windows_by_stacking(global.display.list_all_windows()
            .filter(w => w.get_workspace() === ws && !w.minimized));
        const i = wins.findIndex(w => w.get_id() === {wid});
        const f = wins[i].get_frame_rect();
        let top = f.y, bottom = f.y + f.height;      // visible band, narrowed by windows above it
        for (const o of wins.slice(i + 1)) {{
            const g = o.get_frame_rect();
            if (g.x >= f.x + f.width || g.x + g.width <= f.x) continue;
            if (g.y <= top && g.y + g.height >= bottom) return 0;
            if (g.y <= top && g.y + g.height > top) top = g.y + g.height;
            if (g.y + g.height >= bottom && g.y < bottom) bottom = g.y;
        }}
        return Math.max(0, bottom - top);
    }})()""")


def done():
    h.close_windows()
    time.sleep(1.0)


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    h.set_forge_setting("auto-split-enabled", False)
    r = []

    for name, toggle in (("17.1", "con-stacked-layout-toggle"), ("17.2", "con-tabbed-layout-toggle")):
        a, ws = column(2)
        before = group_of(ws[0]["id"])[0]
        activate(ws[0]["id"])
        key(toggle)
        mid = group_of(ws[0]["id"])[0]
        key(toggle)
        after = group_of(ws[0]["id"])[0]
        ok = after == before
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {toggle} twice: {before} -> {mid} -> {after}")
        r.append(ok)
        done()

    a, ws = column(3)
    activate(ws[0]["id"])
    key("con-stacked-layout-toggle")
    order = group_of(ws[0]["id"])[1]
    activate(order[0])
    strips = {i % 1000: visible_strip(i) for i in order}
    ok = all(v > 0 for v in strips.values())
    print(f"  {'PASS' if ok else 'FAIL'}  17.3: stack of {len(order)}, focus on the first: visible rows per window {strips}")
    r.append(ok)

    key("con-tabbed-layout-toggle")
    key("con-stacked-layout-toggle")
    bars = json.loads(h.js(f"""JSON.stringify(global.window_group.get_children()
        .filter(c => c.type === "forge-deco" && c.visible && c.width > 0 && c.height > 0)
        .map(c => [c.get_n_children(), {h.WM}.tree.getNodeByType("CON").includes(c.parentNode) ? c.parentNode.layout : "gone"]))"""))
    stray = [b for b in bars if b[1] != "TABBED"]
    ok = not stray
    print(f"  {'PASS' if ok else 'FAIL'}  17.4: stacked -> tabbed -> stacked: tab bars left that belong to no tabbed "
          f"group: {stray}")
    r.append(ok)

    order = group_of(ws[0]["id"])[1]
    activate(order[0])                      # use the first window of the stack
    key("window-focus-left")                # to A
    left_ok = focus() == a["id"]
    key("window-focus-right")               # back into the stack
    ok = left_ok and focus() == order[0]
    print(f"  {'PASS' if ok else 'FAIL'}  17.5: focus the stack's first window, Super+H, Super+L: back on "
          f"{focus() % 1000} (expected {order[0] % 1000}, the window last used there)")
    r.append(ok)
    sys.exit(h.summary(r))


main()
