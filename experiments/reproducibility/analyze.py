#!/usr/bin/env python3
"""Analyze reproducibility experiment outputs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
RESULTS_PATH = BASE_DIR / "results.json"
REPORT_PATH = BASE_DIR / "results_report.md"


def _top_hash_stats(rows: list[dict[str, Any]]) -> tuple[str, int]:
    hashes = [r.get("sha256_hash", "") for r in rows if r.get("sha256_hash")]
    if not hashes:
        return "N/A", 0
    top_hash, count = Counter(hashes).most_common(1)[0]
    return top_hash, count


def _count_valid(rows: list[dict[str, Any]]) -> tuple[int, int]:
    valid = sum(1 for r in rows if r.get("valid") is True)
    total = len(rows)
    return valid, total


def build_report(data: dict[str, Any]) -> str:
    rows = data.get("runs", [])
    summary = data.get("summary", {})

    nail_rows = [r for r in rows if r.get("lang") == "nail"]
    py_rows = [r for r in rows if r.get("lang") == "python"]

    nail_top_hash, nail_top_count = _top_hash_stats(nail_rows)
    py_top_hash, py_top_count = _top_hash_stats(py_rows)
    nail_valid, nail_total = _count_valid(nail_rows)

    lines: list[str] = []
    lines.append("# Reproducibility Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- NAIL unique hashes: **{summary.get('nail_unique_hashes', 'N/A')}**")
    lines.append(f"- Python unique hashes: **{summary.get('python_unique_hashes', 'N/A')}**")
    lines.append(f"- NAIL match rate: **{summary.get('nail_match_rate', 'N/A')}**")
    lines.append(f"- Python match rate: **{summary.get('python_match_rate', 'N/A')}**")
    lines.append(f"- NAIL valid runs: **{nail_valid}/{nail_total}**")
    lines.append("")
    lines.append("## Most Frequent Output Hash")
    lines.append("")
    lines.append(f"- NAIL: `{nail_top_hash}` ({nail_top_count} runs)")
    lines.append(f"- Python: `{py_top_hash}` ({py_top_count} runs)")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("Lower unique-hash count and higher match rate indicate higher output reproducibility.")
    lines.append("For NAIL, canonical JSON normalization removes key-order variance before hashing.")

    return "\n".join(lines) + "\n"


def main() -> int:
    if not RESULTS_PATH.exists():
        raise FileNotFoundError(f"results.json not found: {RESULTS_PATH}")

    data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    rows = data.get("runs", [])
    summary = data.get("summary", {})

    nail_rows = [r for r in rows if r.get("lang") == "nail"]
    py_rows = [r for r in rows if r.get("lang") == "python"]
    nail_valid, nail_total = _count_valid(nail_rows)

    print("=== Reproducibility Comparison ===")
    print(f"NAIL runs: {len(nail_rows)}")
    print(f"Python runs: {len(py_rows)}")
    print(f"NAIL valid runs: {nail_valid}/{nail_total}")
    print(f"NAIL unique hashes: {summary.get('nail_unique_hashes', 'N/A')}")
    print(f"Python unique hashes: {summary.get('python_unique_hashes', 'N/A')}")
    print(f"NAIL match rate: {summary.get('nail_match_rate', 'N/A')}")
    print(f"Python match rate: {summary.get('python_match_rate', 'N/A')}")

    report = build_report(data)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Saved report: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
