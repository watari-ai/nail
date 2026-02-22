#!/usr/bin/env python3
"""Phase 2 LLM experiment runner (subprocess-based).

Calls LLMs via CLI tools instead of direct API calls:
- Claude: openclaw agent --message "<prompt>" --json --session-id nail-experiment-claude
- GPT-4o: codex exec "<prompt>" --model gpt-4o

Prompts each LLM to implement 5 problems in both NAIL and Python.
Validates NAIL through the interpreter, tests Python functions.
Saves results to experiments/phase2/llm_results.json.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interpreter import Checker, Runtime  # noqa: E402

PROBLEMS_PATH = Path(__file__).with_name("PROBLEMS.md")
RESULTS_PATH = Path(__file__).with_name("llm_results.json")
SPEC_PATH = ROOT / "SPEC.md"
EXAMPLES_DIR = ROOT / "examples"

# ---------------------------------------------------------------------------
# Load NAIL spec and examples for rich prompts
# ---------------------------------------------------------------------------

def load_nail_spec() -> str:
    if SPEC_PATH.exists():
        return SPEC_PATH.read_text(encoding="utf-8")
    return "(NAIL spec not found)"


def load_nail_examples() -> str:
    parts: list[str] = []
    for p in sorted(EXAMPLES_DIR.glob("*.nail")):
        parts.append(f"--- {p.name} ---\n{p.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts) if parts else "(no examples found)"


NAIL_SPEC = load_nail_spec()
NAIL_EXAMPLES = load_nail_examples()

# ---------------------------------------------------------------------------
# Problem definitions and test cases
# ---------------------------------------------------------------------------

@dataclass
class Problem:
    name: str
    description: str


TEST_CASES: dict[str, list[tuple[dict[str, int], Any]]] = {
    "is_even": [
        ({"n": 4}, True),
        ({"n": 7}, False),
        ({"n": 0}, True),
        ({"n": -2}, True),
        ({"n": -3}, False),
    ],
    "abs_val": [
        ({"n": 5}, 5),
        ({"n": -5}, 5),
        ({"n": 0}, 0),
        ({"n": -100}, 100),
    ],
    "max_of_two": [
        ({"a": 3, "b": 7}, 7),
        ({"a": 7, "b": 3}, 7),
        ({"a": 5, "b": 5}, 5),
        ({"a": -1, "b": -5}, -1),
    ],
    "clamp": [
        ({"val": 5, "lo": 1, "hi": 10}, 5),
        ({"val": 0, "lo": 1, "hi": 10}, 1),
        ({"val": 15, "lo": 1, "hi": 10}, 10),
        ({"val": 1, "lo": 1, "hi": 1}, 1),
    ],
    "factorial": [
        ({"n": 0}, 1),
        ({"n": 1}, 1),
        ({"n": 5}, 120),
        ({"n": 10}, 3628800),
    ],
}


def load_problems() -> list[Problem]:
    if not PROBLEMS_PATH.exists():
        return default_problems()
    body = PROBLEMS_PATH.read_text(encoding="utf-8")
    chunks = re.findall(
        r"^###\s+P\d+:\s+([a-z_]+)\n(.*?)(?=\n###\s+P\d+:|\Z)",
        body, flags=re.M | re.S,
    )
    if not chunks:
        return default_problems()
    return [Problem(name=n.strip(), description=c.strip()) for n, c in chunks]


def default_problems() -> list[Problem]:
    return [
        Problem("is_even", "Input n:int64, return bool: true when n is even."),
        Problem("abs_val", "Input n:int64, return |n| as int64."),
        Problem("max_of_two", "Inputs a,b int64, return the larger value."),
        Problem("clamp", "Inputs val,lo,hi int64, assume lo<=hi, clamp val into [lo,hi]."),
        Problem("factorial", "Input n:int64 with 0<=n<=20, return n! using a loop."),
    ]


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def nail_prompt(problem: Problem) -> str:
    return textwrap.dedent(f"""\
You are implementing a function in NAIL, a JSON-based programming language for AI.
Return ONLY a single valid JSON object — no markdown fences, no explanation.

## NAIL Language Specification
{NAIL_SPEC}

## Example NAIL programs
{NAIL_EXAMPLES}

## Your task
Implement the function `{problem.name}` in NAIL JSON.

Problem spec:
{problem.description}

Constraints:
- Pure function (effects: [])
- Output must be a single JSON object with keys: nail, kind, id, effects, params, returns, body
- Must type-check against NAIL v0.1 spec
- Return ONLY the JSON object, nothing else
""")


def python_prompt(problem: Problem) -> str:
    return textwrap.dedent(f"""\
Implement exactly one Python function for this problem.
Return ONLY Python code — no markdown fences, no explanation.

Function name: {problem.name}
Spec:
{problem.description}

Constraints:
- No prints, no I/O, no extra text.
- Deterministic pure function.
- Include type hints.
""")


# ---------------------------------------------------------------------------
# LLM callers (subprocess-based)
# ---------------------------------------------------------------------------

def call_claude(prompt: str) -> tuple[str, str | None]:
    """Call Claude via openclaw agent CLI."""
    try:
        result = subprocess.run(
            [
                "openclaw", "agent",
                "--message", prompt,
                "--json",
                "--session-id", "nail-experiment-claude",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return "", f"openclaw exit code {result.returncode}: {result.stderr[:500]}"

        # --json outputs JSON; extract the response text
        try:
            data = json.loads(result.stdout)
            text = data.get("response", data.get("text", result.stdout))
            if isinstance(text, str):
                return text.strip(), None
            return json.dumps(text), None
        except json.JSONDecodeError:
            # Plain text output
            return result.stdout.strip(), None

    except subprocess.TimeoutExpired:
        return "", "timeout (120s)"
    except FileNotFoundError:
        return "", "openclaw command not found"
    except Exception as exc:
        return "", str(exc)


def call_gpt4o(prompt: str) -> tuple[str, str | None]:
    """Call GPT-4o via codex exec CLI."""
    try:
        result = subprocess.run(
            [
                "codex", "exec",
                prompt,
                "--model", "gpt-4o",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return "", f"codex exit code {result.returncode}: {result.stderr[:500]}"
        return result.stdout.strip(), None

    except subprocess.TimeoutExpired:
        return "", "timeout (120s)"
    except FileNotFoundError:
        return "", "codex command not found"
    except Exception as exc:
        return "", str(exc)


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------

def extract_python_code(text: str) -> str:
    fenced = re.findall(r"```(?:python)?\n(.*?)```", text, flags=re.S | re.I)
    if fenced:
        return fenced[0].strip()
    return text.strip()


def extract_json_object(text: str) -> str:
    # Try fenced blocks first
    fenced = re.findall(r"```(?:json)?\n(.*?)```", text, flags=re.S | re.I)
    candidates = fenced + [text]
    for candidate in candidates:
        obj = _first_json_object(candidate)
        if obj is not None:
            return obj
    raise ValueError("No JSON object found in model response")


def _first_json_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i, ch in enumerate(text[start:], start=start):
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
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
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def approx_tokens(text: str) -> int:
    return len(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S", text))


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_nail(raw_text: str, problem_name: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "check_pass": False,
        "test_pass": 0,
        "test_total": len(TEST_CASES[problem_name]),
        "errors": [],
        "code_tokens": 0,
    }
    try:
        json_text = extract_json_object(raw_text)
        out["code_tokens"] = approx_tokens(json_text)
        spec = json.loads(json_text)
    except Exception as exc:
        out["errors"].append(f"parse_error: {exc}")
        return out

    try:
        checker = Checker(spec)
        checker.check()
        out["check_pass"] = True
    except Exception as exc:
        out["errors"].append(f"check_error: {exc}")
        return out

    runtime = Runtime(spec)
    for args, expected in TEST_CASES[problem_name]:
        try:
            got = runtime.run(args)
            if got == expected:
                out["test_pass"] += 1
            else:
                out["errors"].append(f"test_failed args={args} expected={expected} got={got}")
        except Exception as exc:
            out["errors"].append(f"runtime_error args={args}: {exc}")
    return out


def evaluate_python(raw_text: str, problem_name: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "check_pass": False,
        "test_pass": 0,
        "test_total": len(TEST_CASES[problem_name]),
        "errors": [],
        "code_tokens": 0,
    }
    code = extract_python_code(raw_text)
    out["code_tokens"] = approx_tokens(code)

    try:
        ns: dict[str, Any] = {}
        exec(code, ns, ns)
    except Exception as exc:
        out["errors"].append(f"syntax_or_exec_error: {exc}")
        return out

    fn = ns.get(problem_name)
    if not callable(fn):
        out["errors"].append(f"missing_function: {problem_name}")
        return out

    out["check_pass"] = True
    for args, expected in TEST_CASES[problem_name]:
        try:
            got = fn(**args)
            if got == expected:
                out["test_pass"] += 1
            else:
                out["errors"].append(f"test_failed args={args} expected={expected} got={got}")
        except Exception as exc:
            out["errors"].append(f"runtime_error args={args}: {exc}")
    return out


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def format_rate(n: int, total: int) -> str:
    return f"{n}/{total}"


def print_table(rows: list[dict[str, Any]]) -> None:
    headers = ["problem", "run", "check", "tests", "code_tok"]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row.get(h, ""))))

    def line(cells: dict[str, Any]) -> str:
        return " | ".join(str(cells.get(h, "")).ljust(widths[h]) for h in headers)

    print(line({h: h for h in headers}))
    print("-+-".join("-" * widths[h] for h in headers))
    for row in rows:
        print(line(row))


def main() -> None:
    problems = [p for p in load_problems() if p.name in TEST_CASES]
    if not problems:
        raise RuntimeError("No valid problems found")

    runs = [
        ("claude", "nail"),
        ("claude", "python"),
        ("gpt4o", "nail"),
        ("gpt4o", "python"),
    ]

    callers = {
        "claude": call_claude,
        "gpt4o": call_gpt4o,
    }

    all_results: dict[str, Any] = {
        "meta": {
            "script": Path(__file__).name,
            "method": "subprocess (openclaw agent / codex exec)",
            "models": {
                "claude": "claude (via openclaw agent)",
                "gpt4o": "gpt-4o (via codex exec)",
            },
            "problems": [p.name for p in problems],
        },
        "results": [],
    }

    table_rows: list[dict[str, Any]] = []

    for problem in problems:
        print(f"\n=== {problem.name} ===")
        for model_name, language in runs:
            prompt = nail_prompt(problem) if language == "nail" else python_prompt(problem)
            caller = callers[model_name]

            print(f"  {model_name}->{language} ... ", end="", flush=True)
            response_text, err = caller(prompt)

            record: dict[str, Any] = {
                "problem": problem.name,
                "model": model_name,
                "language": language,
                "prompt_length": len(prompt),
                "response": response_text[:2000] if response_text else "",
                "request_error": err,
            }

            if err:
                eval_result = {
                    "check_pass": False,
                    "test_pass": 0,
                    "test_total": len(TEST_CASES[problem.name]),
                    "errors": [f"request_error: {err}"],
                    "code_tokens": 0,
                }
            elif language == "nail":
                eval_result = evaluate_nail(response_text, problem.name)
            else:
                eval_result = evaluate_python(response_text, problem.name)

            record["evaluation"] = eval_result
            all_results["results"].append(record)

            status = "PASS" if eval_result["check_pass"] else "FAIL"
            tests = format_rate(eval_result["test_pass"], eval_result["test_total"])
            print(f"check={status} tests={tests}")

            table_rows.append({
                "problem": problem.name,
                "run": f"{model_name}->{language}",
                "check": status,
                "tests": tests,
                "code_tok": eval_result.get("code_tokens", 0),
            })

    RESULTS_PATH.write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved: {RESULTS_PATH}")
    print("\n--- Comparison Table ---")
    print_table(table_rows)


if __name__ == "__main__":
    main()
