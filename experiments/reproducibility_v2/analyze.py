#!/usr/bin/env python3
"""Analyze reproducibility experiment v2 outputs.

Usage:
    python analyze.py [--results path/to/results_v2.json]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS_PATH = BASE_DIR / "results_v2.json"
REPORT_PATH = BASE_DIR / "results_v2_report.md"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _unique_hashes(rows: list[dict[str, Any]]) -> list[str]:
    return list({r["sha256_hash"] for r in rows if r.get("sha256_hash")})


def _match_rate(rows: list[dict[str, Any]]) -> str:
    hashes = [r["sha256_hash"] for r in rows if r.get("sha256_hash")]
    if not hashes:
        return "N/A"
    top_count = Counter(hashes).most_common(1)[0][1]
    return f"{(top_count / len(hashes)) * 100:.1f}%"


def _hash_distribution(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    hashes = [r["sha256_hash"] for r in rows if r.get("sha256_hash")]
    return Counter(hashes).most_common()


def _valid_count(rows: list[dict[str, Any]]) -> tuple[int, int]:
    valid = sum(1 for r in rows if r.get("valid") is True)
    return valid, len(rows)


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------


def print_report(data: dict[str, Any]) -> None:
    runs = data.get("runs", [])
    problems = data.get("problems", [])
    runs_per_problem = data.get("runs_per_problem", "?")

    print("=" * 72)
    print("Reproducibility Experiment v2 — Analysis")
    print("=" * 72)
    print(f"Problems: {', '.join(problems)}")
    print(f"Runs per problem per language: {runs_per_problem}")
    print()

    # Per-problem table
    col_w = [22, 8, 8, 10, 8, 10]
    header = (
        f"{'Problem':<{col_w[0]}}"
        f"{'Lang':<{col_w[1]}}"
        f"{'Unique':<{col_w[2]}}"
        f"{'/ Runs':<{col_w[3]}}"
        f"{'Valid':<{col_w[4]}}"
        f"{'MatchRate'}"
    )
    sep = "-" * 72

    print(header)
    print(sep)

    for problem_name in problems:
        for lang in ("nail", "python"):
            rows = [
                r for r in runs
                if r.get("problem") == problem_name and r.get("lang") == lang
            ]
            if not rows:
                continue

            unique = len(_unique_hashes(rows))
            total = len(rows)
            match_rate = _match_rate(rows)

            if lang == "nail":
                valid, _ = _valid_count(rows)
                valid_str = f"{valid}/{total}"
            else:
                valid_str = "N/A"

            print(
                f"{problem_name:<{col_w[0]}}"
                f"{lang:<{col_w[1]}}"
                f"{unique:<{col_w[2]}}"
                f"{f'/ {total}':<{col_w[3]}}"
                f"{valid_str:<{col_w[4]}}"
                f"{match_rate}"
            )

        print()  # blank line between problems

    # Hash distribution detail
    print("=" * 72)
    print("Hash distribution (most common first)")
    print("=" * 72)

    for problem_name in problems:
        for lang in ("nail", "python"):
            rows = [
                r for r in runs
                if r.get("problem") == problem_name and r.get("lang") == lang
            ]
            if not rows:
                continue
            dist = _hash_distribution(rows)
            print(f"\n[{problem_name}] {lang}:")
            for h, count in dist:
                bar = "█" * count
                print(f"  {h[:16]}...  {count:2d}x  {bar}")

    # Overall summary
    print()
    print("=" * 72)
    print("Overall")
    print("=" * 72)
    overall = data.get("summary", {}).get("overall", {})
    if overall:
        nail_total = overall.get("nail_total_runs", "?")
        nail_valid = overall.get("nail_total_valid", "?")
        nail_unique = overall.get("nail_total_unique_hashes", "?")
        py_total = overall.get("python_total_runs", "?")
        py_unique = overall.get("python_total_unique_hashes", "?")

        print(f"NAIL   : {nail_unique} unique hashes / {nail_total} runs (valid: {nail_valid})")
        print(f"Python : {py_unique} unique hashes / {py_total} runs")

        if isinstance(nail_unique, int) and isinstance(py_unique, int):
            ratio = py_unique / nail_unique if nail_unique > 0 else float("inf")
            print(f"Ratio  : Python has {ratio:.1f}x more unique hashes than NAIL")
            if nail_unique < py_unique:
                print("→ NAIL shows higher structural reproducibility ✓")
            elif nail_unique == py_unique:
                print("→ Equal reproducibility (inconclusive)")
            else:
                print("→ Python shows higher reproducibility (unexpected)")


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------


def build_markdown_report(data: dict[str, Any]) -> str:
    runs = data.get("runs", [])
    problems = data.get("problems", [])
    runs_per_problem = data.get("runs_per_problem", "?")
    summary = data.get("summary", {})
    per_problem = summary.get("per_problem", {})
    overall = summary.get("overall", {})

    lines: list[str] = []
    lines.append("# Reproducibility Experiment v2 — Report")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(f"- Problems: {', '.join(f'`{p}`' for p in problems)}")
    lines.append(f"- Runs per problem per language: **{runs_per_problem}**")
    lines.append("")

    lines.append("## Per-Problem Results")
    lines.append("")
    lines.append("| Problem | Language | Unique Hashes | Runs | Valid | Match Rate |")
    lines.append("|---------|----------|:-------------:|:----:|:-----:|:----------:|")

    for name in problems:
        stats = per_problem.get(name, {})
        nail_unique = stats.get("nail_unique_hashes", "?")
        nail_runs = stats.get("nail_runs", "?")
        nail_valid = stats.get("nail_valid", "?")
        nail_match = stats.get("nail_match_rate", "?")
        py_unique = stats.get("python_unique_hashes", "?")
        py_runs = stats.get("python_runs", "?")
        py_match = stats.get("python_match_rate", "?")

        lines.append(f"| `{name}` | NAIL   | **{nail_unique}** | {nail_runs} | {nail_valid}/{nail_runs} | {nail_match} |")
        lines.append(f"| `{name}` | Python | **{py_unique}** | {py_runs} | N/A | {py_match} |")

    lines.append("")
    lines.append("## Hash Distribution")
    lines.append("")

    for name in problems:
        lines.append(f"### `{name}`")
        lines.append("")
        for lang in ("nail", "python"):
            rows = [
                r for r in runs
                if r.get("problem") == name and r.get("lang") == lang
            ]
            dist = _hash_distribution(rows)
            lines.append(f"**{lang.upper()}** — {len(dist)} unique hash(es):")
            lines.append("")
            lines.append("| Hash (first 16 chars) | Count |")
            lines.append("|----------------------|-------|")
            for h, count in dist:
                lines.append(f"| `{h[:16]}...` | {count} |")
            lines.append("")

    lines.append("## Overall")
    lines.append("")
    if overall:
        nail_total = overall.get("nail_total_runs", "?")
        nail_valid = overall.get("nail_total_valid", "?")
        nail_unique = overall.get("nail_total_unique_hashes", "?")
        py_total = overall.get("python_total_runs", "?")
        py_unique = overall.get("python_total_unique_hashes", "?")

        lines.append(f"- NAIL: **{nail_unique}** unique hashes / {nail_total} runs (valid: {nail_valid})")
        lines.append(f"- Python: **{py_unique}** unique hashes / {py_total} runs")

        if isinstance(nail_unique, int) and isinstance(py_unique, int) and nail_unique > 0:
            ratio = py_unique / nail_unique
            lines.append(
                f"- Ratio: Python has **{ratio:.1f}x** more unique hashes than NAIL"
            )

    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "Lower unique-hash count and higher match rate indicate higher output reproducibility. "
        "For NAIL, canonical JSON normalization (JCS) eliminates key-order variance before hashing, "
        "ensuring that structurally identical programs always produce the same hash."
    )
    lines.append("")
    lines.append(
        "Expected outcome: NAIL should produce 2–4 unique hashes per problem "
        "(variation in condition ordering, loop variable naming, etc.), "
        "while Python produces 5–10 unique hashes due to variable names, "
        "comments, blank lines, and stylistic variance."
    )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(results_path: Path) -> int:
    if not results_path.exists():
        print(f"Error: results file not found: {results_path}")
        print("Run `python run.py` first to generate results.")
        return 1

    data = json.loads(results_path.read_text(encoding="utf-8"))

    print_report(data)

    report_md = build_markdown_report(data)
    REPORT_PATH.write_text(report_md, encoding="utf-8")
    print(f"\nMarkdown report saved: {REPORT_PATH}")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze reproducibility v2 results")
    parser.add_argument(
        "--results",
        type=Path,
        default=DEFAULT_RESULTS_PATH,
        help="Path to results_v2.json (default: same directory as this script)",
    )
    args = parser.parse_args()
    raise SystemExit(main(args.results))
