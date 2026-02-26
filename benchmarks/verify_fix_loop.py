#!/usr/bin/env python3
"""
NAIL Multi-LLM Verify-Fix Loop Benchmark
Issue #103: Benchmark Demo

For each LLM × task combination:
  1. Ask the LLM to generate a NAIL spec (JSON)
  2. Validate with NAIL Checker
  3. On failure → feed error back, retry (max 3 attempts)
  4. Record: model / task / attempts / final_pass / error_codes

Real API mode: set NAIL_REAL_API=1 and ensure anthropic/openai/google-generativeai
               packages are installed with valid keys in env.
Mock mode (default): runs offline with pre-defined valid/invalid spec sequences.

Usage:
    python benchmarks/verify_fix_loop.py              # mock mode
    NAIL_REAL_API=1 python benchmarks/verify_fix_loop.py  # real API
    python benchmarks/verify_fix_loop.py --save       # save CSV to benchmarks/results/
    python benchmarks/verify_fix_loop.py --output json
"""

from __future__ import annotations

import csv
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

# ── project root on path ────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from interpreter.checker import Checker, CheckError
from interpreter.types import NailEffectError, NailTypeError

# ── Constants ────────────────────────────────────────────────────────────────
MAX_RETRIES = 3
TASKS_DIR = Path(__file__).parent / "tasks"
RESULTS_DIR = Path(__file__).parent / "results"

# ── Task definitions ─────────────────────────────────────────────────────────

TASK_PROMPTS: dict[str, str] = {
    "simple_calculator": (
        "Generate a NAIL spec in JSON format for a module called 'simple_calculator' "
        "with three pure functions: add(a: int64, b: int64) -> int64, "
        "sub(a: int64, b: int64) -> int64, mul(a: int64, b: int64) -> int64. "
        "Effects must be empty []. Include 'nail': '0.1.0', 'kind': 'module', "
        "'exports': ['add', 'sub', 'mul'], and 'defs' list. "
        "Each function body must contain exactly one return statement."
    ),
    "user_auth": (
        "Generate a NAIL spec in JSON format for a module called 'user_auth' with three functions: "
        "login(username: string, password: string) -> result<string, string> with effects ['NET', 'IO'], "
        "logout(session_token: string) -> unit with effects ['NET', 'IO'], "
        "check_session(session_token: string) -> bool with effects ['NET']. "
        "Use 'nail': '0.1.0', 'kind': 'module', 'exports': ['login', 'logout', 'check_session']. "
        "Return values must match declared return types."
    ),
    "data_pipeline": (
        "Generate a NAIL spec in JSON format for a module called 'data_pipeline' with three functions: "
        "fetch(url: string) -> string with effects ['NET'], "
        "transform(count: int64) -> int64 with no effects, containing a loop from 0 to count step 1, "
        "save(path: string, data: string) -> unit with effects ['FS']. "
        "Use 'nail': '0.1.0', 'kind': 'module'. "
        "The loop body may be empty. All functions must have valid body with a return op."
    ),
}

# Checker level per task
TASK_LEVELS: dict[str, int] = {
    "simple_calculator": 2,
    "user_auth": 2,
    "data_pipeline": 3,
}

# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class BenchResult:
    model: str
    task: str
    attempts: int          # total attempts made (1 = passed on first try)
    final_pass: bool
    error_codes: list[str] = field(default_factory=list)   # errors from each failed attempt
    latency_ms: float = 0.0

    def to_csv_row(self) -> dict:
        return {
            "model": self.model,
            "task": self.task,
            "attempts": self.attempts,
            "final_pass": int(self.final_pass),
            "error_codes": "|".join(self.error_codes),
            "latency_ms": f"{self.latency_ms:.1f}",
        }


# ── NAIL checker wrapper ──────────────────────────────────────────────────────

def check_spec(spec: dict, level: int = 2) -> tuple[bool, str]:
    """
    Check a NAIL spec.
    Returns (passed: bool, error_message: str).
    """
    try:
        Checker(spec, level=level).check()
        return True, ""
    except CheckError as e:
        return False, f"[{e.code}] {e.message}"
    except NailEffectError as e:
        return False, f"[EFFECT_ERROR] {e}"
    except NailTypeError as e:
        return False, f"[TYPE_ERROR] {e}"
    except Exception as e:
        return False, f"[UNKNOWN_ERROR] {e}"


# ── LLM interface ─────────────────────────────────────────────────────────────

class LLMClient:
    """Base class for LLM clients (real or mock)."""

    name: str = "base"
    is_mock: bool = True

    def generate(self, prompt: str, error_feedback: str | None = None) -> str:
        """Return a JSON string (the NAIL spec)."""
        raise NotImplementedError


# ── Mock LLM implementations ──────────────────────────────────────────────────

def _load_template(task: str) -> dict:
    """Load a reference template spec for a task."""
    tpl_path = TASKS_DIR / f"{task}.json.template"
    if tpl_path.exists():
        with open(tpl_path) as f:
            return json.load(f)
    return {}


def _corrupt_spec(spec: dict) -> dict:
    """Return a broken copy of a spec (for mock bad responses)."""
    import copy
    bad = copy.deepcopy(spec)
    # Remove required field to trigger CHECK_ERROR
    if bad.get("kind") == "module" and "defs" in bad:
        # Break a function by removing its 'body'
        if bad["defs"]:
            bad["defs"][0].pop("body", None)
    elif "body" in bad:
        bad.pop("body", None)
    else:
        bad["nail"] = "INVALID"
    return bad


class MockLLM(LLMClient):
    """
    Mock LLM that returns a sequence of responses (valid or invalid)
    based on a pre-configured pattern.

    pass_on_attempt: which attempt number (1-indexed) returns a valid spec.
                     0 = never passes.
    """

    is_mock = True

    def __init__(self, name: str, pass_on_attempt: int = 1, seed: int | None = None):
        self.name = name
        self.pass_on_attempt = pass_on_attempt
        self._attempt = 0
        self._rng = random.Random(seed)
        self._task: str = ""

    def set_task(self, task: str) -> None:
        self._attempt = 0
        self._task = task

    def generate(self, prompt: str, error_feedback: str | None = None) -> str:
        self._attempt += 1
        template = _load_template(self._task)
        if not template:
            return json.dumps({"nail": "0.1.0", "kind": "fn", "id": "stub",
                               "effects": [], "params": [], "returns": {"type": "unit"},
                               "body": [{"op": "return", "val": {"lit": None, "type": {"type": "unit"}}}]})

        if self.pass_on_attempt == 0:
            # Never passes
            return json.dumps(_corrupt_spec(template))
        elif self._attempt >= self.pass_on_attempt:
            # This attempt should pass
            return json.dumps(template)
        else:
            # Return a broken spec
            return json.dumps(_corrupt_spec(template))


# ── Real API clients (optional) ───────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are an expert in NAIL (No Ambiguity, Inference-Locked), a JSON-based AI programming language. "
    "When asked to generate a NAIL spec, output ONLY valid JSON — no prose, no code fences. "
    "The JSON must be a valid NAIL module or function spec."
)


class AnthropicLLM(LLMClient):
    """Real Anthropic Claude client."""

    is_mock = False

    def __init__(self, model: str = "claude-3-haiku-20240307"):
        self.name = f"anthropic/{model}"
        self._model = model
        try:
            import anthropic  # type: ignore
            self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    def generate(self, prompt: str, error_feedback: str | None = None) -> str:
        import anthropic  # type: ignore
        messages = [{"role": "user", "content": prompt}]
        if error_feedback:
            messages.append({"role": "assistant", "content": "[previous attempt failed]"})
            messages.append({"role": "user", "content": f"Fix this error and try again:\n{error_feedback}"})
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        return resp.content[0].text


class OpenAILLM(LLMClient):
    """Real OpenAI client."""

    is_mock = False

    def __init__(self, model: str = "gpt-4o-mini"):
        self.name = f"openai/{model}"
        self._model = model
        try:
            from openai import OpenAI  # type: ignore
            self._client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

    def generate(self, prompt: str, error_feedback: str | None = None) -> str:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        if error_feedback:
            messages.append({"role": "assistant", "content": "[previous attempt failed]"})
            messages.append({"role": "user", "content": f"Fix this error and try again:\n{error_feedback}"})
        resp = self._client.chat.completions.create(model=self._model, messages=messages, max_tokens=2048)
        return resp.choices[0].message.content or ""


class GeminiLLM(LLMClient):
    """Real Google Gemini client."""

    is_mock = False

    def __init__(self, model: str = "gemini-1.5-flash"):
        self.name = f"gemini/{model}"
        self._model = model
        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", "")))
            self._genai_model = genai.GenerativeModel(model)
        except ImportError:
            raise RuntimeError("google-generativeai package not installed. Run: pip install google-generativeai")

    def generate(self, prompt: str, error_feedback: str | None = None) -> str:
        full_prompt = SYSTEM_PROMPT + "\n\n" + prompt
        if error_feedback:
            full_prompt += f"\n\nPrevious attempt failed with:\n{error_feedback}\nPlease fix and try again."
        resp = self._genai_model.generate_content(full_prompt)
        return resp.text


# ── Verify-Fix Loop ────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response (handles code fences, prose)."""
    text = text.strip()
    # Strip markdown code fences
    if "```" in text:
        lines = text.split("\n")
        inside = False
        json_lines = []
        for line in lines:
            if line.strip().startswith("```"):
                inside = not inside
                continue
            if inside:
                json_lines.append(line)
        text = "\n".join(json_lines).strip()
    # Find first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def verify_fix_loop(
    client: LLMClient,
    task: str,
    prompt: str,
    level: int = 2,
    max_retries: int = MAX_RETRIES,
    verbose: bool = False,
) -> BenchResult:
    """
    Run the verify-fix loop for one (model, task) pair.
    Returns a BenchResult.
    """
    if isinstance(client, MockLLM):
        client.set_task(task)

    error_codes: list[str] = []
    last_error: str | None = None
    passed = False
    attempt = 0

    t0 = time.perf_counter()

    for attempt in range(1, max_retries + 1):
        raw = client.generate(prompt, error_feedback=last_error)

        try:
            spec = _extract_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = f"[JSON_PARSE_ERROR] Could not parse JSON: {e}"
            error_codes.append("JSON_PARSE_ERROR")
            if verbose:
                print(f"  attempt {attempt}: JSON parse error")
            continue

        passed, last_error = check_spec(spec, level=level)

        if passed:
            if verbose:
                print(f"  attempt {attempt}: PASS")
            break
        else:
            # Extract error code from message like "[CODE] message"
            code = "CHECK_ERROR"
            if last_error and last_error.startswith("["):
                code = last_error[1 : last_error.index("]")]
            error_codes.append(code)
            if verbose:
                print(f"  attempt {attempt}: FAIL ({code})")

    latency_ms = (time.perf_counter() - t0) * 1000

    return BenchResult(
        model=client.name,
        task=task,
        attempts=attempt,
        final_pass=passed,
        error_codes=error_codes,
        latency_ms=latency_ms,
    )


# ── Build client list ─────────────────────────────────────────────────────────

def build_clients(real_api: bool = False) -> list[LLMClient]:
    """
    Return list of LLM clients.
    In real API mode, attempt to build live clients; fall back to mock on error.
    In mock mode, return a diverse set of mock models.
    """
    if real_api:
        clients: list[LLMClient] = []
        for cls, model, env_key in [
            (AnthropicLLM, "claude-3-haiku-20240307", "ANTHROPIC_API_KEY"),
            (OpenAILLM, "gpt-4o-mini", "OPENAI_API_KEY"),
            (GeminiLLM, "gemini-1.5-flash", "GEMINI_API_KEY"),
        ]:
            if os.environ.get(env_key):
                try:
                    clients.append(cls(model))
                    print(f"[real] {cls.__name__} loaded")
                except Exception as e:
                    print(f"[warn] {cls.__name__} failed ({e}), using mock")
                    clients.append(MockLLM(f"mock/{model}", pass_on_attempt=2, seed=42))
            else:
                print(f"[mock] {env_key} not set → using mock for {model}")
                clients.append(MockLLM(f"mock/{model}", pass_on_attempt=2, seed=42))
        return clients
    else:
        # Four mock models with different success patterns
        return [
            MockLLM("mock/perfect-llm",    pass_on_attempt=1, seed=1),   # always passes 1st try
            MockLLM("mock/slow-llm",       pass_on_attempt=2, seed=2),   # passes on 2nd try
            MockLLM("mock/stubborn-llm",   pass_on_attempt=3, seed=3),   # passes on 3rd try
            MockLLM("mock/failing-llm",    pass_on_attempt=0, seed=4),   # never passes
        ]


# ── Main runner ───────────────────────────────────────────────────────────────

def run_benchmark(
    clients: list[LLMClient] | None = None,
    verbose: bool = True,
    save: bool = False,
    output_format: str = "table",
) -> list[BenchResult]:
    """
    Run the full benchmark: all clients × all tasks.
    Returns list of BenchResult.
    """
    if clients is None:
        clients = build_clients(real_api=os.environ.get("NAIL_REAL_API", "") == "1")

    results: list[BenchResult] = []

    for client in clients:
        for task, prompt in TASK_PROMPTS.items():
            level = TASK_LEVELS[task]
            if verbose:
                print(f"\n[{client.name}] task={task} (L{level})")
            result = verify_fix_loop(
                client=client,
                task=task,
                prompt=prompt,
                level=level,
                verbose=verbose,
            )
            results.append(result)
            if verbose:
                status = "✓ PASS" if result.final_pass else "✗ FAIL"
                print(f"  → {status} | attempts={result.attempts} | {result.latency_ms:.0f}ms")

    if verbose:
        _print_summary(results)

    if save:
        _save_results(results)

    if output_format == "json":
        print(json.dumps([asdict(r) for r in results], indent=2))

    return results


def _print_summary(results: list[BenchResult]) -> None:
    """Print a quick summary table to stdout."""
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    models = sorted({r.model for r in results})
    tasks = sorted({r.task for r in results})
    # Header
    header = f"{'Model':<30} {'Task':<22} {'Pass':<6} {'Tries':<6}"
    print(header)
    print("-" * 60)
    for m in models:
        for t in tasks:
            row = next((r for r in results if r.model == m and r.task == t), None)
            if row:
                status = "YES" if row.final_pass else "NO"
                print(f"{m:<30} {t:<22} {status:<6} {row.attempts:<6}")
    print("=" * 60)


def _save_results(results: list[BenchResult]) -> None:
    """Save results to benchmarks/results/verify_fix_loop_<timestamp>.csv"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    csv_path = RESULTS_DIR / f"verify_fix_loop_{ts}.csv"
    fieldnames = ["model", "task", "attempts", "final_pass", "error_codes", "latency_ms"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_csv_row())
    print(f"\n[saved] {csv_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="NAIL Multi-LLM Verify-Fix Loop Benchmark (#103)"
    )
    parser.add_argument("--save", action="store_true", help="Save CSV to benchmarks/results/")
    parser.add_argument("--output", choices=["table", "json"], default="table")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-attempt output")
    parser.add_argument("--real-api", action="store_true",
                        help="Use real API (requires ANTHROPIC/OPENAI/GEMINI keys)")
    args = parser.parse_args()

    if args.real_api:
        os.environ["NAIL_REAL_API"] = "1"

    run_benchmark(
        verbose=not args.quiet,
        save=args.save,
        output_format=args.output,
    )


if __name__ == "__main__":
    main()
