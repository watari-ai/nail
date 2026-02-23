#!/usr/bin/env python3
"""Reproducibility demo runner.

Runs Claude repeatedly on the same task in two modes:
- NAIL JSON output (normalized via JCS-style canonical JSON)
- Python function output (raw text)

The script stores per-run outputs and a reproducibility summary to results.json.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interpreter import CheckError, Checker, NailEffectError, NailTypeError  # noqa: E402

RUNS_PER_LANG = 10
DELAY_SECONDS = 2
RESULTS_PATH = Path(__file__).with_name("results.json")

PROBLEM_SPEC = """Function `add`:
- Inputs: a:int64, b:int64
- Output: int64
- Effects: [] (pure)
- Behavior: return a + b
"""

NAIL_PROMPT = (
    "You are implementing a function in NAIL, a JSON-only language.\n"
    "Return ONLY one valid JSON object. No markdown, no explanation.\n\n"
    "Task:\n"
    f"{PROBLEM_SPEC}\n"
    "NAIL v0.2 schema reference:\n"
    "- Top-level fields: nail, kind, id, effects, params, returns, body\n"
    "- nail: must be the string \"0.2\"\n"
    "- kind: must be \"fn\"\n"
    "- id: must be \"add\"\n"
    "- effects: must be []\n"
    "- params: list of {\"id\": <name>, \"type\": {\"type\": \"int\", \"bits\": 64, \"overflow\": \"panic\"}}\n"
    "  - Use \"id\" not \"name\" for parameter identifiers\n"
    "- returns: {\"type\": \"int\", \"bits\": 64, \"overflow\": \"panic\"}\n"
    "- body: list of statements\n"
    "  - to return a+b: [{\"op\": \"return\", \"val\": {\"op\": \"+\", \"l\": {\"ref\": \"a\"}, \"r\": {\"ref\": \"b\"}}}]\n"
    "Return ONLY a valid JSON object. The JSON must match the schema exactly.\n"
)

PYTHON_PROMPT = (
    "Implement exactly one Python function and return ONLY code.\n"
    "No markdown fences, no explanation.\n\n"
    "Function signature: def add(a: int, b: int) -> int\n"
    "Behavior: return a + b\n"
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_response_text(stdout: str) -> str:
    """Extract model text from openclaw --json output, with plain-text fallback.

    OpenClaw agent --json response format:
      {"runId": ..., "status": "ok", "result": {"payloads": [{"text": "...", ...}]}}
    """
    try:
        payload = json.loads(stdout)
        # OpenClaw agent format: result.payloads[0].text
        result = payload.get("result", {})
        payloads = result.get("payloads", [])
        if payloads and isinstance(payloads[0].get("text"), str):
            return payloads[0]["text"].strip()
        # Legacy / fallback
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
    fenced = re.findall(r"```(?:json)?\\n(.*?)```", text, flags=re.S | re.I)
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


def call_claude(prompt: str, run_id: int) -> tuple[str, str | None]:
    try:
        result = subprocess.run(
            [
                "openclaw",
                "agent",
                "--message",
                prompt,
                "--json",
                "--session-id",
                f"nail-repro-{run_id}",
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
    except Exception as exc:  # pragma: no cover - defensive guard
        return "", str(exc)


def run_nail_trials() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(RUNS_PER_LANG):
        raw, err = call_claude(NAIL_PROMPT, i)
        row: dict[str, Any] = {
            "run_id": i,
            "lang": "nail",
            "raw": raw,
            "normalized": None,
            "sha256_hash": _sha256(raw),
            "valid": False,
        }

        if err is not None:
            row["error"] = err
            rows.append(row)
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

        if i != RUNS_PER_LANG - 1:
            time.sleep(DELAY_SECONDS)

    return rows


def run_python_trials() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(RUNS_PER_LANG):
        raw, err = call_claude(PYTHON_PROMPT, i)
        row: dict[str, Any] = {
            "run_id": i,
            "lang": "python",
            "raw": raw,
            "sha256_hash": _sha256(raw),
        }
        if err is not None:
            row["error"] = err
        rows.append(row)

        if i != RUNS_PER_LANG - 1:
            time.sleep(DELAY_SECONDS)

    return rows


def _match_rate(hashes: list[str], total_runs: int) -> str:
    if total_runs == 0 or not hashes:
        return "0.0%"
    top_count = Counter(hashes).most_common(1)[0][1]
    return f"{(top_count / total_runs) * 100:.1f}%"


def summarize(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    nail_rows = [r for r in all_rows if r.get("lang") == "nail"]
    python_rows = [r for r in all_rows if r.get("lang") == "python"]

    nail_hashes = [r["sha256_hash"] for r in nail_rows if r.get("sha256_hash")]
    python_hashes = [r["sha256_hash"] for r in python_rows if r.get("sha256_hash")]

    return {
        "nail_unique_hashes": len(set(nail_hashes)),
        "python_unique_hashes": len(set(python_hashes)),
        "nail_match_rate": _match_rate(nail_hashes, RUNS_PER_LANG),
        "python_match_rate": _match_rate(python_hashes, RUNS_PER_LANG),
    }


def main() -> int:
    results: dict[str, Any] = {"runs": [], "summary": {}}

    nail_rows = run_nail_trials()
    python_rows = run_python_trials()
    results["runs"] = nail_rows + python_rows
    results["summary"] = summarize(results["runs"])

    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
