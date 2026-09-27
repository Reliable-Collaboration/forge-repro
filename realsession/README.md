# Real-session runs

Runs the harness scenarios in the GNOME session you are logged into, to confirm a fix on real
hardware, with your own extensions, screen and settings. Use the sandbox for everything else.

**Security trade-off.** While a run is going, GNOME Shell is in *unsafe mode*: any program running as
you can call `org.gnome.Shell.Eval` (run code in the shell, read the screen, inject input). The
`forge-test-bridge@local` extension turns it on only while it is enabled, and `run.py` enables it at
the start of a run and always disables it at the end.

Setup, once:

```sh
cp -r realsession/forge-test-bridge@local ~/.local/share/gnome-shell/extensions/
# log out and in, so the running shell loads it (it stays disabled)
```

Run:

```sh
realsession/run.py              # the scenarios that are safe in a real session
realsession/run.py 01 14        # just these
```

It tests on your **last workspace**, and refuses to start unless that workspace is empty. It
restores your Forge settings after every scenario, closes only the windows on that workspace, and
returns you to the workspace you were on. Don't touch the mouse or keyboard while it runs.

Remove the bridge when you no longer need it:
`rm -r ~/.local/share/gnome-shell/extensions/forge-test-bridge@local`.
