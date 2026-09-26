# Spike: cropping an overflowing window to its tile (GNOME Shell 50.1)

Feasibility check for a possible `clip` overflow policy: when a window's minimum size cannot fit
its tile, place it at its real size and crop what is drawn to the tile.

Forge is disabled for the spike; windows are placed by hand with `move_resize_frame()`.
Run on a fresh sandbox: `sandbox/launch.sh && spikes/overflow-clip/01_place_and_pick.py`, then
`spikes/overflow-clip/02_click_routing.py` (reuses the windows from 01).

Layout: B (Text Editor) frame x 900..1900 below; A (Text Editor) or X (xmessage, X11) frame
x 20..1020 on top; the top window's actor is clipped at stage x 880 with `actor.set_clip()`.

## Results

| Question | Result |
|---|---|
| Does Mutter report the minimum size? | Yes: `MetaWindow.get_min_size()` → `[true, 410, 250]` for Text Editor. (Availability on GNOME 45–49 not checked yet.) |
| Clicks in the cropped-away part go to the visible window below? (Wayland client) | ✅ Click at x 960 focuses B. Control without the crop: focuses A |
| Same for an X11 client (Xwayland)? | ✅ Click at x 960 focuses B. Control without the crop: focuses X |
| Timing caveat | The click must come after the crop has been painted. A pick made in the same main-loop iteration as `set_clip()` still returned the old window |
| Rendering | ❌ with the crop alone: Mutter's occlusion culling ignores the clip, so the window below is not painted behind the crop (blank band; `clip-without-effect.png`). ✅ with any effect attached to the cropped actor (tested with a no-op `Clutter.BrightnessContrastEffect`): culling is skipped for that actor and the result is correct (`clip-with-effect.png`). Cost: one offscreen render for that window while it is cropped |
| Can a window be placed partly outside the monitor? | ✅ Moving A to x = −300 is kept as requested |
| Cropped edge | Square cut, no shadow or rounded corner on that side. That is where an overflow indicator would go |
