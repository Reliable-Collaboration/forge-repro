#!/usr/bin/env python3
"""Spike part 2 (reuses the windows placed by clip_spike.py): separate pointer motion,
hover target (stage device actor) and click, with a paint in between."""
import json, os, sys, time
sys.path.insert(0, os.path.expanduser("~/working/forge-repro/lib"))
import harness as h

h.js("""(() => { globalThis.__dev = global.stage.context.get_backend().get_default_seat().create_virtual_device(0); return "ok"; })()""")
wins = json.loads(h.js("""JSON.stringify(global.display.list_all_windows().filter(w => w.get_monitor() === 0)
    .map(w => { const f = w.get_frame_rect(); return {id: w.get_id(), cls: w.get_wm_class(), x: f.x}; }))"""))
B = next(w["id"] for w in wins if w["cls"] == "org.gnome.TextEditor" and w["x"] == 900)
A = next(w["id"] for w in wins if w["cls"] == "org.gnome.TextEditor" and w["id"] != B)
X = next(w["id"] for w in wins if w["cls"] == "Xmessage")
W = lambda i: f"global.display.list_all_windows().find(w => w.get_id() === {i})"
name = {A: "A", B: "B", X: "X"}

def act(i): h.js(f'(() => {{ {W(i)}.activate(global.get_current_time()); return "ok"; }})()')
def place(i, x): h.js(f'(() => {{ {W(i)}.move_resize_frame(true, {x}, 100, 1000, 800); return "ok"; }})()')
def clip(i, right):
    body = "a.remove_clip();" if right is None else f"a.set_clip(0, 0, {right} - a.x, a.height);"
    h.js(f'(() => {{ const a = {W(i)}.get_compositor_private(); {body} return "ok"; }})()')
def move(x, y):
    h.js(f'(() => {{ __dev.notify_absolute_motion(GLib.get_monotonic_time(), {x}, {y}); return "ok"; }})()')
def hover():
    """Window of the actor Clutter delivered the last button press to (captured-event)."""
    return h.js("globalThis.__press ?? null")
def click():
    h.js("""(() => { globalThis.__press = null;
        const id = global.stage.connect('captured-event', (_s, ev) => {
            if (ev.type() === 5 /* BUTTON_PRESS */ && globalThis.__press === null) {
                let a = global.stage.get_event_actor(ev);
                for (let p = a; p; p = p.get_parent()) if (p instanceof Meta.WindowActor) { globalThis.__press = p.get_meta_window().get_id(); break; }
                if (globalThis.__press === null) globalThis.__press = String(a);
                global.stage.disconnect(id);
            }
            return false; });
        return "ok"; })()""")
    h.js('(() => { const t = GLib.get_monotonic_time(); __dev.notify_button(t, 1, 1); __dev.notify_button(t + 50000, 1, 0); return "ok"; })()')
def focus(): return h.js("global.display.focus_window?.get_id() ?? null")

def trial(label, top, clip_right, x):
    move(1700, 950)          # park the pointer on B-only area
    act(B); act(top); time.sleep(0.4)
    clip(top, clip_right); time.sleep(0.5)
    move(x, 540); time.sleep(0.4)
    click(); time.sleep(0.6); hv = hover(); fc = focus()
    clip(top, None)
    print(f"  {label:32s} x={x}: press delivered to -> {name.get(hv, hv)}, focus after click -> {name.get(fc, fc)}")

place(A, 20); place(X, 20); time.sleep(0.5)
print("control: click on B-only area focuses B")
trial("A on top, unclipped", A, None, 1500)
print("Wayland A over B")
trial("A on top, unclipped", A, None, 960)
trial("A on top, clipped at 880", A, 880, 960)
print("X11 xmessage over B")
trial("X on top, unclipped", X, None, 960)
trial("X on top, clipped at 880", X, 880, 960)
