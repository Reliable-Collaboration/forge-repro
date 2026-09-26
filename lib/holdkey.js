// Hold a real key chord with a virtual KEYBOARD in the sandbox (compositor generates repeats).
//   __WIN__ (window id % 1000 to focus), __KEYS__ (keyval list, last one is held), __HOLD_MS__
(() => {
    const wm = Main.extensionManager.lookup('forge@jmmaranan.com').stateObj.extWm;
    const seat = global.stage.context.get_backend().get_default_seat();
    const kb = seat.create_virtual_device(1 /* CLUTTER_KEYBOARD_DEVICE */);
    const now = () => GLib.get_monotonic_time();
    const st = globalThis.__hk = { t0: now(), log: [], done: false, calls: 0 };
    const snap = (tag) => {
        const wins = wm.tree.getNodeByType('WINDOW').map((n) => {
            const f = n.nodeValue.get_frame_rect();
            return `${n.nodeValue.get_id() % 1000}:x=${f.x},y=${f.y},w=${f.width},h=${f.height},p=${(n.percent ?? 0).toFixed(3)}`;
        });
        const con = wm.tree.getNodeByType('CON')[0];
        st.log.push(`${((now() - st.t0) / 1000).toFixed(0)}ms ${tag} calls=${st.calls} | ${wins.join(' | ')}${con ? ` | CON p=${(con.percent ?? 0).toFixed(3)}` : ''}`);
    };
    // Count how often Forge's resize() actually runs (wrapped only for this test run).
    const orig = wm.resize;
    wm.resize = function (...a) { st.calls++; return orig.apply(this, a); };
    const keys = [__KEYS__];
    const w = global.display.list_all_windows().find((w) => w.get_id() % 1000 === __WIN__);
    w.activate(global.get_current_time());
    const seq = [() => snap('start')];
    keys.forEach((k) => seq.push(() => kb.notify_keyval(now(), k, 1)));
    seq.push(() => snap('keys down'));
    const holdTicks = Math.round(__HOLD_MS__ / 100);
    for (let i = 1; i <= holdTicks; i++) seq.push(() => snap(`holding ${i * 100}ms`));
    [...keys].reverse().forEach((k) => seq.push(() => kb.notify_keyval(now(), k, 0)));
    seq.push(() => snap('keys released'));
    for (let j = 1; j <= 4; j++) seq.push(() => snap(`after release +${j * 100}ms`));
    let k = 0;
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
        if (k < seq.length) { seq[k++](); return GLib.SOURCE_CONTINUE; }
        wm.resize = orig;
        st.done = true;
        return GLib.SOURCE_REMOVE;
    });
    return 'started';
})()
