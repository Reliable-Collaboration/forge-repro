#!/usr/bin/env python3
"""Moving a window out of its container can leave its old size share behind.

Forge sizes the windows of a split by their shares (percents), which must add up to 100%. When
"move window up/down" (or left/right) takes a window out of its container to the workspace level
(because there's nothing in that direction to move into), the moved window keeps the share it had
in its old container, and the workspace level's shares aren't reset. The shares there then add up
to more than 100% and the windows overlap or run off-screen.

Found by the randomized stress test (09_fuzz.py, seed 303 on the real-size profile).

Run on a fresh sandbox:  sandbox/launch.sh && scenarios/14_move_out_shares.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402


def command(win_id, cmd):
    h.js(f"""(() => {{ global.display.list_all_windows().find(w => w.get_id() === {win_id})
        .activate(global.get_current_time()); {h.WM}.command({cmd}); return "ok"; }})()""")
    time.sleep(1.0)


def setup():
    """A | B at unequal shares, then A and C together in a container, also at unequal shares:
    HSPLIT[HSPLIT[A, C], B]. Returns (A, B, C)."""
    h.open_editor()
    h.open_editor()
    a, b = sorted(h.windows(), key=lambda w: w["x"])
    h.drag_edge(a["id"], "right", h.monitor_size()[0] // 8)
    command(a["id"], '{name: "Split", orientation: "horizontal"}')
    h.open_editor()                    # joins A's container, next to A
    c = next(w for w in h.windows() if w["id"] not in (a["id"], b["id"]))
    h.drag_edge(a["id"], "right", -h.monitor_size()[0] // 16)
    return a, b, c


def case(name, direction):
    a, b, c = setup()
    print(f"before: {h.tree_summary()}")
    command(c["id"], f'{{name: "Move", direction: "{direction}"}}')
    ok = h.layout_check(name, f"move C {direction.lower()} out of its container: shares still add up, "
                              "no overlap or off-screen")
    print(f"          after: {h.tree_summary()}")
    h.close_windows()
    time.sleep(1.0)
    return ok


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    h.set_forge_setting("auto-split-enabled", False)   # new windows join the focused window's split
    r = [case("14.1", "Up"), case("14.2", "Down")]
    sys.exit(h.summary(r))


main()
