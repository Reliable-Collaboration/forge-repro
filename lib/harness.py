"""Shared helpers for driving the nested sandbox gnome-shell (see sandbox/launch.sh).

All calls go to the sandbox's private D-Bus bus. Input is injected with Clutter virtual devices
created *inside* the nested shell, so nothing reaches the host session.
"""
import json
import os
import subprocess
import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "lib")
SANDBOX_DIR = os.environ.get("SANDBOX_DIR") or os.path.join(
    os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "forge-repro", "sandbox")

TOL = 10      # px allowed between an edge's position at release and where it settles
GAP = 8       # Forge's default inter-window gap in these layouts
GAP_TOL = 4
WM = 'Main.extensionManager.lookup("forge@jmmaranan.com").stateObj.extWm'

_bus = None


def bus():
    global _bus
    if _bus is None:
        addr = open(os.path.join(SANDBOX_DIR, "bus-address")).read().strip()
        if not addr.startswith("unix:path=/tmp/dbus-"):
            raise SystemExit(f"refusing: {addr!r} is not a private dbus-run-session bus")
        _bus = Gio.DBusConnection.new_for_address_sync(
            addr, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
    return _bus


def js_raw(code):
    return bus().call_sync("org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell", "Eval",
                           GLib.Variant("(s)", (code,)), GLib.VariantType("(bs)"),
                           Gio.DBusCallFlags.NONE, 20000, None).unpack()


def js(code):
    ok, out = js_raw(code)
    if not ok:
        raise RuntimeError(out)
    return json.loads(out) if out else None


def windows():
    """Tiled windows on monitor 0 with frame geometry, node percent and parent info."""
    return json.loads(js(f"""JSON.stringify({WM}.tree.getNodeByType("WINDOW")
        .filter(n => n.nodeValue.get_monitor() === 0).map(n => {{
            const f = n.nodeValue.get_frame_rect();
            return {{ id: n.nodeValue.get_id(), x: f.x, y: f.y, w: f.width, h: f.height,
                      percent: n.percent ?? 0, playout: n.parentNode.layout,
                      pid: n.parentNode.nodeType === "CON" ? "con" : "top",
                      depth: (() => {{ let d = 0; for (let p = n.parentNode; p; p = p.parentNode) if (p.nodeType === "CON") d++; return d; }})() }}; }}))"""))


def park_pointer():
    """Move the sandbox pointer to the centre of monitor 0 so new windows open there."""
    js("""(() => { const r = global.display.get_monitor_geometry(0);
        const d = global.stage.context.get_backend().get_default_seat().create_virtual_device(0);
        d.notify_absolute_motion(GLib.get_monotonic_time(), r.x + r.width / 2, r.y + r.height / 2);
        return "ok"; })()""")


def open_app(*argv):
    """Open an app inside the sandbox and wait until Forge tiles its window."""
    park_pointer()
    before = len(windows())
    subprocess.Popen([os.path.join(ROOT, "sandbox", "run-in-sandbox.sh"), *argv],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(40):
        time.sleep(0.25)
        if len(windows()) > before:
            time.sleep(1.0)
            return
    raise RuntimeError(f"{argv[0]} window did not appear")


def open_editor():
    open_app("gnome-text-editor", "--standalone")


def run_js_file(name, subs, flag):
    code = open(os.path.join(LIB, name)).read()
    for k, v in subs.items():
        code = code.replace(k, str(v))
    js(code)
    for _ in range(160):
        time.sleep(0.25)
        if js(f"String(globalThis.{flag}?.done)") == "true":
            return json.loads(js(f"JSON.stringify(globalThis.{flag}.log)"))
    raise RuntimeError(f"{name} did not finish")


def find(ws, wid):
    return next(w for w in ws if w["id"] == wid)


def edge(win, side):
    return {"left": win["x"], "right": win["x"] + win["w"], "top": win["y"], "bottom": win["y"] + win["h"]}[side]


OPP = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
HORIZONTAL = {"left", "right"}


def neighbour_side(a, b):
    """Side of window a that faces window b (they must share a border)."""
    for side in ("left", "right", "top", "bottom"):
        if abs(edge(a, side) - edge(b, OPP[side])) < 24:
            return side
    raise ValueError("windows are not adjacent")


def js_errors():
    try:
        return sum("JS ERROR" in l for l in open(os.path.join(SANDBOX_DIR, "nested.log"), errors="replace"))
    except FileNotFoundError:
        return 0


def settle_check(name, moved_id, side, nb_id, expect_edge, tol=TOL):
    """PASS if the moved edge settled near expect_edge and the neighbour sits one gap away."""
    time.sleep(1.0)
    ws = windows()
    m, n = find(ws, moved_id), find(ws, nb_id)
    got = edge(m, side)
    gap = abs(edge(n, OPP[side]) - got)
    ok = abs(got - expect_edge) <= tol and abs(gap - GAP) <= GAP_TOL
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: {side} edge expected ~{expect_edge}, settled {got}; "
          f"gap to neighbour {gap}px")
    return ok


def drag_edge(win_id, side, delta, steps=20, step_ms=40):
    """Press just outside `side` of the window (in the gap) and drag `delta` px across it.
    Returns (edge_before, grabbed: bool, log)."""
    w = find(windows(), win_id)
    e = edge(w, side)
    off = 1 if side in ("right", "bottom") else -1
    if side in HORIZONTAL:
        x, y, dx, dy = e + off, w["y"] + w["h"] // 2, delta, 0
    else:
        x, y, dx, dy = w["x"] + w["w"] // 2, e + off, 0, delta
    log = run_js_file("drag.js", {"__X0__": x, "__Y0__": y, "__DX__": dx, "__DY__": dy,
                                  "__STEPS__": steps, "__STEP_MS__": step_ms}, "__drag")
    return e, any("grab-op-begin" in l for l in log), log


# Forge default keybindings (sandbox uses defaults): grow an edge = window-resize-*-increase
GROW_KEYS = {"right": "0xffe3, 0xffeb, 0x6f",   # Ctrl+Super+O
             "left": "0xffe3, 0xffeb, 0x79",    # Ctrl+Super+Y
             "bottom": "0xffe3, 0xffeb, 0x75",  # Ctrl+Super+U
             "top": "0xffe3, 0xffeb, 0x69"}     # Ctrl+Super+I


def hold_keys(win_id, keys, hold_ms=1000):
    """Focus a window and hold a key chord with a virtual keyboard (real key repeat).
    Returns the timeline log (each line has per-window x,y,w,h,p and resize() call count)."""
    return run_js_file("holdkey.js", {"__WIN__": win_id % 1000, "__KEYS__": keys, "__HOLD_MS__": hold_ms}, "__hk")


def parse_line(line):
    """Parse a timeline line into {id%1000: dict(x,y,w,h,p)} plus 'calls'."""
    out = {}
    if "calls=" in line:
        out["calls"] = int(line.split("calls=")[1].split()[0])
    for tok in line.split(" | ")[1:]:
        if ":" in tok and "=" in tok and not tok.startswith("CON"):
            wid, kv = tok.split(":", 1)
            out[int(wid)] = {k: float(v) for k, v in (p.split("=") for p in kv.split(","))}
    return out


def nested_layout():
    """Open 3 editors => Forge builds [A] + CON[B, C] on monitor 0. Returns (A, B, C)."""
    if windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    for _ in range(3):
        open_editor()
    ws = windows()
    con = [w for w in ws if w["pid"] == "con"]
    top = [w for w in ws if w["pid"] == "top"]
    assert len(con) == 2 and len(top) == 1, f"unexpected layout: {ws}"
    horiz = con[0]["playout"] == "HSPLIT"
    b, c = sorted(con, key=lambda w: w["x"] if horiz else w["y"])
    return top[0], b, c


def summary(results):
    errs = js_errors()
    print(f"sandbox JS errors: {errs}")
    print(f"RESULT: {sum(results)}/{len(results)} passed")
    return 0 if all(results) and errs == 0 else 1
