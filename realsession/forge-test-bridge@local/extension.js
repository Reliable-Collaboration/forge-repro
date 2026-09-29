// REAL-SESSION TEST RUNS ONLY. Puts GNOME Shell in unsafe mode (any process of this user can call
// org.gnome.Shell.Eval), but only while a test runner holds a fresh lease: a file with an expiry
// time that realsession/run.py keeps renewing. If the runner dies without cleaning up (closed
// terminal, kill -9, logged out), unsafe mode turns itself off within LEASE_CHECK_S of the lease
// running out, and stays off at every later login until a runner takes a new lease.
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const LEASE = GLib.build_filenamev([GLib.get_user_cache_dir(), 'forge-test-bridge', 'lease']);
const LEASE_CHECK_S = 5;

export default class ForgeTestBridge extends Extension {
    enable() {
        this._previous = global.context.unsafe_mode;
        this._check();
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, LEASE_CHECK_S, () => {
            this._check();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _check() {
        let fresh = false;
        try {
            const [ok, bytes] = GLib.file_get_contents(LEASE);
            const expiry = Number(new TextDecoder().decode(bytes).trim());
            fresh = ok && expiry > GLib.get_real_time() / 1e6;
        } catch (e) {
            fresh = false; // no lease: no unsafe mode
        }
        global.context.unsafe_mode = fresh || (this._previous ?? false);
    }

    disable() {
        if (this._timer) GLib.source_remove(this._timer);
        this._timer = 0;
        global.context.unsafe_mode = this._previous ?? false;
        this._previous = null;
    }
}
