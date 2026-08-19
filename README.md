# Smart Surveillance System

A local, multi-camera threat detection system. YOLO11 detectors feed a
behavioural analytics layer, which feeds a debounced alert manager, which
writes to an event log and notifies operators. A Flask dashboard shows the
annotated streams and the log.

Everything runs on the local machine. No video ever leaves it.

MSc Computer Science Project (7COM1040) — Ahmed Raza, 24178662.
Supervisor: Mr Imran Khan.

---

## Quick start

```bash
python -m venv venv && venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

```bash
python run.py --check
```

`--check` validates `config.yaml`, confirms every model file is present, and
reports whether email alerting is configured. Then:

```bash
python run.py
```

The dashboard is at <http://127.0.0.1:8000>.

| Command | Effect |
|---|---|
| `python run.py` | Detection plus the web dashboard |
| `python run.py --display` | Also opens a local OpenCV window (`q` or `Esc` to close) |
| `python run.py --headless` | Detection and alerting only, no web server |
| `python run.py --check` | Validate configuration and exit |

## Architecture

```
camera ──> CameraWorker ──> DetectorBundle ──> AnalyticsEngine ──> AlertManager
(cv2)      (one thread     (person, weapon,   (tracking,          (debounce,
            per camera)     fire models)       loitering,          cooldown)
                                               armed person)          │
                                                                      ├─> EventStore (SQLite + snapshots)
                                                                      ├─> DesktopChannel
                                                                      └─> EmailChannel
                              annotated frames ──> FrameBuffer ──> Flask dashboard (MJPEG)
```

| Module | Responsibility |
|---|---|
| `surveillance/config.py` | `config.yaml` + environment loading |
| `surveillance/detectors.py` | YOLO model loading and inference |
| `surveillance/analytics.py` | Tracking, loitering, weapon-to-person association |
| `surveillance/alerts.py` | Debounce, cooldown, threaded dispatch |
| `surveillance/channels/` | Desktop and email delivery |
| `surveillance/storage.py` | Event log and snapshot retention |
| `surveillance/render.py` | Annotation, letterboxing, panel composition |
| `surveillance/pipeline.py` | Capture loop, one worker per camera |
| `surveillance/web/` | Flask dashboard |

## Detection

Three single-purpose YOLO11-nano detectors run per frame. Full metrics,
training provenance and known limitations are in
[`docs/MODEL_CARD.md`](docs/MODEL_CARD.md).

| Detector | Classes | mAP@50 | Threshold |
|---|---|---:|---:|
| Person | `person` | 0.860 | 0.40 |
| Weapon | `Handgun` | 0.836 | 0.40 |
| Fire | `fire`, `smoke` | 0.458 | 0.50 |

The fire model is the weak one. It runs at a higher threshold and needs four
consecutive frames before it alerts anyone; see the model card for a documented
false positive.

## Alerts

Analytics raises an event on every qualifying frame. The alert manager decides
whether a human should hear about it:

- **Debounce** — the condition must hold for `min_consecutive_frames` before
  anything fires, so a single-frame false positive stays silent.
- **Cooldown** — repeats of the same event on the same camera are suppressed
  for `cooldown_seconds`. A weapon held in view for ten seconds at 10 fps
  produces one alert, not a hundred.
- **Off-thread dispatch** — delivery runs on a worker thread, so a slow SMTP
  server never stalls a camera.

Both are tunable per event in `config.yaml` and live from the Settings page.

## Configuration

Operator settings live in [`config.yaml`](config.yaml). Cameras take an integer
device index or a stream URL:

```yaml
cameras:
  - id: cam-01
    source: 0
  - id: cam-02
    source: "rtsp://192.168.1.50:554/stream1"
```

**Secrets never go in `config.yaml`.** Copy `.env.example` to `.env` and set
the SMTP values there; `.env` is git-ignored. With no SMTP credentials present,
the email channel simply is not registered and desktop alerts continue.

## Data protection

- Frames that did not raise an alert are **never written to disk**.
- Snapshots attached to an alert are deleted after `retention_days`, enforced
  by an hourly job in `surveillance/storage.py` and covered by tests.
- The dashboard binds to `127.0.0.1` by default.

## Tests

```bash
python -m unittest discover -s tests -t .
```

82 tests covering analytics, alert debouncing and cooldown, event storage and
retention, configuration, geometry, and every dashboard route. They use only
the standard library and Flask, so they run without OpenCV or PyTorch
installed. Model inference itself is not unit tested — it is measured instead,
by `tools/evaluate.py`.

## Evaluation

```bash
python tools/inspect_models.py
```

Reads training provenance and metrics straight out of the checkpoints — no
PyTorch needed.

```bash
python tools/evaluate.py --benchmark --iterations 100
```

Per-model and end-to-end inference latency on this machine.

```bash
python tools/evaluate.py --validate --data path/to/test_data.yaml --split test
```

Held-out metrics. The numbers in the model card are *validation* metrics from
training and are optimistically biased; anything quoted as generalisation
performance needs a split no model has seen.

```bash
python tools/evaluate.py --confusion --images imgs/
```

Runs every detector over a folder and flags images where more than one fires —
the cross-model false positives worth writing up.

Results are written to `docs/results/` as CSV and JSON.

## Repository layout

```
run.py                  single entry point
config.yaml             operator configuration
.env.example            template for secrets (never commit .env)
surveillance/           the system
tests/                  unit tests
tools/                  evaluation and provenance
docs/                   model card, evidence, generated results
legacy/                 archived prototypes, see legacy/README.md
weights_*/, new/        trained checkpoints
imgs/                   captured frames (git-ignored: may contain personal data)
```
