#!/usr/bin/env python3
"""Run harness scenarios in the GNOME session you are logged into (not a sandbox).

    realsession/run.py [scenario ...]      default: the scenarios that are safe in a real session

What it does, and what it guarantees:
  - takes a lease (a file with an expiry time, renewed every 20 s) and enables the
    forge-test-bridge@local extension, which turns on unsafe mode (so the harness can use
    org.gnome.Shell.Eval) only while the lease is fresh. At the end it drops the lease and disables
    the bridge, also on errors, Ctrl+C, SIGTERM or a hang-up; if this process dies anyway (kill -9,
    logout), the lease runs out and the bridge turns unsafe mode off within about 90 s;
  - refuses to start unless the test workspace (default: the last one) has no windows, runs every
    scenario there, and never closes a window that existed before the run started (nor one shown
    on all workspaces);
  - saves your Forge settings first and restores them exactly after every scenario (scenarios
    change settings such as gaps or auto-split);
  - returns you to the workspace you were on.
Don't use the mouse or keyboard while it runs: the scenarios drive a virtual mouse and keyboard.

Needs the bridge installed in ~/.local/share/gnome-shell/extensions (see realsession/README.md)
and loaded by the running shell (log out and in once after installing it).
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time

HERE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE_DIR)
BRIDGE = "forge-test-bridge@local"
FORGE_DCONF = "/org/gnome/shell/extensions/forge/"
# Scenarios that only open, arrange and close their own windows on the test workspace.
# Not here: 09 (fuzz: random actions), 10 (moves windows to another workspace), 12 (needs two
# monitors), 13 (a proposal's setting).
DEFAULT = ["01", "02", "03", "04", "06", "07", "08", "11", "14", "15", "16", "17"]

LEASE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
                     "forge-test-bridge", "lease")
LEASE_S, RENEW_S = 90, 20

os.environ["FORGE_TEST_REAL_SESSION"] = "1"
os.environ["FORGE_TEST_SINCE"] = str(int(time.time()))
sys.path.insert(0, os.path.join(ROOT, "lib"))
import harness as h  # noqa: E402


def write_lease():
    os.makedirs(os.path.dirname(LEASE), exist_ok=True)
    tmp = LEASE + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(int(time.time()) + LEASE_S))
    os.replace(tmp, LEASE)


def drop_lease():
    try:
        os.remove(LEASE)
    except FileNotFoundError:
        pass


def keep_lease(stop):
    while not stop.wait(RENEW_S):
        write_lease()


def sh(*argv, check=True):
    return subprocess.run(argv, check=check, capture_output=True, text=True).stdout


def bridge(on):
    sh("gnome-extensions", "enable" if on else "disable", BRIDGE, check=False)


def unsafe_mode():
    try:
        ok, _ = h.js_raw("1")
        return ok
    except Exception:
        return False


def window_ids_on(ws_index):
    return json.loads(h.js(f"""JSON.stringify(global.display.list_all_windows()
        .filter(w => !w.is_skip_taskbar() && w.get_workspace()?.index() === {ws_index} && !w.is_on_all_workspaces())
        .map(w => w.get_id()))"""))


def activate_workspace(index):
    h.js(f"""(() => {{ global.workspace_manager.get_workspace_by_index({index})
        .activate(global.get_current_time()); return "ok"; }})()""")
    time.sleep(1.0)


def close_test_windows(test_ws):
    """Close the windows the run opened on the test workspace (harness.close_windows() leaves the
    ones that existed before the run alone); refuse if that workspace isn't the active one."""
    activate_workspace(test_ws)
    if h.js("global.workspace_manager.get_active_workspace_index()") != test_ws:
        print(f"cleanup: workspace {test_ws + 1} isn't active; not closing anything")
        return
    h.close_windows()


def restore_settings(saved):
    subprocess.run(["dconf", "reset", "-f", FORGE_DCONF], check=True)
    subprocess.run(["dconf", "load", FORGE_DCONF], input=saved, text=True, check=True)
    time.sleep(0.5)


def main():
    wanted = sys.argv[1:] or DEFAULT
    if BRIDGE not in sh("gnome-extensions", "list"):
        raise SystemExit(f"{BRIDGE} is not loaded by the running shell: install it and log out and in once")
    saved = sh("dconf", "dump", FORGE_DCONF)
    backup = os.path.join(tempfile.gettempdir(), f"forge-settings-before-real-test-{os.getpid()}.dconf")
    open(backup, "w").write(saved)
    for sig in (signal.SIGTERM, signal.SIGHUP):                 # run the cleanup below on these too
        signal.signal(sig, lambda *_: sys.exit(1))
    results = []
    original_ws = test_ws = None
    stop = threading.Event()
    try:
        write_lease()
        threading.Thread(target=keep_lease, args=(stop,), daemon=True).start()
        bridge(True)
        for _ in range(20):
            if unsafe_mode():
                break
            time.sleep(0.25)
        else:
            raise SystemExit("the bridge is enabled but Eval still fails")
        original_ws = h.js("global.workspace_manager.get_active_workspace_index()")
        test_ws = h.js("global.workspace_manager.get_n_workspaces()") - 1
        if window_ids_on(test_ws):
            raise SystemExit(f"workspace {test_ws + 1} has windows; empty it (or pick another) and run again")
        # Every window that exists now is yours: the harness never closes any of them
        os.environ["FORGE_TEST_PRESERVE"] = ",".join(str(i) for i in json.loads(h.js(
            "JSON.stringify(global.display.list_all_windows().map(w => w.get_id()))")))
        os.environ["FORGE_TEST_WS"] = str(test_ws)
        print(f"testing on workspace {test_ws + 1}; your Forge settings are saved in {backup}")
        activate_workspace(test_ws)
        for arg in wanted:
            scenario = next((os.path.join(ROOT, "scenarios", f) for f in sorted(os.listdir(os.path.join(ROOT, "scenarios")))
                             if f.startswith(arg) and f.endswith(".py")), None)
            if not scenario:
                print(f"no scenario {arg}")
                continue
            name = os.path.basename(scenario)[:-3]
            print(f"== {name}", flush=True)
            with tempfile.TemporaryDirectory(prefix="forge-real-") as tmp:
                # throwaway profiles/logs (e.g. VS Code); Forge errors counted from this scenario on
                env = dict(os.environ, SANDBOX_DIR=tmp, FORGE_TEST_SINCE=str(int(time.time())))
                try:
                    r = subprocess.run([sys.executable, scenario], env=env, capture_output=True, text=True,
                                       timeout=1200)
                    out, status = r.stdout + r.stderr, r.returncode
                except subprocess.TimeoutExpired as e:
                    out, status = (e.stdout or b"").decode() + "\ntimed out", 124
            for line in out.splitlines():
                if any(k in line for k in ("PASS", "FAIL", "SKIP", "RESULT", "Error", "   - ")):
                    print(line, flush=True)
            result = next((l for l in reversed(out.splitlines()) if l.startswith("RESULT")), f"no result (exit {status})")
            results.append((name, result, status))
            # Clean up after each scenario: its windows (only on the test workspace) and settings
            close_test_windows(test_ws)
            restore_settings(saved)
    finally:
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):  # let the cleanup finish
            signal.signal(sig, signal.SIG_IGN)
        try:
            if original_ws is not None and test_ws is not None:
                close_test_windows(test_ws)
                activate_workspace(original_ws)
        except Exception as e:
            print(f"cleanup: {e}")
        try:
            restore_settings(saved)
        except Exception as e:
            print(f"could not restore Forge settings ({e}); restore them with: dconf load {FORGE_DCONF} < {backup}")
        stop.set()
        drop_lease()
        bridge(False)
        time.sleep(0.5)
        print("bridge off" if not unsafe_mode() else "WARNING: unsafe mode is still on; run: "
              f"gnome-extensions disable {BRIDGE}")
    print("\n== summary (real session)")
    for name, result, _ in results:
        print(f"  {name}: {result}")
    sys.exit(0 if all(s in (0, 77) for _, _, s in results) else 1)


main()
