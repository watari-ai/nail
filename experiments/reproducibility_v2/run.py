#!/usr/bin/env python3
"""Reproducibility experiment v2 runner.

Runs Claude repeatedly on the same tasks in two modes:
- NAIL JSON output (normalized via JCS-style canonical JSON)
- Python function output (raw text)

v2 improvements over v1:
1. Harder tasks (clamp, fibonacci, fizzbuzz_count) instead of trivial add(a,b)
2. NAIL prompt contains schema structure ONLY — no body examples that leak the answer
3. Per-problem grouping in results_v2.json

Usage:
    python run.py            # Run all experiments
    python run.py --dry-run  # Validate imports and prompt construction only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interpreter import CheckError, Checker, NailEffectError, NailTypeError  # noqa: E402

RUNS_PER_PROBLEM = 5
DELAY_SECONDS = 2
RESULTS_PATH = Path(__file__).with_name("results_v2.json")
RUN_UUID = uuid.uuid4().hex[:8]  # unique per execution — prevents session-id reuse across runs

# ---------------------------------------------------------------------------
# Problems
# ---------------------------------------------------------------------------

PROBLEMS = [
    {
        "name": "clamp",
        "spec": "clamp(val:int64, lo:int64, hi:int64) -> int64. Return val clamped to [lo, hi].",
    },
    {
        "name": "fibonacci",
        "spec": "fibonacci(n:int64) -> int64. Return the n-th Fibonacci number (0-indexed).",
    },
    {
        "name": "fizzbuzz_count",
        "spec": (
            "fizzbuzz_count(n:int64) -> int64. "
            "Return how many numbers from 1..n are divisible by 3 or 5."
        ),
    },
]

# ---------------------------------------------------------------------------
# NAIL schema reference (structure only — NO body examples that reveal answers)
# ---------------------------------------------------------------------------

NAIL_SCHEMA_REFERENCE = """\
NAIL v0.2 is a JSON-only programming language. Output a single JSON object.

## Top-level structure
{
  "nail": "0.2",
  "kind": "fn",
  "id": "<function_name>",
  "effects": [],
  "params": [ { "id": "<param_name>", "type": <type_object> }, ... ],
  "returns": <type_object>,
  "body": [ <statement>, ... ]
}

## Type objects
  int64 (signed 64-bit, panics on overflow):
    {"type": "int", "bits": 64, "overflow": "panic"}
  bool:
    {"type": "bool"}

## Expressions
  Literal:      {"lit": <value>}
  Variable ref: {"ref": "<name>"}
  Arithmetic:   {"op": "+"|"-"|"*"|"/"|"%",   "l": <expr>, "r": <expr>}
  Comparison:   {"op": "eq"|"neq"|"lt"|"lte"|"gt"|"gte", "l": <expr>, "r": <expr>}
                (returns bool)
  Logical:      {"op": "and"|"or", "l": <expr>, "r": <expr>}
                {"op": "not",      "v": <expr>}

## Statements (used inside body / then / else / loop body)
  Return:  {"op": "return", "val": <expr>}
  Let:     {"op": "let", "id": "<name>", "type": <type_object>, "val": <expr>}
           (immutable by default)
  Let mut: {"op": "let", "id": "<name>", "type": <type_object>, "val": <expr>, "mut": true}
  Assign:  {"op": "assign", "id": "<name>", "val": <expr>}
           (only valid for previously declared mutable variables)
  If:      {"op": "if", "cond": <bool_expr>,
            "then": [<statement>, ...],
            "else": [<statement>, ...]}
           (else branch is mandatory)
  Loop:    {"op": "loop", "bind": "<loop_var>",
            "from": <expr>, "to": <expr>, "step": <expr>,
            "body": [<statement>, ...]}
           (iterates bind = from, from+step, ..., to-1; must terminate)

## Rules
  - kind "fn" cannot call other functions (only modules can)
  - Recursion is forbidden
  - All "if" statements must have an "else" branch
  - "assign" only works on variables declared with "mut": true
  - Loop variable (bind) is read-only within the loop body

## Output requirements
  - Return ONLY a single valid JSON object
  - No markdown fences, no explanation, no comments
  - Keys must be sorted alphabetically (JCS canonical form)
"""


def _nail_prompt(problem: dict[str, Any]) -> str:
    return (
        "You are implementing a function in NAIL, a JSON-only language.\n"
        "Return ONLY one valid JSON object. No markdown, no explanation.\n\n"
        f"Task: {problem['spec']}\n\n"
        f"{NAIL_SCHEMA_REFERENCE}"
    )


def _python_prompt(problem: dict[str, Any]) -> str:
    name = problem["name"]
    spec = problem["spec"]
    return (
        "Implement exactly one Python function and return ONLY the code.\n"
        "No markdown fences, no explanation.\n\n"
        f"Specification: {spec}\n"
        f"Function name: {name}\n"
    )


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_response_text(stdout: str) -> str:
    """Extract model text from openclaw --json output, with plain-text fallback."""
    try:
        payload = json.loads(stdout)
        result = payload.get("result", {})
        payloads = result.get("payloads", [])
        if payloads and isinstance(payloads[0].get("text"), str):
            return payloads[0]["text"].strip()
        text = payload.get("response", payload.get("text", stdout))
        if isinstance(text, str):
            return text.strip()
        return json.dumps(text, ensure_ascii=False)
    except json.JSONDecodeError:
        return stdout.strip()


def _first_json_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escaped = False

        for idx in range(start, len(text)):
            ch = text[idx]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break

        start = text.find("{", start + 1)
    return None


def extract_json_object(text: str) -> str:
    fenced = re.findall(r"```(?:json)?\n(.*?)```", text, flags=re.S | re.I)
    for candidate in fenced + [text]:
        obj = _first_json_object(candidate)
        if obj is not None:
            return obj
    raise ValueError("No JSON object found in response")


def canonicalize_jcs(raw_json: str) -> str:
    parsed = json.loads(raw_json)
    return json.dumps(parsed, sort_keys=True, separators=(",", ":"))


def validate_nail(canonical_json: str) -> tuple[bool, str | None]:
    try:
        spec = json.loads(canonical_json)
        checker = Checker(spec, raw_text=canonical_json, strict=True)
        checker.check()
        return True, None
    except (CheckError, NailTypeError, NailEffectError, json.JSONDecodeError, ValueError) as exc:
        return False, str(exc)


def call_claude(prompt: str, session_id: str) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            [
                "openclaw",
                "agent",
                "--message",
                prompt,
                "--json",
                "--session-id",
                session_id,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "unknown error").strip()
            return "", f"openclaw exit code {result.returncode}: {err[:500]}"
        return _extract_response_text(result.stdout), None
    except subprocess.TimeoutExpired:
        return "", "timeout (120s)"
    except FileNotFoundError:
        return "", "openclaw command not found"
    except Exception as exc:
        return "", str(exc)


# ---------------------------------------------------------------------------
# Trial runners
# ---------------------------------------------------------------------------


def run_nail_trials_for_problem(problem: dict[str, Any]) -> list[dict[str, Any]]:
    name = problem["name"]
    prompt = _nail_prompt(problem)
    rows: list[dict[str, Any]] = []

    for i in range(RUNS_PER_PROBLEM):
        session_id = f"nail-repro-v2-{RUN_UUID}-{name}-{i}"
        raw, err = call_claude(prompt, session_id)
        row: dict[str, Any] = {
            "run_id": i,
            "problem": name,
            "lang": "nail",
            "raw": raw,
            "normalized": None,
            "sha256_hash": _sha256(raw),
            "valid": False,
        }

        if err is not None:
            row["error"] = err
        else:
            try:
                extracted = extract_json_object(raw)
                normalized = canonicalize_jcs(extracted)
                valid, validation_error = validate_nail(normalized)
                row["normalized"] = normalized
                row["valid"] = valid
                row["sha256_hash"] = _sha256(normalized)
                if validation_error:
                    row["error"] = validation_error
            except Exception as exc:
                row["error"] = str(exc)

        rows.append(row)
        print(
            f"  [{name}] NAIL run {i+1}/{RUNS_PER_PROBLEM} "
            f"valid={row.get('valid', False)} "
            f"hash={row['sha256_hash'][:12]}..."
        )

        if i != RUNS_PER_PROBLEM - 1:
            time.sleep(DELAY_SECONDS)

    return rows


def run_python_trials_for_problem(problem: dict[str, Any]) -> list[dict[str, Any]]:
    name = problem["name"]
    prompt = _python_prompt(problem)
    rows: list[dict[str, Any]] = []

    for i in range(RUNS_PER_PROBLEM):
        session_id = f"python-repro-v2-{RUN_UUID}-{name}-{i}"
        raw, err = call_claude(prompt, session_id)
        row: dict[str, Any] = {
            "run_id": i,
            "problem": name,
            "lang": "python",
            "raw": raw,
            "sha256_hash": _sha256(raw),
        }
        if err is not None:
            row["error"] = err

        rows.append(row)
        print(
            f"  [{name}] Python run {i+1}/{RUNS_PER_PROBLEM} "
            f"hash={row['sha256_hash'][:12]}..."
        )

        if i != RUNS_PER_PROBLEM - 1:
            time.sleep(DELAY_SECONDS)

    return rows


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------


def _match_rate(hashes: list[str]) -> str:
    if not hashes:
        return "0.0%"
    top_count = Counter(hashes).most_common(1)[0][1]
    return f"{(top_count / len(hashes)) * 100:.1f}%"


def summarize_by_problem(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_problem: dict[str, Any] = {}

    for problem in PROBLEMS:
        name = problem["name"]
        nail_rows = [r for r in all_rows if r.get("problem") == name and r.get("lang") == "nail"]
        py_rows = [r for r in all_rows if r.get("problem") == name and r.get("lang") == "python"]

        nail_hashes = [r["sha256_hash"] for r in nail_rows if r.get("sha256_hash")]
        py_hashes = [r["sha256_hash"] for r in py_rows if r.get("sha256_hash")]
        nail_valid = sum(1 for r in nail_rows if r.get("valid") is True)

        per_problem[name] = {
            "nail_runs": len(nail_rows),
            "nail_valid": nail_valid,
            "nail_unique_hashes": len(set(nail_hashes)),
            "nail_match_rate": _match_rate(nail_hashes),
            "python_runs": len(py_rows),
            "python_unique_hashes": len(set(py_hashes)),
            "python_match_rate": _match_rate(py_hashes),
        }

    # Overall totals
    nail_all = [r for r in all_rows if r.get("lang") == "nail"]
    py_all = [r for r in all_rows if r.get("lang") == "python"]
    nail_hashes_all = [r["sha256_hash"] for r in nail_all if r.get("sha256_hash")]
    py_hashes_all = [r["sha256_hash"] for r in py_all if r.get("sha256_hash")]

    return {
        "per_problem": per_problem,
        "overall": {
            "nail_total_runs": len(nail_all),
            "nail_total_valid": sum(1 for r in nail_all if r.get("valid") is True),
            "nail_total_unique_hashes": len(set(nail_hashes_all)),
            "python_total_runs": len(py_all),
            "python_total_unique_hashes": len(set(py_hashes_all)),
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(dry_run: bool = False) -> int:
    if dry_run:
        print("=== Dry run: validating imports and prompt construction ===")
        print()
        for problem in PROBLEMS:
            nail_p = _nail_prompt(problem)
            py_p = _python_prompt(problem)
            print(f"Problem: {problem['name']}")
            print(f"  NAIL prompt length: {len(nail_p)} chars")
            print(f"  Python prompt length: {len(py_p)} chars")
            # Verify no concrete answer is leaked in NAIL prompt
            # (schema description uses <expr> placeholders, not real function bodies)
            for param in ["val", "lo", "hi", "a", "b"]:
                assert f'"ref": "{param}"' not in nail_p, (
                    f"NAIL prompt must not contain concrete ref to param '{param}' "
                    "(would leak the answer)"
                )
        print()
        print("All imports OK. Prompts constructed. No body examples detected.")
        print("Run without --dry-run to execute experiments.")
        return 0

    all_rows: list[dict[str, Any]] = []

    for problem in PROBLEMS:
        print(f"\n--- Problem: {problem['name']} ---")
        print("Running NAIL trials...")
        nail_rows = run_nail_trials_for_problem(problem)
        all_rows.extend(nail_rows)

        print("Running Python trials...")
        py_rows = run_python_trials_for_problem(problem)
        all_rows.extend(py_rows)

    summary = summarize_by_problem(all_rows)

    results: dict[str, Any] = {
        "version": "v2",
        "runs_per_problem": RUNS_PER_PROBLEM,
        "problems": [p["name"] for p in PROBLEMS],
        "summary": summary,
        "runs": all_rows,
    }

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {RESULTS_PATH}")

    # Print quick summary
    print("\n=== Quick Summary ===")
    for name, stats in summary["per_problem"].items():
        print(
            f"{name:20s}  "
            f"NAIL unique={stats['nail_unique_hashes']}/{stats['nail_runs']} "
            f"(valid {stats['nail_valid']}, match {stats['nail_match_rate']})  "
            f"Python unique={stats['python_unique_hashes']}/{stats['python_runs']} "
            f"(match {stats['python_match_rate']})"
        )

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reproducibility experiment v2")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate imports and prompt construction without calling the LLM",
    )
    args = parser.parse_args()
    raise SystemExit(main(dry_run=args.dry_run))
