# Archived prototypes

These are the exploratory scripts written while working out the detection
pipeline, kept because they are part of the development record. **They are not
the system.** Run `python run.py` from the project root for that.

| Script | What it explored |
|---|---|
| `second_main.py` | Stock COCO weights, person class only — the first thing that worked |
| `main.py` | Three custom detectors drawn onto one frame |
| `1window.py` | Added a desktop alert on weapon detection |
| `4window.py` | Quad panel: raw feed, person, weapon, fire side by side |
| `vdo.py` | Camera smoke test, saves a frame on `r` |
| `new.py`, `test_file.py` | Single-image inference against one model |
| `noti.py` | The original notification helper |

`samples/` holds the still images these scripts run against.

## Defects corrected during review

Each of these was found in the pre-FPR review. They are fixed here so nothing
in the repository is broken, and they are listed because the fixes are worth
discussing in the report rather than hiding.

- **`4window.py` — panels shared one buffer.** `pd_frame = gd_frame = fd_frame
  = frame` binds three names to a single NumPy array, so the weapon panel also
  showed the person boxes and the fire panel showed all three. Now one
  `.copy()` per panel.
- **`second_main.py` — crashed on its first detection.** Box coordinates come
  out of `boxes.data.tolist()` as floats, and `cv2.rectangle` requires integer
  points. `imshow`/`waitKey` also sat inside the per-detection loop, so the
  window froze whenever nobody was in shot and `q` could not quit.
- **`noti.py` — blocked the capture loop.** It slept one second inside the
  notify call, on every alerting frame. Rate limiting now lives in
  `surveillance/alerts.py`, off the capture thread.
- **Fire and smoke raised no alert.** Only weapons set the flag, despite the
  report describing fire monitoring. `1window.py` now alerts on both.
- **Class names were hard-coded.** `("smoke", "fire")[int(class_id) == 0]`
  happens to be right for the current checkpoint and silently wrong after any
  retrain. Now read from `model.names`.
- **Wrong checkpoints.** Scripts loaded `last.pt`; they now load `best.pt`.
  `1window.py` and `4window.py` also loaded stock COCO weights for people
  rather than the custom-trained person model.
- **`new.py` pointed at a directory that does not exist** (`./weights/`).
- **Invisible label.** `putText(..., (0, 0), ...)` places the text *baseline*
  on the top edge, so every glyph rendered above the frame.
- **Fire ran at the 0.25 default** in two scripts and 0.35 in a third. All
  three now use 0.5, matching `config.yaml` and the model card.
- **Quad-view could raise on odd canvas sizes.** Fixed slices of `width // 2`
  do not necessarily add back up to `width`; the assignments now slice by each
  tile's own shape.

## What replaced them

| Prototype concern | Now lives in |
|---|---|
| Model loading and inference | `surveillance/detectors.py` |
| Drawing, letterboxing, panels | `surveillance/render.py`, `surveillance/geometry.py` |
| Capture loop, multi-camera | `surveillance/pipeline.py` |
| Notifications | `surveillance/alerts.py`, `surveillance/channels/` |
| Nothing — this is new | `surveillance/analytics.py`, `surveillance/storage.py`, `surveillance/web/` |
