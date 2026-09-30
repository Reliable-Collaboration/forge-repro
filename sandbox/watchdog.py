#!/usr/bin/env python3
"""Continuous layout watcher for a whole scenario (lib/watchdog.js, running inside the shell).

    sandbox/watchdog.py start            start (or restart) watching
    sandbox/watchdog.py report [--min-ms N]
                                         print the overlap/off-screen episodes so far, longest first;
                                         episodes shorter than N ms (default 0) are only counted
Each episode is "layout" (Forge asked for overlapping or off-screen places: a Forge bug), "lag"
(Forge's requests were fine but an app hadn't taken its new place yet; the lagging apps are named)
"stall" (such an app didn't change its frame at all for 450 ms or more: the app was busy) or
"drag" (the window out of place is being resized with the mouse, which GNOME does, not Forge) or
"opening" (a window that hasn't reached any place since it appeared).
Uses the same shell as the harness: the sandbox (SANDBOX_DIR), or the real session in a
realsession/run.py run (FORGE_TEST_REAL_SESSION=1).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "report"])
    ap.add_argument("--min-ms", type=int, default=0)
    args = ap.parse_args()
    if args.cmd == "start":
        print(h.js(open(os.path.join(h.LIB, "watchdog.js")).read()))
        return
    rep = json.loads(h.js("globalThis.__watchdog ? globalThis.__watchdog.report() : 'null'") or "null")
    if not rep:
        print("watch: no watcher running")
        return
    eps = sorted(rep["episodes"], key=lambda e: -e["duration_ms"])
    shown = [e for e in eps if e["duration_ms"] >= args.min_ms]
    parts = []
    for kind in ("layout", "lag", "stall", "drag", "opening"):
        k = [e for e in eps if e.get("kind") == kind]
        parts.append(f"{len(k)} {kind}" + (f" (longest {k[0]['duration_ms']} ms)" if k else ""))
    print(f"watch: {len(eps)} overlap/off-screen episodes: {', '.join(parts)}; {rep['samples']} samples"
          f" (started {rep['started_wall_ms']})")
    for app, a in sorted(rep.get("apps", {}).items()):
        lags = sorted(a["lag_ms"])
        if lags:
            pct = lambda q: lags[min(len(lags) - 1, int(q * len(lags)))]
            print(f"  {app}: takes its new place in {pct(0.5)} ms (median), {pct(0.9)} ms (90%), "
                  f"{lags[-1]} ms (worst) over {len(lags)} changes; {a['superseded']} requests overtaken")
    for e in shown:
        lag = f", lagging: {' '.join(e['lagging'])}" if e.get("lagging") else ""
        print(f"  at {e['start_ms'] / 1000:7.2f} s for {e['duration_ms']:5d} ms, worst {e['max_px']:4d} px, "
              f"{e.get('kind', '?'):6s}: {e['what']}{' (still)' if e.get('ongoing') else ''}{lag}")
        if e.get("where") and e["duration_ms"] >= 100:
            print(f"      where: {e['where']}")
        if e.get("kind") == "layout" and e.get("drag_ms"):
            # (an episode that is partly a mouse drag: how much of it wasn't)
            print(f"      layout for {e['layout_ms']} ms of it, from {e.get('layout_at_ms')} ms"
                  + (f": {e['layout_where']}" if e.get("layout_where") else ""))


main()
