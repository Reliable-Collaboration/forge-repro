#!/usr/bin/env python3
"""The split direction hint appears (forge-ext/forge#407).

With "split border" on (split-border-toggle), a window alone in a container that will split
(after Super+V or Super+Z) gets a coloured border on the side where the next window goes. The
condition that shows it tested `!maximized` where `maximized` is a function (so always false,
since 2023), and the hint never appeared.

  21.1  A | B; Super+V on B (B alone in a vertical split): B shows the vertical split hint
  21.2  Super+Z (horizontal) on the same: the hint turns horizontal
  21.3  a second window joins B's container: no hint (it is no longer alone)

Run on a fresh sandbox:  sandbox/launch.sh && scenarios/21_split_hint.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402


def new_editor():
    known = {w["id"] for w in h.windows()}
    h.open_editor()
    return next(w for w in h.windows() if w["id"] not in known)


def command(wid, cmd):
    h.js(f"""(() => {{ global.display.list_all_windows().find(w => w.get_id() === {wid})
        .activate(global.get_current_time()); {h.WM}.command({cmd}); return "ok"; }})()""")
    time.sleep(1.0)
    h.settle()


def hint(wid):
    """The split hint of window `wid`: [visible, direction, x, y, w, h] or None."""
    return json.loads(h.js(f"""JSON.stringify((() => {{
        const w = global.display.list_all_windows().find(w => w.get_id() === {wid});
        const b = w?.get_compositor_private()?.splitBorder;
        if (!b) return null;
        const dir = b.has_style_class_name("window-split-vertical") ? "vertical"
            : b.has_style_class_name("window-split-horizontal") ? "horizontal" : "none";
        return [b.visible, dir, b.x, b.y, b.width, b.height]; }})())"""))


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    h.set_forge_setting("auto-split-enabled", False)
    h.set_forge_setting("split-border-toggle", True)
    h.set_forge_setting("focus-border-toggle", True)
    a = new_editor()
    b = new_editor()
    h.ensure_parent_layout(a["id"], "HSPLIT")
    r = []

    command(b["id"], '{name: "Split", orientation: "vertical"}')
    got = hint(b["id"])
    ok = bool(got) and got[0] and got[1] == "vertical"
    print(f"  {'PASS' if ok else 'FAIL'}  21.1 Super+V on B: split hint {got} (expected visible, vertical); "
          f"layout {h.tree_summary()}")
    r.append(ok)

    command(b["id"], '{name: "Split", orientation: "horizontal"}')
    got = hint(b["id"])
    ok = bool(got) and got[0] and got[1] == "horizontal"
    print(f"  {'PASS' if ok else 'FAIL'}  21.2 then Super+Z: split hint {got} (expected visible, horizontal)")
    r.append(ok)

    command(b["id"], '{name: "Split", orientation: "vertical"}')
    h.js(f"""(() => {{ global.display.list_all_windows().find(w => w.get_id() === {b["id"]})
        .activate(global.get_current_time()); return "ok"; }})()""")
    time.sleep(0.5)
    c = new_editor()                                   # joins B's container
    h.js(f"""(() => {{ global.display.list_all_windows().find(w => w.get_id() === {b["id"]})
        .activate(global.get_current_time()); return "ok"; }})()""")
    time.sleep(1.0)
    got = hint(b["id"])
    ok = not got or not got[0]
    print(f"  {'PASS' if ok else 'FAIL'}  21.3 a window joined B's container: split hint {got} (expected none); "
          f"layout {h.tree_summary()} (C {c['id'] % 1000})")
    r.append(ok)
    h.close_windows()
    sys.exit(h.summary(r))


main()
