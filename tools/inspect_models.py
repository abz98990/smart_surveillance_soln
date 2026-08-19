#!/usr/bin/env python3
"""Training provenance read straight out of the .pt files.

    python tools/inspect_models.py [--json]

A checkpoint is a zip around a pickle, so this walks it with a restricted
unpickler that stubs every tensor. No torch needed.
"""

import argparse
import io
import json
import pickle
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INTERESTING_ARGS = (
    "model", "data", "epochs", "batch", "imgsz", "optimizer", "lr0",
    "pretrained", "seed", "device", "workers",
)


class _Stub:
    """Stands in for every torch object encountered while unpickling."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return _Stub()

    def __setstate__(self, state):
        self._state = state

    def __repr__(self):
        return "<stub>"


class _RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "collections" and name == "OrderedDict":
            return dict
        if module in ("builtins", "__builtin__") and name == "set":
            return set
        return _Stub

    def persistent_load(self, pid):
        return "<storage>"


def read_checkpoint(path):
    archive = zipfile.ZipFile(path)
    entry = next(n for n in archive.namelist() if n.endswith("data.pkl"))
    return _RestrictedUnpickler(io.BytesIO(archive.read(entry))).load()


def describe(path):
    """Return a provenance record for one checkpoint."""
    checkpoint = read_checkpoint(path)
    model_state = getattr(checkpoint.get("model"), "_state", {}) or {}
    args = checkpoint.get("train_args") or model_state.get("args") or {}
    metrics = checkpoint.get("train_metrics") or {}
    results = checkpoint.get("train_results") or {}

    final_epoch = {}
    if isinstance(results, dict):
        for key, series in results.items():
            if isinstance(series, list) and series:
                final_epoch[key] = series[-1]

    names = model_state.get("names") or {}
    data_path = args.get("data", "")

    return {
        "weights": str(Path(path).relative_to(PROJECT_ROOT)),
        "size_mb": round(Path(path).stat().st_size / (1024 * 1024), 2),
        "trained_on": checkpoint.get("date", ""),
        "ultralytics_version": checkpoint.get("version", ""),
        "architecture": args.get("model", ""),
        "classes": {int(k): v for k, v in names.items()} if names else {},
        "num_classes": model_state.get("nc", len(names)),
        "dataset_yaml": data_path,
        "trained_in_cloud": "/content/" in str(data_path),
        "hyperparameters": {k: args.get(k) for k in INTERESTING_ARGS if k in args},
        "saved_epoch_metrics": {
            "precision": metrics.get("metrics/precision(B)"),
            "recall": metrics.get("metrics/recall(B)"),
            "mAP50": metrics.get("metrics/mAP50(B)"),
            "mAP50_95": metrics.get("metrics/mAP50-95(B)"),
            "fitness": metrics.get("fitness"),
        },
        "final_epoch_metrics": {
            "epoch": final_epoch.get("epoch"),
            "precision": final_epoch.get("metrics/precision(B)"),
            "recall": final_epoch.get("metrics/recall(B)"),
            "mAP50": final_epoch.get("metrics/mAP50(B)"),
            "mAP50_95": final_epoch.get("metrics/mAP50-95(B)"),
        },
        "training_seconds": final_epoch.get("time"),
    }


def find_checkpoints(root):
    return sorted(
        p for p in Path(root).rglob("best.pt")
        if "venv" not in p.parts and "runs" not in p.parts
    )


def print_report(records):
    print("Model provenance")
    print("=" * 78)
    for record in records:
        print("\n{}  ({} MB)".format(record["weights"], record["size_mb"]))
        print("  trained        {} with ultralytics {}".format(
            record["trained_on"][:19], record["ultralytics_version"]))
        print("  architecture   {}".format(record["architecture"]))
        print("  classes        {}".format(
            ", ".join("{}={}".format(k, v) for k, v in record["classes"].items())
            or "(unnamed)"))
        print("  dataset        {}".format(record["dataset_yaml"] or "(not recorded)"))
        if record["trained_in_cloud"]:
            print("                 ^ a Google Colab path: this model was NOT "
                  "trained locally")
        hyper = record["hyperparameters"]
        print("  hyperparams    epochs={} batch={} imgsz={} optimizer={} lr0={}".format(
            hyper.get("epochs"), hyper.get("batch"), hyper.get("imgsz"),
            hyper.get("optimizer"), hyper.get("lr0")))
        if record["training_seconds"]:
            print("  wall clock     {:.0f} s ({:.1f} min)".format(
                record["training_seconds"], record["training_seconds"] / 60))

        saved = record["saved_epoch_metrics"]
        final = record["final_epoch_metrics"]
        print("  {:<14} {:>10} {:>10} {:>10} {:>12}".format(
            "", "precision", "recall", "mAP@50", "mAP@50-95"))
        for label, block in (("saved (best)", saved), ("final epoch", final)):
            if block.get("precision") is None:
                continue
            print("  {:<14} {:>10.4f} {:>10.4f} {:>10.4f} {:>12.4f}".format(
                label, block["precision"], block["recall"],
                block["mAP50"], block["mAP50_95"]))

        if (saved.get("precision") or 1) < 0.5 and (saved.get("recall") or 0) > 0.95:
            print("  [!] the saved checkpoint has near-total recall at very low")
            print("      precision: it fires on almost everything. Ultralytics")
            print("      picked it on fitness (0.9*mAP50-95 + 0.1*mAP50), which")
            print("      does not penalise that. Do not quote its mAP as")
            print("      generalisation performance.")

    print("\n" + "=" * 78)
    cloud = [r for r in records if r["trained_in_cloud"]]
    if cloud:
        print("{} of {} model(s) were trained in Google Colab. Any claim of local"
              .format(len(cloud), len(records)))
        print("GPU training is contradicted by these files.")
    print("\nEvery dataset yaml above must be cited in the report's data")
    print("collection section with its source, licence, size and splits.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(PROJECT_ROOT))
    parser.add_argument("--json", action="store_true", help="emit JSON instead")
    args = parser.parse_args(argv)

    checkpoints = find_checkpoints(args.root)
    if not checkpoints:
        print("no best.pt checkpoints found under {}".format(args.root),
              file=sys.stderr)
        return 1

    records = [describe(path) for path in checkpoints]
    if args.json:
        print(json.dumps(records, indent=2, default=str))
    else:
        print_report(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
