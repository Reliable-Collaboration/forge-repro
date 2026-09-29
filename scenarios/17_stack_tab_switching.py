#!/usr/bin/env python3
"""Stacked and tabbed groups: toggling them, and seeing and reaching their windows.

Driven with Forge's own shortcuts (Super+Shift+S stacked, Super+Shift+T tabbed, Super+H/J/K/L focus).

  17.1  stacking a container and toggling it back keeps its split direction (VSPLIT stays VSPLIT)
  17.2  the same for tabs
  17.3  in a stack, every window can be found: with focus on the first window, the stack shows a
        title list with one row per window, the focused window is on top, and no window covers
        the list (i3-style); none is hidden without a trace
  17.4  switching from a stack to a tab group and back leaves no empty tab bar behind
  17.5  moving focus into a stack from outside returns to the window last used there (#230)
  17.6  clicking a window's row in a stack's title list focuses that window
  17.7  the same as 17.5 for a tab group
  17.8  the close button on a stack's row closes that window
  17.9  with title bars turned off (showtab-decoration-enabled), stacks keep the old cascade, no list
  17.10 if the window last used in a group is closed, focus coming back still lands in the group
  17.11 a stack holding a container (not only windows) keeps the cascade: no title list

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


def visible_strip(wid):  # noqa: kept for diagnostics
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


def title_list(con_wid):
    """The shown title bar of the group holding `con_wid`: rows (tabs) and rect, or None."""
    return json.loads(h.js(f"""JSON.stringify((() => {{
        const n = {h.WM}.tree.getNodeByType("WINDOW").find(n => n.nodeValue.get_id() === {con_wid});
        const d = n.parentNode.decoration;
        if (!d || !d.visible || d.width === 0 || d.height === 0) return null;
        const rows = d.get_children().filter(c => c.visible).map(c => {{
            const [x, y] = c.get_transformed_position();
            return [Math.round(x), Math.round(y), Math.round(c.width), Math.round(c.height),
                    c.has_style_class_name("window-tabbed-tab-active")]; }});
        const [x, y] = d.get_transformed_position();
        return {{rows, rect: [Math.round(x), Math.round(y), Math.round(d.width), Math.round(d.height)]}};
    }})())"""))


def click(x, y):
    h.js(f"""(() => {{ const dev = global.stage.context.get_backend().get_default_seat().create_virtual_device(0);
        const t = GLib.get_monotonic_time();
        dev.notify_absolute_motion(t, {x}, {y}); dev.notify_button(t + 1000, 1, 1); dev.notify_button(t + 2000, 1, 0);
        return "ok"; }})()""")
    time.sleep(1.0)
    h.settle()


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
        ok = mid in ("STACKED", "TABBED") and after == before     # the toggle happened, and was undone
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: {toggle} twice: {before} -> {mid} -> {after}")
        r.append(ok)
        done()

    a, ws = column(3)
    activate(ws[0]["id"])
    key("con-stacked-layout-toggle")
    order = group_of(ws[0]["id"])[1]
    activate(order[0])
    tl = title_list(order[0])
    rows = len(tl["rows"]) if tl else 0
    top = h.js("""global.display.sort_windows_by_stacking(global.display.list_all_windows()
        .filter(w => w.get_workspace() === global.workspace_manager.get_active_workspace())).at(-1).get_id()""")
    list_bottom = tl["rect"][1] + tl["rect"][3] if tl else None
    covering = [w["id"] % 1000 for w in h.windows() if tl and w["id"] in order and w["y"] < list_bottom - 2]
    highlighted = [i for i, row in enumerate(tl["rows"]) if row[4]] if tl else []
    inside = tl and all(r_[1] + r_[3] <= list_bottom + 1 for r_ in tl["rows"])
    ok = rows == len(order) and top == order[0] and not covering and highlighted == [0] and inside
    print(f"  {'PASS' if ok else 'FAIL'}  17.3: stack of {len(order)}, focus on the first: title list rows {rows}, "
          f"focused on top: {top == order[0]}, windows over the list: {covering}, highlighted rows: "
          f"{highlighted} (expected [0]), rows inside the list: {inside}")
    r.append(ok)
    if tl and rows == len(order):
        x, y, w, hh, _ = tl["rows"][2]                      # the third window's row
        click(x + w // 2, y + hh // 2)
        ok = focus() == order[2]
        print(f"  {'PASS' if ok else 'FAIL'}  17.6: click the third row: focus {focus() % 1000} (expected {order[2] % 1000})")
    else:
        ok = False
        print("  FAIL  17.6: no title list to click")
    r.append(ok)
    activate(order[0])

    key("con-tabbed-layout-toggle")
    key("con-stacked-layout-toggle")
    bars = json.loads(h.js(f"""JSON.stringify(global.window_group.get_children()
        .filter(c => c.type === "forge-deco" && c.visible && c.width > 0 && c.height > 0)
        .map(c => [c.get_n_children(), {h.WM}.tree.getNodeByType("CON").includes(c.parentNode) ? c.parentNode.layout : "gone"]))"""))
    # A bar is right on a tab or stack group that shows rows (a stack's title list is one too);
    # stray if its container is gone, is no group, or the bar is empty
    stray = [b for b in bars if b[1] not in ("TABBED", "STACKED") or b[0] == 0]
    ok = not stray
    print(f"  {'PASS' if ok else 'FAIL'}  17.4: stacked -> tabbed -> stacked: stray or empty tab bars left: {stray}")
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

    key("con-tabbed-layout-toggle")          # the same group as tabs
    order = group_of(ws[0]["id"])[1]
    activate(order[1])                       # use the middle tab
    activate(a["id"])                        # then A (a click)
    key("window-focus-right")                # back into the group
    ok = focus() == order[1]
    print(f"  {'PASS' if ok else 'FAIL'}  17.7: tab group: last used the middle tab, then A, Super+L: back on "
          f"{focus() % 1000} (expected {order[1] % 1000})")
    r.append(ok)
    done()

    # 17.8: close a window from its row
    a, ws = column(3)
    activate(ws[0]["id"])
    key("con-stacked-layout-toggle")
    order = group_of(ws[0]["id"])[1]
    tl = title_list(order[0])
    if tl and len(tl["rows"]) == 3:
        x, y, w, hh, _ = tl["rows"][1]
        click(x + w - hh // 2, y + hh // 2)                 # the close button at the row's right end
        time.sleep(1.0)
        left = group_of(order[0])[1]
        ok = order[1] not in left and len(left) == 2
        print(f"  {'PASS' if ok else 'FAIL'}  17.8: close button on row 2: stack now {[i % 1000 for i in left]} "
              f"(expected {order[1] % 1000} gone)")
    else:
        ok = False
        print("  FAIL  17.8: no title list")
    r.append(ok)

    # 17.10: the last-used window of the stack is closed, then focus comes back from A
    left = group_of(order[0])[1]
    activate(left[0])
    activate(a["id"])
    h.js(f"""(() => {{ global.display.list_all_windows().find(w => w.get_id() === {left[0]})
        .delete(global.get_current_time()); return "ok"; }})()""")
    time.sleep(1.5)
    h.settle()
    activate(a["id"])
    key("window-focus-right")
    ok = focus() in group_of(left[1])[1]
    print(f"  {'PASS' if ok else 'FAIL'}  17.10: last-used window closed, Super+L from A: focus {focus() % 1000} "
          f"(expected a window of the stack)")
    r.append(ok)
    done()

    # 17.9: title bars off: the old cascade, no list
    h.set_forge_setting("showtab-decoration-enabled", False)
    a, ws = column(3)
    activate(ws[0]["id"])
    key("con-stacked-layout-toggle")
    order = group_of(ws[0]["id"])[1]
    tops = sorted(h.find(h.windows(), i)["y"] for i in order)
    steps = [b - a_ for a_, b in zip(tops, tops[1:])]
    ok = title_list(order[0]) is None and len(set(steps)) == 1 and steps[0] > 0
    print(f"  {'PASS' if ok else 'FAIL'}  17.9: title bars off: list shown: {title_list(order[0]) is not None}, "
          f"window tops {tops} (a cascade: equal steps)")
    r.append(ok)
    h.set_forge_setting("showtab-decoration-enabled", True)
    done()

    # 17.11: STACKED[W1, HSPLIT[W2, W3]]: a container has no title row, so no list
    a, ws = column(2)
    command(ws[1]["id"], '{name: "Split", orientation: "horizontal"}')
    activate(ws[1]["id"])
    new_window()                                        # joins W2's new container
    activate(ws[0]["id"])
    key("con-stacked-layout-toggle")
    print(f"          layout: {h.tree_summary()}")
    tops = sorted({w["y"] for w in h.windows() if w["id"] != a["id"]})
    ok = title_list(ws[0]["id"]) is None and len(tops) >= 2
    print(f"  {'PASS' if ok else 'FAIL'}  17.11: stack with a container: list shown: "
          f"{title_list(ws[0]['id']) is not None}, window tops {tops} (a cascade)")
    r.append(ok)
    sys.exit(h.summary(r))


main()
