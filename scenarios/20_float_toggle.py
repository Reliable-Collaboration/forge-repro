#!/usr/bin/env python3
"""Float toggle (Super+C) works per window, also for a second window of the same app
(forge-ext/forge#534, #495; it was fixed for #492 and came back).

Forge floats a window by adding a rule to its window overrides (for Super+C, a rule for that
window only). It skipped adding the rule if any float rule for the same app existed, so once one
Text Editor window floated, Super+C on a second one did nothing.

  20.1  two Text Editor windows; Super+C on the first: it floats, the second stays tiled
  20.2  Super+C on the second: it floats too
  20.3  Super+C on the first again: it tiles, the second still floats
  20.4  Super+C on the second again: it tiles
  20.5  Super+C on the first, then "always float" (Super+Shift+C) on the second: the second floats
        and stays floating after the next layout (a single window's rule doesn't count as the app's)
  20.6  "always float" off again on the second: it tiles, and the first (floated on its own with
        Super+C) still floats

Run on a fresh sandbox:  sandbox/launch.sh && scenarios/20_float_toggle.py
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
    return next(w["id"] for w in h.windows() if w["id"] not in known)


def float_toggle(wid, binding="window-toggle-float"):
    """Super+C as Forge's keybinding runs it: the FloatToggle command on the focused window
    (binding "window-toggle-always-float": the FloatClassToggle command, for the whole app)."""
    h.js(f"""(() => {{ global.display.list_all_windows().find(w => w.get_id() === {wid})
        .activate(global.get_current_time()); return "ok"; }})()""")
    time.sleep(0.5)
    h.hold_keys(wid, h.chord(binding), 0)
    time.sleep(1.0)
    h.settle()


def floating(wid):
    return json.loads(h.js(f"""JSON.stringify((() => {{
        const n = {h.WM}.tree.getNodeByType("WINDOW").find(n => n.nodeValue.get_id() === {wid});
        return n ? n.isFloat() : null; }})())"""))


def check(name, a, b, want_a, want_b):
    fa, fb = floating(a), floating(b)
    ok = fa == want_a and fb == want_b
    word = lambda f: "floating" if f else "tiled"  # noqa: E731
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: first {word(fa)} (expected {word(want_a)}), "
          f"second {word(fb)} (expected {word(want_b)})")
    return ok


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    a = new_editor()
    b = new_editor()
    r = []
    float_toggle(a)
    r.append(check("20.1 Super+C on the first", a, b, True, False))
    float_toggle(b)
    r.append(check("20.2 Super+C on the second (same app)", a, b, True, True))
    float_toggle(a)
    r.append(check("20.3 Super+C on the first again", a, b, False, True))
    float_toggle(b)
    r.append(check("20.4 Super+C on the second again", a, b, False, False))
    float_toggle(a)
    float_toggle(b, "window-toggle-always-float")
    h.js(f'(() => {{ {h.WM}.renderTree("test", true); return "ok"; }})()')   # the next layout
    time.sleep(1.0)
    h.settle()
    ok = floating(b) is True
    print(f"  {'PASS' if ok else 'FAIL'}  20.5 'always float' on the second after Super+C on the first: "
          f"second {'floating' if floating(b) else 'tiled'} after the next layout (expected floating)")
    r.append(ok)
    float_toggle(b, "window-toggle-always-float")                         # the app's rule off again
    h.js(f'(() => {{ {h.WM}.renderTree("test", true); return "ok"; }})()')
    time.sleep(1.0)
    h.settle()
    r.append(check("20.6 'always float' off on the second", a, b, True, False))
    h.close_windows()
    sys.exit(h.summary(r))


main()
