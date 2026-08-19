# Pre-FPR remediation

Every finding from the verification pass, and what was done about it. Finding
IDs match the review so the two can be read side by side.

---

## Blocking

| ID | Finding | Resolution |
|---|---|---|
| SEC-1 | Gmail app password in plaintext in `mailing in python.py`, tracked and pushed | File deleted and untracked. SMTP config moved to environment variables (`.env.example`, `surveillance/config.py`). `.gitignore` added covering `.env`. A test now fails if any tracked Python file hard-codes an SMTP login. **The credential itself still needs revoking, and the git history still needs rewriting — see "Still outstanding".** |

---

## Documents versus artefacts

| ID | Finding | Resolution |
|---|---|---|
| EVID-1 | IPR abstract claimed local "Ryzen GPU" training | Corrected to cloud training on Google Colab with local CPU inference, in both the IPR abstract and the proposal's project description. Recorded in `docs/MODEL_CARD.md` with the Drive paths as evidence. |
| EVID-2 | Gantt marks custom training *Pending*; checkpoints are 18 months older | **Deliberately not changed.** Back-dating a submitted progress table would replace one inaccuracy with a worse one. The honest place to reconcile this is FPR §5.4 Project Management Reflection. |
| EVID-3 | Documents said YOLOv8; everything built is YOLO11 | Corrected in all four places in the IPR, in the proposal, and in both reference lists (now `Jocher, G., & Qiu, J. (2024). Ultralytics YOLO11`). |

---

## Missing objectives

| ID | Objective | Resolution |
|---|---|---|
| GAP-2 | Anomaly detection from behavioural patterns | **Built.** `surveillance/analytics.py`: centroid tracking, dwell-time loitering detection, and weapon-to-person association by box containment. 21 unit tests. |
| GAP-3 | Automated alerts by email or SMS | **Email built.** `surveillance/channels/email.py`, wired through `AlertManager` and dispatched off the capture thread. SMS is not implemented and is now stated as out of scope. |
| GAP-4 | Web-based admin dashboard with event logs | **Built.** `surveillance/web/`: live MJPEG streams per camera, alert log with snapshots and filters, acknowledgement, and runtime threshold configuration. 17 route tests. |
| GAP-5 | Multiple cameras, USB and Wi-Fi | **Built.** Cameras are configured in `config.yaml`; an integer is a USB device index and a URL is an RTSP/HTTP stream. One `CameraWorker` thread per camera. |
| GAP-6 | Event log and retention | **Built.** `surveillance/storage.py`: SQLite alert log, snapshots written only for alerts, hourly retention purge. 14 tests including the retention path. |
| GAP-1 | Facial recognition of known individuals | **Not built — moved to Future Work.** Matching against a gallery of known individuals is a separate research problem from the single-class face *detector* that exists. See the model card. |

---

## Code defects

| ID | Finding | Resolution |
|---|---|---|
| CODE-1 | `4window.py` panels shared one buffer (`a = b = c = frame`) | Fixed in the archived script with `.copy()` per panel; the replacement renderer (`surveillance/render.py`) copies by default. |
| CODE-2 | `second_main.py` raised `TypeError` on first detection; `q` could not quit | Rewritten: integer box coordinates, display and key handling moved into the frame loop. |
| CODE-3 | Alert path slept 1 s inside the capture loop, no cooldown, placeholder text | `AlertManager` debounces on consecutive frames, applies a per-event cooldown, and dispatches on a worker thread. A test asserts `submit()` returns in under 200 ms even with a channel that sleeps for a second, and that 100 alerting frames produce one alert. |
| CODE-4 | Fire and smoke never raised an alert | Both are now first-class events with their own rules. Also fixed in the archived `1window.py`. |
| CODE-5 | Scripts disagreed on models; loaded `last.pt`; ignored the trained person model | One entry point (`run.py`), one config. A test asserts every configured detector uses `best.pt`. |
| CODE-6 | `requirements.txt` listed TensorFlow, Keras, Flask, mtcnn… none imported; `plyer` missing | Rewritten to the six packages actually used. |
| CODE-7 | `new.py` pointed at a non-existent directory; invisible label at `(0,0)`; hard-coded class names; inconsistent thresholds; stretched aspect ratio | All fixed. Class names now read from `model.names`; `surveillance/geometry.py` letterboxes instead of stretching; thresholds live in one config. |

---

## Model and evidence

| ID | Finding | Resolution |
|---|---|---|
| PERF-1 | Fire model false-positives at 84% on a handgun photo | Documented rather than hidden. `docs/MODEL_CARD.md` describes it; the image is preserved at `docs/evidence/fire-false-positive-on-handgun.jpg`. Mitigations: threshold raised to 0.50, four consecutive frames required. `tools/evaluate.py --confusion` finds the whole class of error. |
| PERF-2 | Face model checkpoint is degenerate (P 0.350 at R 1.000) | Documented in the model card with the reason (fitness-based selection). Not used by the system. |
| PERF-3 | All metrics are validation, not held-out | `tools/evaluate.py --validate` added for a proper test split. The model card states plainly that the current numbers are validation metrics and must not be quoted as generalisation performance. |
| METH-1 | All test evidence is a webcam pointed at a monitor | Flagged in the model card. A real held-out set still has to be collected — see "Still outstanding". |
| METH-2 | No dataset provenance anywhere | `tools/inspect_models.py` recovers the dataset yaml path, hyperparameters and metrics from each checkpoint without needing PyTorch. Source, licence and split sizes still have to be recovered from Drive. |

---

## Report text

| ID | Finding | Resolution |
|---|---|---|
| IPR-1 | Filename said "Ahmed Shah" | Renamed to `IPR - Ahmed Raza.docx`; original kept as `.bak`. |
| IPR-2 | Five spelling errors inside the diagram images | All six figures regenerated from source (`tools/make_diagrams.py`) as both SVG and PNG. Text now lives in a file a spell-checker can reach. |
| IPR-3 | Sentences that do not parse | Rewritten: the abstract's opening, "CPU that is dedicated to a GPU", the "common in 2. Custom Training" artefact, and two literature-review sentences. |
| IPR-4 | Reported as mojibake in the review | **Correction to the review:** the character was a proper `‘` — my extraction could not encode it. The real defect was a mismatched quote pair and the term "alerts fatigue"; both fixed to "alert fatigue". |
| IPR-5 | §2.1 heading "Foundational Heuristics and Simulation Toolkits" | Renamed to "Foundational Computer Vision Libraries" in the body and the table of contents. |
| IPR-6 | First-person plural in a single-author report | Rewritten impersonally, without changing the progress claims. |
| PROP-1 | Research question written as a statement | Rewritten as a question, with a hypothesis carrying three measurable targets (mAP@50 ≥ 0.80, ≥ 5 fps CPU-only, alert within 2 s). |
| PROP-2 | "Error-free monitoring", "significantly improve" | Replaced with the measurable criteria above. |
| PROP-3 | No dataset provenance | Tooling added; the data itself still has to be recovered. |
| PROP-4 | Six references | Only the Ultralytics citation was corrected. Expanding to 40–60 belongs to FPR drafting, where each source can be verified rather than asserted. |

---

## UML

All six figures regenerated to match the system as built.

| ID | Finding | Resolution |
|---|---|---|
| UML-1 | Activity diagram showed face detection, omitted fire | Now forks into person / weapon / fire-smoke, and includes the debounce and cooldown gates. |
| UML-2 | Component and sequence diagrams disagreed on frame routing | Both now follow the code: camera → CameraWorker → DetectorBundle → AnalyticsEngine → AlertManager. |
| UML-3 | "Person Identification" overstated the model | Renamed to person detection, in the diagram and in IPR §3.1. |
| UML-4 | Mixed `«extend»`/`«extends»`, wrong relationship direction | One keyword throughout; `«include»` points from base to included behaviour, `«extend»` from the optional behaviour to the base. The figure carries a note stating the rule. |
| UML-5 | Deployment diagram showed USB only | Now shows both a USB camera and an RTSP camera, plus the browser and SMTP relay. |
| UML-6 | Mixed arrow semantics in the alt fragment | Solid for calls, dashed for returns, consistently. |

---

## Still outstanding

These need a person, not a patch.

1. **Revoke the Gmail app password** at Google Account → Security → App passwords. Deleting the file does not invalidate the credential, and it remains in the git history.
2. **Rewrite the git history** (`git filter-repo`) or make the repository private.
3. **Collect a held-out test set** of real images, separate from the validation split, and run `tools/evaluate.py --validate`. Chapters 4.3 and 4.4 have no foundation without it.
4. **Recover dataset provenance** from the Colab Drive folders: source, licence, image count, split sizes.
5. **Run `tools/evaluate.py --benchmark`** on the target machine to get real latency figures for the real-time claim.
6. **Expand the bibliography** to 40–60 verified sources.
7. **Add the FPR front matter**: Declaration, Proof-reading and Quality Assurance Statement, List of Figures, List of Tables, Glossary.
8. **End-to-end run with a live camera.** The test suite covers everything except model inference, which needs OpenCV and PyTorch installed. Start with `python run.py --check`.
