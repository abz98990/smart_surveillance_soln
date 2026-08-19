# Model card

Five checkpoints, all fine-tuned from a nano-scale YOLO backbone at 640 px.
Every figure below comes from a run artefact in `docs/training_runs/` or from
the checkpoint metadata itself. Regenerate with:

```bash
python tools/inspect_models.py
```

```bash
python tools/summarise_runs.py --write
```

## Production models

| Model | Weights | Classes | Epochs | Batch | Precision | Recall | mAP@50 | mAP@50-95 | Wall clock |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Person | `weights_people/best.pt` | `person` | 33 | 16 | 0.871 | 0.811 | 0.860 | 0.572 | 79.9 min |
| Handgun | `weights_gun/best.pt` | `Handgun` | 60 | 32 | 0.879 | 0.728 | 0.836 | 0.710 | 34.8 min |
| Fire/smoke | `weights_fire/best.pt` | `fire`, `smoke` | 40 | 64 | 0.537 | 0.458 | 0.458 | 0.200 | 45.4 min |

Optimiser `auto`, `lr0 = 0.01`, `pretrained = true`, `seed = 0` throughout.

**These are validation metrics, not held-out test metrics.** They are the score
of the epoch Ultralytics saved as `best.pt`, measured on the same split that
selected it, so they are optimistically biased and must not be presented as
generalisation performance. For quotable numbers, build a test split no model
has seen and run:

```bash
python tools/evaluate.py --validate --data path/to/test_data.yaml --split test
```

## The aggregate hides the fire model's real behaviour

Reporting the fire checkpoint as a single mAP of 0.458 is misleading. Its two
classes are far apart:

| Class | AP@50 | Precision | Recall | Val instances |
|---|---:|---:|---:|---:|
| `fire` | **0.648** | 0.629 | 0.686 | 649 |
| `smoke` | **0.269** | 0.447 | 0.303 | 323 |

Per-class AP is read from `docs/training_runs/yolo11n-fire/PR_curve.png`;
precision, recall and instance counts are derived from the confusion matrix in
the same folder, at its default operating point.

Confusion matrix, fire model (columns are ground truth):

| Predicted ↓ / True → | fire | smoke | background |
|---|---:|---:|---:|
| fire | 445 | 2 | **260** |
| smoke | 4 | 98 | **117** |
| background (missed) | 200 | 223 | — |

Two things follow.

**Smoke is the weak class, not the model.** It misses roughly seven of every
ten smoke instances. The fire class on its own is workable.

**The 260 background regions classified as fire are the false-positive
behaviour seen in the field.** That is a false positive for every 2.5 genuine
fire instances, and it is the same failure that produced an 84%-confidence
"fire" on a photograph of a handgun — preserved at
`docs/evidence/fire-false-positive-on-handgun.jpg`.

### What the system does about it

`config.yaml` gives the two classes separate operating points rather than one
shared threshold:

```yaml
conf: 0.50
class_conf:
  fire: 0.50
  smoke: 0.70
```

Smoke also needs four consecutive frames before it raises anything, and it is
`warning` severity rather than `critical`. The reasoning is recorded in the
config next to the numbers, and a test asserts smoke stays stricter than fire.

## Handgun model

| | Value |
|---|---:|
| Val instances | 206 |
| Correctly detected | 169 |
| Missed | 37 |
| Background false positives | 64 |

At the confusion matrix's operating point that is recall 0.820 and precision
0.725; at the optimal-F1 point the run reports 0.728 / 0.879. Both are honest,
they are just different points on the same curve — say which one you are
quoting. At mAP@50-95 = 0.710 on a nano backbone this is the strongest result
in the project and should lead the results chapter.

## Architecture comparison: YOLO11n vs YOLO12n

Both architectures were trained on the same two datasets with identical epochs,
batch size, image size and seed. This is the evidence for choosing YOLO11n, a
choice the earlier drafts asserted without support.

| Task | Architecture | Precision | Recall | mAP@50 | mAP@50-95 | Wall clock |
|---|---|---:|---:|---:|---:|---:|
| Fire | `yolo11n` | 0.5372 | 0.4582 | **0.4583** | **0.1995** | 2722 s |
| Fire | `yolo12n` | 0.5155 | 0.4521 | 0.4305 | 0.1772 | 2578 s |
| Handgun | `yolo11n` | 0.8785 | 0.7282 | 0.8360 | **0.7103** | 2089 s |
| Handgun | `yolo12n` | 0.8765 | 0.7039 | **0.8420** | 0.6958 | 1916 s |

**Conclusion: YOLO11n wins on both tasks at tight localisation.** It leads
mAP@50-95 by 11.2% relative on fire and 2.0% on handguns. YOLO12n is marginally
ahead on handgun mAP@50 (+0.7%), meaning it finds roughly as many objects but
places the boxes less precisely. YOLO12n trains 6–8% faster.

For a surveillance system where a box position feeds a downstream
weapon-to-person association test, tight localisation matters more than a
fractional gain at loose IoU. YOLO11n is therefore the production choice, and
the YOLO12n checkpoints are kept at `weights_gun_v12/` and `weights_fire_v12/`
so the comparison is reproducible.

## Face demonstrator — not in the pipeline

`new/best.pt` is a single-class detector for one individual, trained on a very
small dataset: 50 epochs in 161 seconds implies tens of images. Its saved
checkpoint scores precision 0.350 at recall 1.000 — it fires on almost
anything. Ultralytics selected it on fitness (`0.9·mAP@50-95 + 0.1·mAP@50`),
which does not penalise that. The final epoch was far better (0.997 / 0.971),
but neither figure supports a generalisation claim.

It is **not wired into the running system**. Face *recognition* — matching
against a gallery of known individuals — is a different problem from
single-class face detection, and is out of scope.

## Training environment

All models were trained in **Google Colab**, not on local hardware. Every
`args.yaml` records a dataset path under `/content/gdrive/MyDrive/`:

| Model | Dataset manifest | Est. train images |
|---|---|---:|
| Person | `/content/gdrive/MyDrive/YOLOv11/data.yaml` | not recoverable |
| Handgun | `/content/gdrive/MyDrive/gun_training_data/gun_data.yaml` | ≈ 1,340 |
| Fire/smoke | `/content/gdrive/MyDrive/fire_training_data/fire_data.yaml` | ≈ 2,120 |
| Face | `/content/gdrive/MyDrive/HenryYOLO/config.yaml` | tens |

Training-set sizes are **estimates**, derived from the highest `train_batch*`
index in each run divided by the epoch count and multiplied by the batch size.
Validation instance counts (649 fire, 323 smoke, 206 handgun) are exact, read
from the confusion matrices.

Inference runs locally on CPU. Training in the cloud and inferring at the edge
is an ordinary split — it just has to be described accurately.

**Still outstanding:** dataset source, licence, exact image counts and split
ratios have to be recovered from the Drive folders. Nothing in the run
artefacts records them, and §3.4 of the report cannot be written without them.

## Shared characteristics

- All models are nano-scale, chosen for CPU inference latency over accuracy.
- All were trained at 640 px; frames are letterboxed, never stretched.
- The three production detectors run **in sequence** per frame, so end-to-end
  latency is roughly their sum. Measure it on the target machine:

```bash
python tools/evaluate.py --benchmark --iterations 100
```

## Reproducing the numbers

| Command | What it gives you |
|---|---|
| `python tools/inspect_models.py` | Provenance and metrics from the checkpoints, no PyTorch needed |
| `python tools/summarise_runs.py` | Per-run and architecture-comparison tables |
| `python tools/evaluate.py --benchmark` | Real inference latency on this machine |
| `python tools/evaluate.py --confusion --images imgs/` | Cross-model false positives |
| `python tools/evaluate.py --validate --data ... --split test` | Held-out metrics |

Figures for the report — PR curves, F1 curves, confusion matrices, per-epoch
loss — are in `docs/training_runs/<run>/`.
