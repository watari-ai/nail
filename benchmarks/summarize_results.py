#!/usr/bin/env python3
"""
NAIL Benchmark Result Summarizer
Issue #103: Multi-LLM Verify-Fix Loop

Reads benchmarks/results/*.csv files and produces:
  - Per-model pass rate and average attempts
  - Per-task pass rate
  - Consensus rate: fraction of tasks where ALL models agree on pass/fail

Usage:
    python benchmarks/summarize_results.py
    python benchmarks/summarize_results.py --output json
    python benchmarks/summarize_results.py --input path/to/result.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"


# ── Loading ──────────────────────────────────────────────────────────────────

def load_csv(path: Path) -> list[dict]:
    """Load a single CSV file, normalise types."""
    rows: list[dict] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append({
                "model":       row["model"],
                "task":        row["task"],
                "attempts":    int(row["attempts"]),
                "final_pass":  bool(int(row["final_pass"])),
                "error_codes": row.get("error_codes", ""),
                "latency_ms":  float(row.get("latency_ms", 0)),
            })
    return rows


def load_all(glob: str = "verify_fix_loop_*.csv", extra: list[Path] | None = None) -> list[dict]:
    """Load all matching CSVs from RESULTS_DIR plus any extra paths."""
    rows: list[dict] = []
    paths = list(RESULTS_DIR.glob(glob)) + (extra or [])
    if not paths:
        return rows
    for p in sorted(paths):
        rows.extend(load_csv(p))
    return rows


# ── Analysis ──────────────────────────────────────────────────────────────────

def summarize(rows: list[dict]) -> dict:
    """
    Compute summary statistics from benchmark rows.

    Returns a dict with:
      - per_model:  {model: {pass_rate, avg_attempts, total}}
      - per_task:   {task:  {pass_rate, avg_attempts, total}}
      - consensus:  {task:  consensus_rate}  (fraction of models that agreed)
      - overall:    {pass_rate, avg_attempts, total, consensus_rate}
    """
    if not rows:
        return {
            "per_model": {},
            "per_task": {},
            "consensus": {},
            "overall": {"pass_rate": None, "avg_attempts": None, "total": 0, "consensus_rate": None},
        }

    # ── per-model ────────────────────────────────────────────────────────────
    model_groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        model_groups[r["model"]].append(r)

    per_model: dict[str, dict] = {}
    for model, mrs in model_groups.items():
        passes = sum(1 for r in mrs if r["final_pass"])
        per_model[model] = {
            "pass_rate":    round(passes / len(mrs), 3),
            "avg_attempts": round(sum(r["attempts"] for r in mrs) / len(mrs), 2),
            "total":        len(mrs),
            "passed":       passes,
        }

    # ── per-task ─────────────────────────────────────────────────────────────
    task_groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        task_groups[r["task"]].append(r)

    per_task: dict[str, dict] = {}
    for task, trs in task_groups.items():
        passes = sum(1 for r in trs if r["final_pass"])
        per_task[task] = {
            "pass_rate":    round(passes / len(trs), 3),
            "avg_attempts": round(sum(r["attempts"] for r in trs) / len(trs), 2),
            "total":        len(trs),
            "passed":       passes,
        }

    # ── consensus rate per task ───────────────────────────────────────────────
    # consensus = fraction of (task, model) groups where the final verdict
    # matches the majority verdict for that task
    consensus: dict[str, float] = {}
    for task, trs in task_groups.items():
        majority_pass = (sum(1 for r in trs if r["final_pass"]) / len(trs)) >= 0.5
        agreed = sum(1 for r in trs if r["final_pass"] == majority_pass)
        consensus[task] = round(agreed / len(trs), 3)

    # ── overall ───────────────────────────────────────────────────────────────
    total = len(rows)
    total_pass = sum(1 for r in rows if r["final_pass"])
    overall_consensus = round(
        sum(consensus.values()) / len(consensus), 3
    ) if consensus else None

    overall = {
        "pass_rate":       round(total_pass / total, 3) if total else None,
        "avg_attempts":    round(sum(r["attempts"] for r in rows) / total, 2) if total else None,
        "total":           total,
        "consensus_rate":  overall_consensus,
    }

    return {
        "per_model": per_model,
        "per_task":  per_task,
        "consensus": consensus,
        "overall":   overall,
    }


# ── Display ───────────────────────────────────────────────────────────────────

def _pct(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.1f}%"


def print_summary(summary: dict) -> None:
    print("\n" + "=" * 64)
    print("NAIL VERIFY-FIX LOOP — BENCHMARK SUMMARY")
    print("=" * 64)

    # Per-model table
    print("\n▶ Per-Model Results")
    print(f"  {'Model':<30} {'PassRate':>9} {'AvgTries':>9} {'N':>4}")
    print("  " + "-" * 55)
    for model, stat in sorted(summary["per_model"].items()):
        print(f"  {model:<30} {_pct(stat['pass_rate']):>9} {stat['avg_attempts']:>9.2f} {stat['total']:>4}")

    # Per-task table
    print("\n▶ Per-Task Results")
    print(f"  {'Task':<24} {'PassRate':>9} {'AvgTries':>9} {'N':>4}")
    print("  " + "-" * 50)
    for task, stat in sorted(summary["per_task"].items()):
        print(f"  {task:<24} {_pct(stat['pass_rate']):>9} {stat['avg_attempts']:>9.2f} {stat['total']:>4}")

    # Consensus
    print("\n▶ Consensus Rate (models agree on same verdict)")
    print(f"  {'Task':<24} {'Consensus':>10}")
    print("  " + "-" * 36)
    for task, rate in sorted(summary["consensus"].items()):
        print(f"  {task:<24} {_pct(rate):>10}")

    # Overall
    ov = summary["overall"]
    print(f"\n▶ Overall  total={ov['total']}  pass_rate={_pct(ov['pass_rate'])}"
          f"  avg_tries={ov['avg_attempts']}  consensus={_pct(ov['consensus_rate'])}")
    print("=" * 64)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Summarize NAIL benchmark results")
    parser.add_argument("--output", choices=["table", "json"], default="table")
    parser.add_argument("--input", type=Path, action="append", default=None,
                        help="Specific CSV file(s) to load (can repeat)")
    args = parser.parse_args()

    rows = load_all(extra=args.input)

    if not rows:
        print("[warn] No result CSVs found. Run verify_fix_loop.py --save first.")
        sys.exit(0)

    summary = summarize(rows)

    if args.output == "json":
        print(json.dumps(summary, indent=2))
    else:
        print_summary(summary)


if __name__ == "__main__":
    main()
