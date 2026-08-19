#!/usr/bin/env python3
"""Evaluation harness for the Final Project Report.

Three things the project could not previously report:

``--validate``  runs each model against a dataset split and prints precision,
                recall, mAP@50 and mAP@50-95. Point it at a *test* split, not
                the validation split the models were tuned on - the numbers
                baked into the checkpoints are validation numbers and cannot be
                quoted as held-out performance.

``--benchmark`` measures per-model and end-to-end inference latency on this
                machine, which is the evidence for any real-time claim.

``--confusion`` runs the whole detector bundle over a folder of images and
                reports what each model fires on. Aimed at cross-model false
                positives - the fire model scoring 84% on a photograph of a
                handgun is the case that motivated it.

Results are written as CSV and JSON so they can go straight into the report.

    python tools/evaluate.py --validate --data path/to/test_data.yaml
    python tools/evaluate.py --benchmark --iterations 100
    python tools/evaluate.py --confusion --images imgs/
"""

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from surveillance.config import PROJECT_ROOT, load_config  # noqa: E402

RESULTS_DIR = PROJECT_ROOT / "docs" / "results"


def _write(name, rows, fieldnames):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / (name + ".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    (RESULTS_DIR / (name + ".json")).write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )
    print("\nwrote {} and {}".format(csv_path.name, name + ".json"))
    print("  -> {}".format(RESULTS_DIR))


def validate(config, data_yaml, split="test", imgsz=640):
    """Evaluate every enabled detector on a dataset split."""
    from ultralytics import YOLO

    rows = []
    print("Validating on {} (split: {})\n".format(data_yaml, split))
    header = "{:<10} {:>10} {:>10} {:>10} {:>12} {:>8}".format(
        "detector", "precision", "recall", "mAP@50", "mAP@50-95", "images")
    print(header)
    print("-" * len(header))

    for detector in config.enabled_detectors:
        model = YOLO(str(PROJECT_ROOT / detector.weights))
        metrics = model.val(data=data_yaml, split=split, imgsz=imgsz, verbose=False)
        box = metrics.box
        row = {
            "detector": detector.id,
            "weights": detector.weights,
            "split": split,
            "precision": round(float(box.mp), 4),
            "recall": round(float(box.mr), 4),
            "mAP50": round(float(box.map50), 4),
            "mAP50_95": round(float(box.map), 4),
            "images": int(getattr(metrics, "seen", 0) or 0),
        }
        rows.append(row)
        print("{:<10} {:>10.4f} {:>10.4f} {:>10.4f} {:>12.4f} {:>8}".format(
            row["detector"], row["precision"], row["recall"],
            row["mAP50"], row["mAP50_95"], row["images"]))

    _write("held_out_metrics", rows,
           ["detector", "weights", "split", "precision", "recall",
            "mAP50", "mAP50_95", "images"])
    return rows


def benchmark(config, iterations=50, size=(480, 640)):
    """Measure inference latency per detector and for the full bundle."""
    import numpy as np

    from surveillance.detectors import DetectorBundle

    bundle = DetectorBundle(config.enabled_detectors)
    bundle.load()

    rng = np.random.default_rng(0)
    frame = rng.integers(0, 255, (size[0], size[1], 3), dtype=np.uint8)

    print("Warming up...")
    for _ in range(5):
        bundle.detect(frame)

    print("Benchmarking {} iterations at {}x{}\n".format(iterations, size[1], size[0]))
    per_detector = {d.id: [] for d in config.enabled_detectors}
    totals = []

    for _ in range(iterations):
        started = time.perf_counter()
        _, timings = bundle.detect(frame)
        totals.append((time.perf_counter() - started) * 1000.0)
        for detector_id, elapsed in timings.items():
            per_detector[detector_id].append(elapsed)

    rows = []
    header = "{:<12} {:>10} {:>10} {:>10} {:>10}".format(
        "stage", "mean ms", "median", "p95", "max fps")
    print(header)
    print("-" * len(header))

    for name, samples in list(per_detector.items()) + [("END-TO-END", totals)]:
        if not samples:
            continue
        ordered = sorted(samples)
        p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
        mean = statistics.mean(samples)
        row = {
            "stage": name,
            "mean_ms": round(mean, 2),
            "median_ms": round(statistics.median(samples), 2),
            "p95_ms": round(p95, 2),
            "max_fps": round(1000.0 / mean, 1) if mean else 0.0,
            "iterations": len(samples),
        }
        rows.append(row)
        print("{:<12} {:>10.2f} {:>10.2f} {:>10.2f} {:>10.1f}".format(
            row["stage"], row["mean_ms"], row["median_ms"],
            row["p95_ms"], row["max_fps"]))

    print("\nNote: the three detectors run in sequence, so end-to-end latency is")
    print("roughly their sum. This is the cost of three single-purpose models")
    print("rather than one multi-class model.")

    _write("latency_benchmark", rows,
           ["stage", "mean_ms", "median_ms", "p95_ms", "max_fps", "iterations"])
    return rows


def confusion(config, image_dir):
    """Report what every detector fires on across a folder of images."""
    import cv2

    from surveillance.detectors import DetectorBundle

    image_dir = Path(image_dir)
    patterns = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp")
    images = sorted(p for pattern in patterns for p in image_dir.glob(pattern))
    if not images:
        print("no images found in {}".format(image_dir))
        return []

    bundle = DetectorBundle(config.enabled_detectors)
    bundle.load()

    rows = []
    print("Scanning {} image(s) in {}\n".format(len(images), image_dir))
    for path in images:
        frame = cv2.imread(str(path))
        if frame is None:
            print("  skipped unreadable file: {}".format(path.name))
            continue

        detections, _ = bundle.detect(frame)
        by_detector = {}
        for detection in detections:
            best = by_detector.get(detection.detector)
            if best is None or detection.confidence > best.confidence:
                by_detector[detection.detector] = detection

        row = {"image": path.name, "detectors_fired": len(by_detector)}
        for detector in config.enabled_detectors:
            hit = by_detector.get(detector.id)
            row[detector.id + "_label"] = hit.label if hit else ""
            row[detector.id + "_conf"] = round(hit.confidence, 3) if hit else 0.0
        rows.append(row)

        summary = ", ".join(
            "{}={} {:.0%}".format(d, h.label, h.confidence)
            for d, h in sorted(by_detector.items())
        ) or "nothing"
        flag = "  <-- MULTIPLE DETECTORS" if len(by_detector) > 1 else ""
        print("  {:<44} {}{}".format(path.name[:44], summary, flag))

    multiple = [r for r in rows if r["detectors_fired"] > 1]
    print("\n{} of {} image(s) fired more than one detector.".format(
        len(multiple), len(rows)))
    if multiple:
        print("Each is a candidate cross-model false positive and belongs in the")
        print("report's error analysis, not just in the summary metrics.")

    fieldnames = ["image", "detectors_fired"]
    for detector in config.enabled_detectors:
        fieldnames += [detector.id + "_label", detector.id + "_conf"]
    _write("cross_model_confusion", rows, fieldnames)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=None)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--confusion", action="store_true")
    parser.add_argument("--data", help="dataset yaml for --validate")
    parser.add_argument("--split", default="test", choices=["train", "val", "test"])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--images", default="imgs", help="image folder for --confusion")
    args = parser.parse_args(argv)

    if not (args.validate or args.benchmark or args.confusion):
        parser.error("choose at least one of --validate, --benchmark, --confusion")

    config = load_config(args.config)

    if args.validate:
        if not args.data:
            parser.error("--validate needs --data path/to/data.yaml")
        validate(config, args.data, args.split, args.imgsz)
    if args.benchmark:
        benchmark(config, args.iterations)
    if args.confusion:
        confusion(config, args.images)

    return 0


if __name__ == "__main__":
    sys.exit(main())
