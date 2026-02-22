#!/usr/bin/env python3
"""Phase 2 LLM experiment runner.

Generates solutions for 5 problems with two models and two target languages:
- Claude (claude-3-5-sonnet-20241022) -> NAIL and Python
- GPT-4o -> Python and NAIL

Then validates and tests outputs, records token usage and errors, and writes:
- experiments/phase2/llm_results.json
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# Local interpreter imports
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interpreter import Checker, Runtime  # noqa: E402

PROBLEMS_PATH = Path(__file__).with_name("PROBLEMS.md")
RESULTS_PATH = Path(__file__).with_name("llm_results.json")


@dataclass
class Problem:
    name: str
    description: str


# Canonical test cases used for execution checks.
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


def approx_tokens(text: str) -> int:
    return len(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S", text))


def load_problems() -> list[Problem]:
    if not PROBLEMS_PATH.exists():
        return default_problems()

    body = PROBLEMS_PATH.read_text(encoding="utf-8")
    chunks = re.findall(r"^###\s+P\d+:\s+([a-z_]+)\n(.*?)(?=\n###\s+P\d+:|\Z)", body, flags=re.M | re.S)
    if not chunks:
        return default_problems()

    problems: list[Problem] = []
    for name, chunk in chunks:
        problems.append(Problem(name=name.strip(), description=chunk.strip()))
    return problems


def default_problems() -> list[Problem]:
    return [
        Problem("is_even", "Input n:int64, return bool: true when n is even."),
        Problem("abs_val", "Input n:int64, return |n| as int64."),
        Problem("max_of_two", "Inputs a,b int64, return the larger value."),
        Problem("clamp", "Inputs val,lo,hi int64, assume lo<=hi, clamp val into [lo,hi]."),
        Problem("factorial", "Input n:int64 with 0<=n<=20, return n! using a loop."),
    ]


def nail_prompt(problem: Problem) -> str:
    return textwrap.dedent(
        f"""
        Implement this function in NAIL JSON only. Return only one JSON object.

        Problem: {problem.name}
        Spec:
        {problem.description}

        Required NAIL format:
        - Top-level keys: nail, kind, id, effects, params, returns, body
        - Use: {{"nail":"0.1.0","kind":"fn","id":"...","effects":[],"params":[...],"returns":{{...}},"body":[...]}}
        - Type objects must use NAIL v0.1 shape like: {{"type":"int","bits":64,"overflow":"panic"}}, {{"type":"bool"}}
        - Params are: {{"id":"name","type":<type_obj>}}
        - Body statements: let, return, if, loop, assign
        - Loop statement shape: {{"op":"loop","bind":"i","from":<expr>,"to":<expr>,"step":<expr>,"body":[...]}}
        - Expression ops use symbols/keywords as supported by NAIL checker:
          +, -, *, /, %, eq, neq, lt, lte, gt, gte, and, or, not
        - Variable reference: {{"ref":"name"}}
        - Literal: {{"lit": 123}}

        Constraints:
        - No side effects (effects must be [])
        - Output must be valid JSON and must type-check in NAIL checker.
        """
    ).strip()


def python_prompt(problem: Problem) -> str:
    return textwrap.dedent(
        f"""
        Implement exactly one Python function for this problem.
        Return only Python code.

        Function name: {problem.name}
        Spec:
        {problem.description}

        Constraints:
        - No prints, no I/O, no extra text.
        - Deterministic pure function.
        """
    ).strip()


def call_claude(prompt: str) -> tuple[str, dict[str, int]]:
    try:
        import anthropic
    except Exception as exc:  # pragma: no cover - env dependent
        raise RuntimeError("anthropic package is not installed") from exc

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1200,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    text_parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", "") == "text":
            text_parts.append(block.text)

    usage = {
        "input_tokens": int(getattr(resp.usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(resp.usage, "output_tokens", 0) or 0),
    }
    return "\n".join(text_parts).strip(), usage


def call_gpt(prompt: str) -> tuple[str, dict[str, int]]:
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - env dependent
        raise RuntimeError("openai package is not installed") from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    content = resp.choices[0].message.content or ""
    usage = {
        "input_tokens": int(getattr(resp.usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(resp.usage, "completion_tokens", 0) or 0),
    }
    return content.strip(), usage


def extract_python_code(text: str) -> str:
    fenced = re.findall(r"```(?:python)?\n(.*?)```", text, flags=re.S | re.I)
    if fenced:
        return fenced[0].strip()
    return text.strip()


def extract_json_object(text: str) -> str:
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


def run_generation(model_name: str, language: str, prompt: str) -> tuple[str, dict[str, int], str | None]:
    try:
        if model_name == "claude":
            text, usage = call_claude(prompt)
        elif model_name == "gpt4o":
            text, usage = call_gpt(prompt)
        else:
            raise ValueError(f"Unknown model: {model_name}")
        return text, usage, None
    except Exception as exc:  # pragma: no cover - env/network dependent
        return "", {"input_tokens": 0, "output_tokens": 0}, str(exc)


def format_rate(pass_n: int, total: int) -> str:
    if total == 0:
        return "0/0"
    return f"{pass_n}/{total}"


def print_table(rows: list[dict[str, Any]]) -> None:
    headers = [
        "problem",
        "run",
        "check",
        "tests",
        "prompt_tok",
        "completion_tok",
        "code_tok",
    ]
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
        ("gpt4o", "python"),
        ("claude", "python"),
        ("gpt4o", "nail"),
    ]

    all_results: dict[str, Any] = {
        "meta": {
            "script": str(Path(__file__).name),
            "models": {
                "claude": "claude-3-5-sonnet-20241022",
                "gpt4o": "gpt-4o",
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
            response_text, usage, err = run_generation(model_name, language, prompt)

            record: dict[str, Any] = {
                "problem": problem.name,
                "model": model_name,
                "language": language,
                "prompt": prompt,
                "response": response_text,
                "usage": usage,
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
            else:
                if language == "nail":
                    eval_result = evaluate_nail(response_text, problem.name)
                else:
                    eval_result = evaluate_python(response_text, problem.name)

            record["evaluation"] = eval_result
            all_results["results"].append(record)

            table_rows.append(
                {
                    "problem": problem.name,
                    "run": f"{model_name}->{language}",
                    "check": "PASS" if eval_result["check_pass"] else "FAIL",
                    "tests": format_rate(eval_result["test_pass"], eval_result["test_total"]),
                    "prompt_tok": usage.get("input_tokens", 0),
                    "completion_tok": usage.get("output_tokens", 0),
                    "code_tok": eval_result.get("code_tokens", 0),
                }
            )

            print(
                f"{model_name}->{language}: "
                f"check={'PASS' if eval_result['check_pass'] else 'FAIL'} "
                f"tests={eval_result['test_pass']}/{eval_result['test_total']}"
            )

    RESULTS_PATH.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSaved:", RESULTS_PATH)
    print("\nComparison Table")
    print_table(table_rows)


if __name__ == "__main__":
    main()
