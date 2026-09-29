#!/usr/bin/env python3
"""Watch sandboxes live: every monitor of each sandbox, in a window on your desktop.

    sandbox/watch.py &                          the sandbox in $SANDBOX_DIR (default)
    sandbox/watch.py sbA sbB sbC &              several sandboxes (names under ~/.cache/forge-repro,
                                                or paths), one window each
    sandbox/watch.py --record DIR sbA sbB &     also record each sandbox session to DIR/*.webm

Each window shows all the sandbox's monitors where they are placed (e.g. side by side in the
two-monitor scenarios), scaled to fit, and the running scenario in its title. It asks each sandbox
shell to screencast its monitors (org.gnome.Mutter.ScreenCast on that sandbox's private bus, never
your session's) and plays the PipeWire streams. Windows stay open across sandbox restarts (each
scenario starts a fresh sandbox) and reconnect automatically. Recordings are named
<sandbox>-<start time in ms>.webm; DIR/index.txt maps them to scenarios (and to the times in the
layout watcher's reports, sandbox/watchdog.py). Close a window or press Ctrl+C to stop.
"""
import argparse
import os
import time

import gi

gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gst, Gtk  # noqa: E402

SC = "org.gnome.Mutter.ScreenCast"
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "forge-repro")
MAX_WIDTH = 1600          # the view is scaled down to at most this wide


def log(*args):
    print(*args, flush=True)


class View:
    """One sandbox: its window, its bus, its streams."""

    def __init__(self, sandbox_dir, record_dir, on_close):
        self.dir = sandbox_dir
        self.name = os.path.basename(sandbox_dir.rstrip("/"))
        self.record_dir = record_dir
        self.addr = self.bus = self.session = self.pipeline = None
        self.recording = None
        self.window = Gtk.Window(title=f"{self.name}: waiting for the sandbox")
        self.window.set_default_size(960, 540)
        self.window.connect("destroy", lambda *_: on_close(self))
        self.waiting = Gtk.Label(label=f"Waiting for sandbox {self.name}…")
        self.window.add(self.waiting)
        self.window.show_all()
        self.scenario = ""
        GLib.timeout_add(1000, self.poll)

    # --- sandbox state ---------------------------------------------------------------------
    def ready_addr(self):
        try:
            addr = open(os.path.join(self.dir, "bus-address")).read().strip()
            log_text = open(os.path.join(self.dir, "nested.log"), errors="replace").read()
        except FileNotFoundError:
            return None
        if not addr.startswith("unix:path=/tmp/dbus-"):
            return None                       # never anything but a sandbox's private bus
        socket = addr.split("unix:path=", 1)[1].split(",", 1)[0]
        if not os.path.exists(socket):
            return None                       # left over from a sandbox that has stopped
        return addr if "GNOME Shell started" in log_text else None

    def call(self, path, iface, method, args, reply, dest=SC):
        return self.bus.call_sync(dest, path, iface, method, args,
                                  GLib.VariantType(reply) if reply else None,
                                  Gio.DBusCallFlags.NONE, 10000, None)

    def monitors(self):
        """[(connector, x, y, width, height)] of the sandbox's monitors, in layout coordinates."""
        state = self.call("/org/gnome/Mutter/DisplayConfig", "org.gnome.Mutter.DisplayConfig",
                          "GetCurrentState", None, None, dest="org.gnome.Mutter.DisplayConfig").unpack()
        sizes = {}
        for (connector, *_), modes, _props in state[1]:
            for mode in modes:
                if mode[6].get("is-current"):
                    sizes[connector] = (mode[1], mode[2])
        out = []
        for x, y, scale, _t, _p, monitors, _props in state[2]:
            for connector, *_ in monitors:
                if connector in sizes:
                    w, hgt = sizes[connector]
                    out.append((connector, x, y, round(w / scale), round(hgt / scale)))
        return out

    # --- connect / disconnect --------------------------------------------------------------
    def poll(self):
        addr = self.ready_addr()
        if addr != self.addr:
            if self.addr:
                self.disconnect("the sandbox stopped or restarted")
            if addr and addr != getattr(self, "failed", None):
                try:
                    self.connect(addr)
                    self.failed = None
                except (GLib.Error, RuntimeError, OSError) as e:
                    log(f"{self.name}: can't show this sandbox yet: {e}")
                    self.disconnect("connect failed")
                    self.failed = addr            # retried when the sandbox restarts
        scenario = ""
        try:
            scenario = open(os.path.join(self.dir, "scenario")).read().strip()
        except FileNotFoundError:
            pass
        if self.addr and scenario != self.scenario:
            self.scenario = scenario
            self.update_title()
            if self.recording:
                with open(os.path.join(self.record_dir, "index.txt"), "a") as f:
                    f.write(f"{os.path.basename(self.recording)} {self.name} {scenario}\n")
        return GLib.SOURCE_CONTINUE

    def update_title(self):
        mons = getattr(self, "mons", [])
        size = " + ".join(f"{w}x{h}" for _c, _x, _y, w, h in mons)
        rec = " · recording" if self.recording else ""
        self.window.set_title(f"{self.name}: {self.scenario or 'sandbox'} ({size}){rec}")

    def connect(self, addr):
        self.bus = Gio.DBusConnection.new_for_address_sync(
            addr, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
        self.addr = addr
        self.mons = self.monitors()
        if not self.mons:
            raise RuntimeError("no monitors yet")
        self.session = self.call("/org/gnome/Mutter/ScreenCast", SC, "CreateSession",
                                 GLib.Variant("(a{sv})", ({},)), "(o)").unpack()[0]
        self.nodes = {}
        for connector, *_ in self.mons:
            stream = self.call(self.session, SC + ".Session", "RecordMonitor",
                               GLib.Variant("(sa{sv})", (connector, {"cursor-mode": GLib.Variant("u", 1)})),
                               "(o)").unpack()[0]
            self.bus.signal_subscribe(SC, SC + ".Stream", "PipeWireStreamAdded", stream, None,
                                      Gio.DBusSignalFlags.NONE,
                                      lambda *a, c=connector: self.stream_added(c, a[5].unpack()[0]))
        self.call(self.session, SC + ".Session", "Start", None, None)

    def stream_added(self, connector, node):
        self.nodes[connector] = node
        if len(self.nodes) == len(self.mons):
            self.play()

    def play(self):
        x0 = min(x for _c, x, _y, _w, _h in self.mons)
        y0 = min(y for _c, _x, y, _w, _h in self.mons)
        width = max(x + w for _c, x, _y, w, _h in self.mons) - x0
        f = min(1.0, MAX_WIDTH / width)
        pads = " ".join(f"sink_{i}::xpos={round((x - x0) * f)} sink_{i}::ypos={round((y - y0) * f)}"
                        for i, (_c, x, y, _w, _h) in enumerate(self.mons))
        desc = f"compositor name=mix background=black {pads} ! videoconvert ! tee name=t "
        desc += "t. ! queue leaky=downstream max-size-buffers=2 ! gtksink name=sink sync=false "
        if self.record_dir:
            os.makedirs(self.record_dir, exist_ok=True)
            self.recording = os.path.join(self.record_dir, f"{self.name}-{int(time.time() * 1000)}.webm")
            desc += ("t. ! queue ! videorate ! video/x-raw,framerate=15/1 ! videoconvert ! "
                     "vp8enc deadline=1 cpu-used=8 threads=4 ! webmmux streamable=true ! "
                     f"filesink location={self.recording} ")
        for i, (connector, _x, _y, w, h) in enumerate(self.mons):
            desc += (f"pipewiresrc path={self.nodes[connector]} always-copy=true do-timestamp=true ! "
                     f"videoconvert ! videoscale ! video/x-raw,width={max(2, round(w * f))},"
                     f"height={max(2, round(h * f))} ! mix.sink_{i} ")
        self.pipeline = Gst.parse_launch(desc)
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", lambda *_: self.disconnect("end of stream"))
        bus.connect("message::error", lambda _b, m: self.disconnect(f"stream error: {m.parse_error()[0].message}"))
        child = self.window.get_child()
        if child:
            self.window.remove(child)
        self.window.add(self.pipeline.get_by_name("sink").props.widget)
        self.window.show_all()
        self.update_title()
        self.pipeline.set_state(Gst.State.PLAYING)
        log(f"{self.name}: watching {', '.join(f'{c} {w}x{h}' for c, _x, _y, w, h in self.mons)}"
            + (f", recording to {self.recording}" if self.recording else ""))

    def disconnect(self, why):
        if self.pipeline:
            self.pipeline.send_event(Gst.Event.new_eos())    # finish the recording cleanly
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        if self.session and self.bus:
            try:
                self.call(self.session, SC + ".Session", "Stop", None, None)
            except GLib.Error:
                pass
        if self.addr:
            log(f"{self.name}: disconnected: {why}")
        self.addr = self.bus = self.session = self.recording = None
        self.scenario = ""
        child = self.window.get_child()
        if child is not self.waiting:
            if child:
                self.window.remove(child)
            self.window.add(self.waiting)
            self.window.show_all()
        self.window.set_title(f"{self.name}: waiting for the sandbox")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", metavar="DIR", help="also record each sandbox session to DIR/*.webm")
    ap.add_argument("sandboxes", nargs="*", help="sandbox names under ~/.cache/forge-repro, or paths")
    args = ap.parse_args()
    dirs = [s if "/" in s else os.path.join(CACHE, s) for s in args.sandboxes] or [
        os.environ.get("SANDBOX_DIR") or os.path.join(CACHE, "sandbox")]
    Gst.init(None)
    Gtk.init(None)
    loop = GLib.MainLoop()
    views = []

    def closed(view):
        view.disconnect("window closed")
        views.remove(view)
        if not views:
            loop.quit()

    views.extend(View(d, args.record, closed) for d in dirs)
    try:
        loop.run()
    except KeyboardInterrupt:
        for v in views:
            v.disconnect("stopped")


main()
