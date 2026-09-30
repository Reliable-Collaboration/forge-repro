#!/usr/bin/env python3
"""Forge starts with an empty or incomplete stylesheet of its own (forge-ext/forge#448).

Forge keeps the user's colours in ~/.config/forge/stylesheet/forge/stylesheet.css and reads its
default colours from it when it starts (and when the preferences open). A rule it looked for and
didn't find came back as {} and was then read as a rule: "TypeError: cssRule.declarations is
undefined", so Forge didn't start ("an error occurred while loading this extension") and the
preferences didn't open. That happened with an empty stylesheet (Forge itself could leave it
empty: it wrote the file without closing it), with one from an older Forge or edited by hand
that lacks a rule, and with a comment in it ("r.selectors is undefined").

  30.1  an empty stylesheet.css: Forge starts and tiles a new window
  30.2  a stylesheet without the .tabbed rule, and one .floated property: the same
  30.3  a stylesheet with a comment: the same
  30.4  Forge read the default colours for what the stylesheet lacks (tabbed, floated), and the
        focus border is drawn in each case (the shell has Forge's styles)
  30.5  the stylesheet is saved completed: it has the rules Forge reads, keeps the user's own
        values, and the file as it was is kept as stylesheet.css.bak
  30.6  a stylesheet with a syntax error: Forge starts with the default one, and the broken file
        is kept as stylesheet.css.bak

This sandbox's own config directory is used, never yours.
Run on a fresh sandbox:  sandbox/launch.sh && scenarios/30_stylesheet_missing_rules.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import harness as h  # noqa: E402

UUID = "forge@jmmaranan.com"
STATES = {1: "ACTIVE", 2: "INACTIVE", 3: "ERROR", 4: "OUT_OF_DATE", 6: "INITIALIZED", 7: "DEACTIVATING",
          8: "ACTIVATING"}


def stylesheet_path():
    return h.js('GLib.build_filenamev([GLib.get_user_config_dir(), "forge", "stylesheet", "forge", "stylesheet.css"])')


def wait_state(want, timeout=15):
    for _ in range(timeout * 4):
        st, err = json.loads(h.js(f"""(() => {{ const e = Main.extensionManager.lookup("{UUID}");
            return JSON.stringify([e.state, e.error ? String(e.error) : ""]); }})()"""))
        if st in want:
            break
        time.sleep(0.25)
    return STATES.get(st, str(st)) + (f": {err}" if err else "")


def restart_forge():
    """Disable and enable Forge in the sandbox shell (both asynchronous in GNOME 50); its state after."""
    h.js(f'(() => {{ Main.extensionManager.disableExtension("{UUID}"); return "ok"; }})()')
    wait_state({2, 3})
    h.js(f'(() => {{ Main.extensionManager.enableExtension("{UUID}"); return "ok"; }})()')
    return wait_state({1, 3})


def css_tag_current():
    """Mark the stylesheet as up to date, so that Forge reads it as it is instead of replacing it
    with its default one (it does that once after each Forge update)."""
    h.js(f"""(() => {{ const e = Main.extensionManager.lookup("{UUID}");
        e.stateObj.getSettings().set_uint("css-last-update", e.stateObj.theme?.cssTag ?? 37); return "ok"; }})()""")


def case(name, contents):
    path = stylesheet_path()
    if h.REAL_SESSION or not path.startswith(os.path.expanduser("~/.cache/forge-repro")):
        print(f"  SKIP  {name}: {path} is not the sandbox's config")
        sys.exit(h.SKIP)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(contents)
    state = restart_forge()
    time.sleep(1.0)
    tiled = False
    palette = None
    border = None
    if state.startswith("ACTIVE"):
        known = {w["id"] for w in h.windows()}
        h.open_editor()
        tiled = any(w["id"] not in known and not w["float"] for w in h.windows())
        palette = json.loads(h.js(f"""JSON.stringify(Main.extensionManager.lookup("{UUID}")
            .stateObj.theme.defaultPalette)"""))
        border = h.js("""(() => { const b = global.display.focus_window?.get_compositor_private()?.border;
            return b ? b.get_theme_node().get_border_width(imports.gi.St.Side.TOP) : -1; })()""")
        h.close_windows()
        time.sleep(0.8)
    with open(path) as f:
        now = f.read()
    backup = open(path + ".bak").read() if os.path.exists(path + ".bak") else None
    ok = state.startswith("ACTIVE") and tiled
    print(f"  {'PASS' if ok else 'FAIL'}  {name}: Forge {state}; a new window tiled: {tiled}; focus border "
          f"width {border}")
    return ok, {"now": now, "backup": backup, "border": border}, palette


def main():
    if h.windows():
        raise SystemExit("sandbox must be fresh (no windows); run sandbox/launch.sh first")
    path = stylesheet_path()
    default = open(os.path.join(json.loads(h.js(f'JSON.stringify(Main.extensionManager.lookup("{UUID}").path)')),
                                "stylesheet.css")).read()
    css_tag_current()
    r = []

    ok1, kept1, _ = case("30.1 empty stylesheet.css", "")
    css_tag_current()

    # the default stylesheet without its .tabbed rule, and without the border-width of .floated
    start = default.index(".tabbed {")
    older = default[:start] + default[default.index("}", start) + 1:]
    fstart = older.index(".floated {")
    fend = older.index("}", fstart)
    older = older[:fstart] + "\n".join(line for line in older[fstart:fend].split("\n")
                                       if "border-width" not in line) + older[fend:]
    ok2, kept2, palette = case("30.2 stylesheet without .tabbed and one .floated property", older)
    css_tag_current()

    mine = "/* my colours */\n" + default.replace("rgba(236, 94, 94, 1)", "rgba(1, 2, 3, 1)", 1)
    ok3, kept3, _ = case("30.3 stylesheet with a comment (and a colour of the user's)", mine)
    r += [ok1, ok2, ok3]

    want = {"tabbed": "rgba(17, 199, 224, 1)", "floated_border": "3"}
    got = {"tabbed": (palette or {}).get("tabbed", {}).get("color"),
           "floated_border": (palette or {}).get("floated", {}).get("border-width")}
    borders = [k["border"] for k in (kept1, kept2, kept3)]
    ok4 = got == want and all(b and b > 0 for b in borders)
    print(f"  {'PASS' if ok4 else 'FAIL'}  30.4 default colours for what the stylesheet lacks: {got} (expected {want}); "
          f"focus border widths {borders} (expected > 0)")
    r.append(ok4)

    completed2 = ".tabbed" in kept2["now"] and kept2["backup"] == older
    completed1 = ".tabbed" in kept1["now"] and kept1["backup"] == ""
    own3 = "rgba(1, 2, 3, 1)" in kept3["now"] and ".tabbed" in kept3["now"]
    ok5 = completed1 and completed2 and own3
    print(f"  {'PASS' if ok5 else 'FAIL'}  30.5 saved completed, the file as it was kept as .bak: empty {completed1}, "
          f"without .tabbed {completed2}; the user's own colour kept: {own3}")
    r.append(ok5)

    broken = default[: default.index(".floated {")] + ".floated {\n  color: red;\n"
    ok6, kept6, _ = case("30.6 stylesheet with a syntax error", broken)
    css_tag_current()
    ok6 = ok6 and kept6["backup"] == broken and ".tabbed" in kept6["now"] and kept6["border"] and kept6["border"] > 0
    print(f"  {'PASS' if ok6 else 'FAIL'}  30.6 with a syntax error: Forge starts, the broken file kept as .bak: "
          f"{kept6['backup'] == broken}")
    r.append(ok6)

    with open(path, "w") as f:                         # (leave a complete stylesheet behind)
        f.write(default)
    restart_forge()
    sys.exit(h.summary(r))


main()
