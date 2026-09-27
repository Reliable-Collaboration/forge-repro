// REAL-SESSION TEST RUNS ONLY. While enabled, GNOME Shell is in unsafe mode: any process of
// this user can call org.gnome.Shell.Eval. realsession/run.sh enables it only for a test run.
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class ForgeTestBridge extends Extension {
    enable() {
        this._previous = global.context.unsafe_mode;
        global.context.unsafe_mode = true;
    }

    disable() {
        global.context.unsafe_mode = this._previous ?? false;
        this._previous = null;
    }
}
