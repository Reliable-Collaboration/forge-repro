#!/usr/bin/env python3
"""Spike: does clipping a window actor also clip input (picking/click focus) in GNOME 50?

Forge is disabled for the spike; windows are placed by hand:
  B: frame x 900..1900 (below)      A: frame x 20..1020 (above, focused)
Click at x=960 (inside both frames). Unclipped -> A expected. With A's actor clipped to frame
x < 880 -> if picking honours the clip, the click lands on B.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.expanduser("~/working/forge-repro/lib"))
import harness as h  # noqa: E402

RUN = os.path.expanduser("~/working/forge-repro/sandbox/run-in-sandbox.sh")


def wins():
    return json.loads(h.js("""JSON.stringify(global.display.list_all_windows().filter(w => w.get_monitor() === 0 && !w.skip_taskbar)
        .map(w => { const f = w.get_frame_rect(); return {id: w.get_id(), cls: w.get_wm_class(),
          x11: w.get_client_type() === Meta.WindowClientType.X11, x: f.x, y: f.y, w: f.width, h: f.height}; }))"""))


def launch(argv, x11=False):
    before = {w["id"] for w in wins()}
    env = None
    cmd = [RUN, *argv]
    if x11:
        xa = h.js('GLib.getenv("XAUTHORITY")'); dpy = h.js('GLib.getenv("DISPLAY")')
        cmd = [RUN, "env", f"DISPLAY={dpy}", f"XAUTHORITY={xa}", "GDK_BACKEND=x11", *argv]
    h.park_pointer()
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                     start_new_session=True, env=env)
    for _ in range(60):
        time.sleep(0.25)
        new = [w for w in wins() if w["id"] not in before]
        if new:
            time.sleep(0.8)
            return new[0]["id"]
    raise RuntimeError(f"{argv} did not open")


def place(wid, x, y, w, hh):
    h.js(f"""(() => {{ const m = global.display.list_all_windows().find(w => w.get_id() === {wid});
        m.move_resize_frame(true, {x}, {y}, {w}, {hh}); return "ok"; }})()""")


def raise_focus(wid):
    h.js(f"""(() => {{ const m = global.display.list_all_windows().find(w => w.get_id() === {wid});
        m.activate(global.get_current_time()); return "ok"; }})()""")


def clip(wid, right_edge):
    """Clip the window actor so nothing right of stage x=right_edge is drawn (None = unclip)."""
    if right_edge is None:
        code = "a.remove_clip();"
    else:
        code = f"a.set_clip(0, 0, {right_edge} - a.x, a.height);"
    h.js(f"""(() => {{ const m = global.display.list_all_windows().find(w => w.get_id() === {wid});
        const a = m.get_compositor_private(); {code} return "ok"; }})()""")


def pick_and_click(x, y):
    """Return (window picked by the stage at x,y, focused window after a real virtual click)."""
    return h.js(f"""(() => {{
        let act = global.stage.get_actor_at_pos(1 /* CLUTTER_PICK_REACTIVE */, {x}, {y});
        let picked = null;
        for (let p = act; p; p = p.get_parent()) if (p instanceof Meta.WindowActor) {{ picked = p.get_meta_window().get_id(); break; }}
        const d = global.stage.context.get_backend().get_default_seat().create_virtual_device(0);
        const t = GLib.get_monotonic_time();
        d.notify_absolute_motion(t, {x}, {y});
        d.notify_button(t + 1000, 1, 1);
        d.notify_button(t + 2000, 1, 0);
        globalThis.__pc = picked;
        return "ok"; }})()""") and (time.sleep(0.6) or (h.js("globalThis.__pc"),
                                                          h.js("global.display.focus_window?.get_id() ?? null")))


def trial(label, top, bottom, clip_right):
    raise_focus(bottom)
    raise_focus(top)
    time.sleep(0.4)
    clip(top, clip_right)
    time.sleep(0.3)
    picked, focused = pick_and_click(960, 540)
    who = lambda i: "A(top)" if i == top else "B(below)" if i == bottom else str(i)
    print(f"  {label}: stage pick -> {who(picked)}, focus after click -> {who(focused)}")
    clip(top, None)
    return picked, focused


def main():
    h.js('(() => { Main.extensionManager.disableExtension("forge@jmmaranan.com"); return "ok"; })()')
    time.sleep(1)
    b = launch(["gnome-text-editor", "--standalone"])
    a = launch(["gnome-text-editor", "--standalone"])
    x = launch(["xmessage", "-geometry", "1000x500", "X11 test window " * 20], x11=True)
    for w in wins():
        print("  window", w)
    place(b, 900, 100, 1000, 800)
    place(a, 20, 100, 1000, 800)
    place(x, 20, 100, 1000, 800)
    time.sleep(1)
    for w in wins():
        print("  placed", w)
    print("Wayland window A over B:")
    trial("unclipped", a, b, None)
    trial("A clipped at x<880", a, b, 880)
    print("X11 window (xmessage) over B:")
    trial("unclipped", x, b, None)
    trial("X clipped at x<880", x, b, 880)

    print("Placement partly off the monitor (A to x=-300):")
    place(a, -300, 100, 1000, 800)
    time.sleep(0.8)
    print("  ", [w for w in wins() if w["id"] == a])


main()
