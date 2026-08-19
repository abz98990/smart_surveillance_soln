#!/usr/bin/env python3
"""Turns docs/training_runs/ into report-ready tables.

    python tools/summarise_runs.py [--markdown | --json | --write]

"best" uses the same fitness rule Ultralytics does, 0.9*mAP@50-95 + 0.1*mAP@50,
so the row matches the shipped checkpoint.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "docs" / "training_runs"
RESULTS_DIR = PROJECT_ROOT / "docs" / "results"

METRICS = {
    "precision": "metrics/precision(B)",
    "recall": "metrics/recall(B)",
    "mAP50": "metrics/mAP50(B)",
    "mAP50_95": "metrics/mAP50-95(B)",
}


def fitness(row):
    return 0.9 * row["mAP50_95"] + 0.1 * row["mAP50"]


def read_args(path):
    """Tiny flat-YAML reader: the args files are one `key: value` per line."""
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        values[key.strip()] = value.strip()
    return values


def read_run(directory):
    csv_path = directory / "results.csv"
    if not csv_path.exists():
        return None

    with csv_path.open(encoding="utf-8") as handle:
        raw = [{k.strip(): v for k, v in row.items() if k} for row in csv.DictReader(handle)]

    epochs = []
    for row in raw:
        record = {"epoch": int(float(row.get("epoch", 0) or 0)),
                  "time": float(row.get("time", 0) or 0)}
        for name, column in METRICS.items():
            try:
                record[name] = float(row.get(column, 0) or 0)
            except ValueError:
                record[name] = 0.0
        epochs.append(record)

    if not epochs:
        return None

    args = read_args(directory / "args.yaml")
    best = max(epochs, key=fitness)

    return {
        "run": directory.name,
        "architecture": args.get("model", "?"),
        "dataset": args.get("data", "?"),
        "epochs": len(epochs),
        "batch": args.get("batch", "?"),
        "imgsz": args.get("imgsz", "?"),
        "optimizer": args.get("optimizer", "?"),
        "lr0": args.get("lr0", "?"),
        "seed": args.get("seed", "?"),
        "wall_clock_s": round(epochs[-1]["time"], 1),
        "best": {"epoch": best["epoch"], **{k: round(best[k], 4) for k in METRICS}},
        "final": {"epoch": epochs[-1]["epoch"],
                  **{k: round(epochs[-1][k], 4) for k in METRICS}},
        "curve": epochs,
    }


def discover():
    if not RUNS_DIR.exists():
        return []
    return [r for r in (read_run(d) for d in sorted(RUNS_DIR.iterdir()) if d.is_dir()) if r]


def print_table(runs):
    header = "{:<16} {:<12} {:>7} {:>6} {:>10} {:>8} {:>8} {:>10}".format(
        "run", "architecture", "epochs", "best", "precision", "recall", "mAP@50", "mAP@50-95")
    print(header)
    print("-" * len(header))
    for run in runs:
        best = run["best"]
        print("{:<16} {:<12} {:>7} {:>6} {:>10.4f} {:>8.4f} {:>8.4f} {:>10.4f}".format(
            run["run"], run["architecture"], run["epochs"], best["epoch"],
            best["precision"], best["recall"], best["mAP50"], best["mAP50_95"]))


def print_comparison(runs):
    """Pair runs that share a dataset but differ in architecture."""
    by_task = {}
    for run in runs:
        task = "fire" if "fire" in run["run"] else "gun" if "gun" in run["run"] else run["run"]
        by_task.setdefault(task, []).append(run)

    print("\nARCHITECTURE COMPARISON")
    print("Same dataset, same epochs, same batch size, same seed.\n")

    for task, group in sorted(by_task.items()):
        if len(group) < 2:
            continue
        group.sort(key=lambda r: r["architecture"])
        baseline = group[0]
        print("  {} ({} epochs, batch {}, seed {})".format(
            task, baseline["epochs"], baseline["batch"], baseline["seed"]))
        header = "    {:<12} {:>10} {:>8} {:>8} {:>10} {:>10}".format(
            "architecture", "precision", "recall", "mAP@50", "mAP@50-95", "wall clock")
        print(header)
        print("    " + "-" * (len(header) - 4))
        for run in group:
            best = run["best"]
            print("    {:<12} {:>10.4f} {:>8.4f} {:>8.4f} {:>10.4f} {:>9.0f}s".format(
                run["architecture"], best["precision"], best["recall"],
                best["mAP50"], best["mAP50_95"], run["wall_clock_s"]))

        other = group[1]
        for metric, label in (("mAP50_95", "mAP@50-95"), ("mAP50", "mAP@50")):
            a, b = baseline["best"][metric], other["best"][metric]
            if a == 0:
                continue
            delta = (b - a) / a * 100
            winner = other["architecture"] if b > a else baseline["architecture"]
            print("    -> {}: {} is ahead by {:.1f}%".format(
                label, winner, abs(delta)))
        print()


def markdown(runs):
    lines = ["# Training run comparison", "",
             "Generated by `tools/summarise_runs.py` from the archived run artefacts",
             "in `docs/training_runs/`. `best` is the epoch Ultralytics saved as",
             "`best.pt`, selected on fitness = 0.9·mAP@50-95 + 0.1·mAP@50.", "",
             "| Run | Architecture | Epochs | Batch | Best epoch | Precision | Recall | mAP@50 | mAP@50-95 | Wall clock |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for run in runs:
        best = run["best"]
        lines.append("| {} | `{}` | {} | {} | {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} | {:.0f} s |".format(
            run["run"], run["architecture"], run["epochs"], run["batch"], best["epoch"],
            best["precision"], best["recall"], best["mAP50"], best["mAP50_95"],
            run["wall_clock_s"]))

    lines += ["", "## Datasets", "",
              "| Run | Dataset manifest |", "|---|---|"]
    for run in runs:
        lines.append("| {} | `{}` |".format(run["run"], run["dataset"]))
    lines += ["", "All manifests are Google Colab Drive paths: every model was trained",
              "in the cloud, not on local hardware.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--markdown", action="store_true", help="emit a markdown table")
    parser.add_argument("--json", action="store_true", help="emit JSON, curves included")
    parser.add_argument("--write", action="store_true",
                        help="write CSV/JSON/markdown into docs/results/")
    args = parser.parse_args(argv)

    runs = discover()
    if not runs:
        print("no runs found under {}".format(RUNS_DIR), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(runs, indent=2))
        return 0
    if args.markdown:
        print(markdown(runs))
        return 0

    print_table(runs)
    print_comparison(runs)

    if args.write:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / "run_comparison.md").write_text(markdown(runs), encoding="utf-8")
        (RESULTS_DIR / "run_comparison.json").write_text(
            json.dumps([{k: v for k, v in r.items() if k != "curve"} for r in runs], indent=2),
            encoding="utf-8")
        with (RESULTS_DIR / "run_comparison.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["run", "architecture", "epochs", "batch", "best_epoch",
                             "precision", "recall", "mAP50", "mAP50_95", "wall_clock_s"])
            for run in runs:
                best = run["best"]
                writer.writerow([run["run"], run["architecture"], run["epochs"], run["batch"],
                                 best["epoch"], best["precision"], best["recall"],
                                 best["mAP50"], best["mAP50_95"], run["wall_clock_s"]])
        print("wrote run_comparison.md / .json / .csv to " + str(RESULTS_DIR))

    return 0


if __name__ == "__main__":
    sys.exit(main())
