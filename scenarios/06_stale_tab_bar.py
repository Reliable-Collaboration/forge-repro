#!/usr/bin/env python3
"""Issue 6: a tab bar stays on screen after all of a tabbed container's windows close at once.

With auto-exit-tabbed (default on), closing the second-to-last tab turns the container back into
a split; when the last window closes, the emptied container is removed, but its tab bar is only
destroyed for containers that are still tabbed. Closing one window at a time hides the bar in the
render in between; closing them together (quitting an app with several windows) leaves it.

Run on a fresh sandbox:  sandbox/launch.sh && scenarios/06_stale_tab_bar.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402

WM = h.WM


def tab_bars():
    """Visible Forge tab bars that still show tabs: [x, y, width, tabs]."""
    return json.loads(h.js("""JSON.stringify(global.window_group.get_children()
        .filter(c => c.type === "forge-deco" && c.visible && c.get_n_children() > 0)
        .map(c => [Math.round(c.x), Math.round(c.y), Math.round(c.width), c.get_n_children()]))"""))


def tabbed_group():
    """A | TABBED[B, C, D]; returns the ids of B, C, D."""
    before = {w["id"] for w in h.windows()}
    h.open_editor()
    h.js(f'(() => {{ {WM}.command({{name: "Split", orientation: "vertical"}}); return "ok"; }})()')
    time.sleep(0.5)
    h.open_editor()
    h.open_editor()
    h.js(f'(() => {{ {WM}.command({{name: "LayoutTabbedToggle"}}); return "ok"; }})()')
    time.sleep(1.0)
    return [w["id"] for w in h.windows() if w["id"] not in before]


def close(ids, together):
    lst = ", ".join(str(i) for i in ids)
    if together:
        h.js(f"""(() => {{ global.display.list_all_windows().filter(w => [{lst}].includes(w.get_id()))
            .forEach(w => w.delete(global.get_current_time())); return "ok"; }})()""")
        time.sleep(2.0)
    else:
        for i in ids:
            h.js(f"""(() => {{ global.display.list_all_windows().find(w => w.get_id() === {i})
                .delete(global.get_current_time()); return "ok"; }})()""")
            time.sleep(1.2)


def check(name, what):
    bars = tab_bars()
    ok = not bars
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {what}: visible tab bars {bars}")
    return ok


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    h.set_forge_setting("auto-split-enabled", False)
    h.open_editor()                          # A stays open throughout
    r = []
    print("control: close the tabbed windows one at a time")
    ids = tabbed_group()
    print(f"          tree: {h.tree_summary()}  tab bars: {tab_bars()}")
    close(ids, together=False)
    r.append(check("6.1", "after closing 3 tabs one by one"))
    print("bug: close the tabbed windows together (e.g. quitting an app with several windows)")
    ids = tabbed_group()
    print(f"          tree: {h.tree_summary()}  tab bars: {tab_bars()}")
    close(ids, together=True)
    r.append(check("6.2", "after closing 3 tabs at once"))
    h.open_editor()
    r.append(check("6.3", "after opening another window"))
    sys.exit(h.summary(r))


main()
