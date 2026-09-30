#!/usr/bin/env python3
"""Changing a Forge setting while Forge is disabled raises no errors (seen in forge-ext/forge#469's log).

Forge connected "changed" handlers to its settings (the window manager's and the quick settings
indicator's) without ever disconnecting them. After Forge was disabled, as on the lock screen, a
changed setting still ran them, and they failed on the settings Forge had dropped ("this.ext.settings
is null", "this.extension.settings is null"). After it was enabled again, the old handlers kept
running next to the new ones.

  29.1  disable Forge, change two of its settings: no Forge errors
  29.2  enable it again: a new window tiles, and changing a setting raises no errors

Run on a fresh sandbox:  sandbox/launch.sh && scenarios/29_settings_after_disable.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402

UUID = "forge@jmmaranan.com"


def set_state(call, want):
    h.js(f'(() => {{ Main.extensionManager.{call}("{UUID}"); return "ok"; }})()')
    for _ in range(60):
        if h.js(f'Main.extensionManager.lookup("{UUID}").state') in want:
            return
        time.sleep(0.25)


def flip(key):
    """Change a Forge setting through a settings object of its own (as the preferences would)."""
    h.js(f"""(() => {{ const s = Main.extensionManager.lookup("{UUID}").stateObj.getSettings();
        s.set_boolean("{key}", !s.get_boolean("{key}")); return "ok"; }})()""")
    time.sleep(0.5)


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    r = []
    h.open_editor()
    h.close_windows()
    time.sleep(0.5)

    errors0 = h.js_errors()
    set_state("disableExtension", (2, 3))
    for key in ("focus-border-toggle", "quick-settings-enabled"):
        flip(key)
        flip(key)
    errors1 = h.js_errors()
    ok = errors1 == errors0
    print(f"  {'PASS' if ok else 'FAIL'}  29.1 settings changed while Forge is disabled: new Forge errors "
          f"{errors1 - errors0} (expected 0)")
    r.append(ok)

    set_state("enableExtension", (1, 3))
    time.sleep(1.0)
    known = {w["id"] for w in h.windows()}
    h.open_editor()
    tiled = any(w["id"] not in known and not w["float"] for w in h.windows())
    flip("focus-border-toggle")
    flip("focus-border-toggle")
    errors2 = h.js_errors()
    ok = tiled and errors2 == errors1
    print(f"  {'PASS' if ok else 'FAIL'}  29.2 enabled again: a new window tiled: {tiled}; new Forge errors "
          f"{errors2 - errors1} (expected 0)")
    r.append(ok)
    h.close_windows()
    sys.exit(h.summary(r))


main()
