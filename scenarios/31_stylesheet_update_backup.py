#!/usr/bin/env python3
"""After a Forge update, the stylesheet backup goes next to the stylesheet, and a read-only
install doesn't make Forge fail at the next update (forge-ext/forge#266).

After each Forge update (setting css-last-update differs from Forge's own tag), Forge backs up
the user's stylesheet (~/.config/forge/stylesheet/forge/stylesheet.css) and copies its default
stylesheet over it. The backup's name came from a property that doesn't exist, so it went to
"undefined.bak" in GNOME Shell's working directory (usually the home folder). Both copies took
the permissions of their source: where the extension's files are read-only (NixOS, some
packages) the user's stylesheet and the backup became read-only too, and at the next update
Forge couldn't overwrite them ("Permission denied"), so it didn't start.

The sandbox's copy of Forge is made read-only here (as such an install is).

  31.1  after an update, the backup is stylesheet.css.bak next to the stylesheet, and no
        undefined.bak is written to GNOME Shell's working directory
  31.2  the updated stylesheet and its backup can be written by the user
  31.3  after a second update Forge starts, and the update went through (css-last-update set)
  31.4  with a read-only stylesheet and backup left by an earlier Forge, an update again works

This sandbox's own config directory is used, never yours.
Run on a fresh sandbox:  sandbox/launch.sh && scenarios/31_stylesheet_update_backup.py
"""
import json
import os
import stat
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402

UUID = "forge@jmmaranan.com"
STATES = {1: "ACTIVE", 2: "INACTIVE", 3: "ERROR", 4: "OUT_OF_DATE", 6: "INITIALIZED", 7: "DEACTIVATING",
          8: "ACTIVATING"}
SANDBOXES = os.path.expanduser("~/.cache/forge-repro")


def wait_state(want, timeout=15):
    for _ in range(timeout * 4):
        st, err = json.loads(h.js(f"""(() => {{ const e = Main.extensionManager.lookup("{UUID}");
            return JSON.stringify([e.state, e.error ? String(e.error) : ""]); }})()"""))
        if st in want:
            break
        time.sleep(0.25)
    return STATES.get(st, str(st)) + (f": {err}" if err else "")


def update_forge():
    """As after a Forge update: css-last-update differs from Forge's tag, and Forge starts again.
    Returns Forge's state and css-last-update afterwards."""
    settings = f'Main.extensionManager.lookup("{UUID}").stateObj.getSettings()'
    h.js(f'(() => {{ Main.extensionManager.disableExtension("{UUID}"); return "ok"; }})()')
    wait_state({2, 3})
    h.js(f'(() => {{ {settings}.set_uint("css-last-update", 1); return "ok"; }})()')
    h.js(f'(() => {{ Main.extensionManager.enableExtension("{UUID}"); return "ok"; }})()')
    state = wait_state({1, 3})
    time.sleep(0.5)
    return state, h.js(f"{settings}.get_uint('css-last-update')")


def writable(path):
    return os.path.exists(path) and bool(os.stat(path).st_mode & stat.S_IWUSR)


def mark(path):
    """Change the user's stylesheet (as a colour change in the preferences does), so that an update
    can be seen replacing it. (Its modification time can't show that: a copy keeps the source's.)"""
    mode = os.stat(path).st_mode
    os.chmod(path, mode | stat.S_IWUSR)
    with open(path, "a") as f:
        f.write("\n.changed-by-the-user {\n  color: red;\n}\n")  # (not a comment: see #448)
    os.chmod(path, mode)


def replaced(path, default):
    return open(path).read() == default


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    css = h.js('GLib.build_filenamev([GLib.get_user_config_dir(), "forge", "stylesheet", "forge", "stylesheet.css"])')
    cwd = h.js("GLib.get_current_dir()")
    ext = h.js(f'Main.extensionManager.lookup("{UUID}").path')
    if h.REAL_SESSION or not all(p.startswith(SANDBOXES) for p in (css, cwd, ext)):
        # the scenario only changes files in the sandbox's own directory
        print(f"  SKIP  31: not all of {css}, {cwd} (GNOME Shell's working directory), {ext} are the sandbox's")
        sys.exit(h.SKIP)
    tag = h.js(f'Main.extensionManager.lookup("{UUID}").stateObj.theme.cssTag')
    default = open(os.path.join(ext, "stylesheet.css")).read()
    undefined_bak = os.path.join(cwd, "undefined.bak")
    for p in (undefined_bak, css + ".bak"):
        if os.path.exists(p):
            os.chmod(p, 0o644)
            os.remove(p)
    # the sandbox's copy of Forge becomes read-only, as a NixOS or package install is
    for root, dirs, files in os.walk(ext):
        for f in files:
            os.chmod(os.path.join(root, f), 0o444)
    r = []

    state, last = update_forge()
    backup = os.path.exists(css + ".bak")
    stray = os.path.exists(undefined_bak)
    ok = state.startswith("ACTIVE") and backup and not stray
    print(f"  {'PASS' if ok else 'FAIL'}  31.1 update: Forge {state}; backup stylesheet.css.bak: {backup}; "
          f"undefined.bak in GNOME Shell's working directory: {stray}")
    r.append(ok)

    ok = writable(css) and writable(css + ".bak")
    print(f"  {'PASS' if ok else 'FAIL'}  31.2 the stylesheet and its backup can be written: "
          f"{writable(css)}, {writable(css + '.bak')}")
    r.append(ok)

    mark(css)
    state, last = update_forge()
    ok = state.startswith("ACTIVE") and last == tag and replaced(css, default)
    print(f"  {'PASS' if ok else 'FAIL'}  31.3 a second update: Forge {state}; css-last-update {last} "
          f"(expected {tag}); stylesheet replaced by the new default: {replaced(css, default)}")
    r.append(ok)

    mark(css)
    for p in (css, css + ".bak"):                      # as an earlier Forge left them
        if os.path.exists(p):
            os.chmod(p, 0o444)
    state, last = update_forge()
    ok = state.startswith("ACTIVE") and last == tag and replaced(css, default)
    print(f"  {'PASS' if ok else 'FAIL'}  31.4 read-only stylesheet and backup from before: Forge {state}; "
          f"css-last-update {last} (expected {tag}); stylesheet replaced by the new default: {replaced(css, default)}")
    r.append(ok)

    for root, dirs, files in os.walk(ext):             # (the sandbox's copy is removed at its next launch)
        for f in files:
            os.chmod(os.path.join(root, f), 0o644)
    if os.path.exists(undefined_bak):
        os.chmod(undefined_bak, 0o644)
    sys.exit(h.summary(r))


main()
