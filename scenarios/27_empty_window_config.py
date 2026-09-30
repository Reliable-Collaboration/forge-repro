#!/usr/bin/env python3
"""An empty or broken windows.json doesn't stop Forge from starting (forge-ext/forge#415).

Forge keeps its window rules in ~/.config/forge/config/windows.json. Reading it did JSON.parse()
without a fallback, so an empty file (which Forge itself could leave behind: it wrote the file
without closing it) or a typo in it made enabling fail: "an error occurred while loading this
extension".

  27.1  windows.json empty: Forge enables, and tiles a new window
  27.2  windows.json with invalid JSON: the same
  27.3  the file is left as it was when Forge starts
  27.4  when the rules change (Super+C) Forge writes the file anew, after copying the broken one to
        windows.json.bak

This sandbox's own config directory is used, never yours.
Run on a fresh sandbox:  sandbox/launch.sh && scenarios/27_empty_window_config.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402

UUID = "forge@jmmaranan.com"


def config_path():
    return h.js('GLib.build_filenamev([GLib.get_user_config_dir(), "forge", "config", "windows.json"])')


STATES = {1: "ACTIVE", 2: "INACTIVE", 3: "ERROR", 4: "OUT_OF_DATE", 6: "INITIALIZED", 7: "DEACTIVATING",
          8: "ACTIVATING"}


def state():
    return h.js(f"""(() => {{ const e = Main.extensionManager.lookup("{UUID}");
        return JSON.stringify([e.state, e.error ? String(e.error) : ""]); }})()""")


def wait_state(want, timeout=15):
    import json
    for _ in range(timeout * 4):
        st, err = json.loads(state())
        if st in want:
            return st, err
        time.sleep(0.25)
    return st, err


def reenable():
    """Disable and enable Forge in the sandbox shell (both are asynchronous in GNOME 50); return
    its state name afterwards."""
    h.js(f'(() => {{ Main.extensionManager.disableExtension("{UUID}"); return "ok"; }})()')
    wait_state({2, 3})
    h.js(f'(() => {{ Main.extensionManager.enableExtension("{UUID}"); return "ok"; }})()')
    st, err = wait_state({1, 3})
    return STATES.get(st, str(st)) + (f": {err}" if err else "")


def case(name, contents):
    path = config_path()
    if h.REAL_SESSION or not path.startswith(os.path.expanduser("~/.cache/forge-repro")):
        # the harness only touches the sandbox's own config (under its SANDBOX_DIR)
        print(f"  SKIP  {name}: {path} is not the sandbox's config")
        sys.exit(h.SKIP)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(contents)
    state_name = reenable()
    time.sleep(1.0)
    known = {w["id"] for w in h.windows()} if state_name.startswith("ACTIVE") else set()
    tiled = False
    if state_name.startswith("ACTIVE"):
        h.open_editor()
        tiled = any(w["id"] not in known and not w["float"] for w in h.windows())
    with open(path) as f:
        kept = f.read() == contents
    ok = state_name.startswith("ACTIVE") and tiled
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: Forge {state_name}; a new window tiled: {tiled}")
    if state_name.startswith("ACTIVE"):          # (the harness closes windows through Forge's tree)
        h.close_windows()
        time.sleep(0.8)
    return ok, kept


def valid_json(path):
    import json
    try:
        json.load(open(path))
        return True
    except ValueError:
        return False


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    r = []
    ok1, kept1 = case("27.1 empty windows.json", "")
    ok2, kept2 = case("27.2 invalid windows.json", '{"overrides": [ {"wmClass": "x", ')
    r += [ok1, ok2]
    ok3 = kept1 and kept2
    print(f"  {'PASS' if ok3 else 'FAIL'}  27.3 the user's file is left as it was: {ok3}")
    r.append(ok3)

    broken = '{"overrides": [ {"wmClass": "mine", "mode": "float"}, '
    path = config_path()
    with open(path, "w") as f:
        f.write(broken)
    state_name = reenable()
    ok4 = False
    if state_name.startswith("ACTIVE"):
        h.open_editor()
        wid = h.windows()[0]["id"]
        h.hold_keys(wid, h.chord("window-toggle-float"), 0)      # the rules change: Forge writes the file
        time.sleep(1.2)
        bak = path + ".bak"
        saved = open(bak).read() if os.path.exists(bak) else None
        ok4 = saved == broken
        print(f"  {'PASS' if ok4 else 'FAIL'}  27.4 after a change, the broken file was kept as windows.json.bak: "
              f"{saved is not None and saved == broken} (file now valid JSON: {valid_json(path)})")
        h.close_windows()
    else:
        print(f"  FAIL  27.4 Forge didn't start: {state_name}")
    r.append(ok4)
    sys.exit(h.summary(r))


main()
