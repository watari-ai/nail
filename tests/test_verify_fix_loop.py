#!/usr/bin/env python3
"""
NAIL #103 — Multi-LLM Verify-Fix Loop benchmark tests.

Covers:
  - MockLLM behaviour (pass on attempt N, never pass)
  - verify_fix_loop mechanics (retries, error propagation)
  - JSON extraction from LLM responses (fences, prose)
  - BenchResult serialisation
  - summarize_results.py analysis functions
  - End-to-end benchmark run (mock mode)

Run:
    python -m pytest tests/test_verify_fix_loop.py -v
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

import pytest

# ── project root ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from benchmarks.verify_fix_loop import (
    BenchResult,
    MockLLM,
    _corrupt_spec,
    _extract_json,
    _load_template,
    build_clients,
    check_spec,
    run_benchmark,
    verify_fix_loop,
    TASK_PROMPTS,
    TASK_LEVELS,
)
from benchmarks.summarize_results import summarize, load_csv

# ── helpers ───────────────────────────────────────────────────────────────────

VALID_FN_SPEC = {
    "nail": "0.1.0",
    "kind": "fn",
    "id": "add",
    "effects": [],
    "params": [
        {"id": "a", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
        {"id": "b", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
    ],
    "returns": {"type": "int", "bits": 64, "overflow": "panic"},
    "body": [
        {"op": "return", "val": {"l": {"ref": "a"}, "op": "+", "r": {"ref": "b"}}}
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. check_spec
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckSpec:
    def test_valid_spec_passes(self):
        passed, err = check_spec(VALID_FN_SPEC, level=2)
        assert passed is True
        assert err == ""

    def test_missing_body_fails(self):
        bad = {k: v for k, v in VALID_FN_SPEC.items() if k != "body"}
        passed, err = check_spec(bad, level=2)
        assert passed is False
        assert err != ""

    def test_effect_violation_fails(self):
        """Declaring no effects but using IO should fail L2."""
        spec = {
            "nail": "0.1.0",
            "kind": "fn",
            "id": "sneaky",
            "effects": [],
            "params": [],
            "returns": {"type": "unit"},
            "body": [
                {"op": "print", "val": {"lit": "hi"}, "effect": "IO"},
                {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}},
            ],
        }
        passed, err = check_spec(spec, level=2)
        assert passed is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. _extract_json
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractJson:
    def test_plain_json(self):
        raw = json.dumps(VALID_FN_SPEC)
        result = _extract_json(raw)
        assert result["id"] == "add"

    def test_json_with_prose(self):
        raw = "Here is the spec:\n" + json.dumps(VALID_FN_SPEC) + "\nHope this helps!"
        result = _extract_json(raw)
        assert result["kind"] == "fn"

    def test_json_with_code_fence(self):
        raw = "```json\n" + json.dumps(VALID_FN_SPEC) + "\n```"
        result = _extract_json(raw)
        assert result["nail"] == "0.1.0"

    def test_invalid_json_raises(self):
        with pytest.raises((json.JSONDecodeError, ValueError)):
            _extract_json("not valid json at all {{{")


# ─────────────────────────────────────────────────────────────────────────────
# 3. MockLLM
# ─────────────────────────────────────────────────────────────────────────────

class TestMockLLM:
    def test_pass_on_first_attempt(self):
        """MockLLM(pass_on_attempt=1) should return valid spec immediately."""
        client = MockLLM("test/perfect", pass_on_attempt=1, seed=0)
        client.set_task("simple_calculator")
        raw = client.generate("generate spec")
        spec = json.loads(raw)
        passed, _ = check_spec(spec, level=2)
        assert passed is True

    def test_pass_on_second_attempt(self):
        """First response is bad, second is valid."""
        client = MockLLM("test/slow", pass_on_attempt=2, seed=0)
        client.set_task("simple_calculator")
        raw1 = client.generate("generate spec")
        # First attempt should be broken
        spec1 = json.loads(raw1)
        # set_task resets counter; manually increment
        raw2 = client.generate("retry", error_feedback="some error")
        spec2 = json.loads(raw2)
        passed2, _ = check_spec(spec2, level=2)
        assert passed2 is True

    def test_never_passes(self):
        """pass_on_attempt=0 means always broken."""
        client = MockLLM("test/bad", pass_on_attempt=0, seed=0)
        client.set_task("simple_calculator")
        for _ in range(4):
            raw = client.generate("generate spec", error_feedback="error")
            spec = json.loads(raw)
            passed, _ = check_spec(spec, level=2)
            assert passed is False

    def test_set_task_resets_counter(self):
        """After set_task, attempt counter restarts."""
        client = MockLLM("test/reset", pass_on_attempt=1, seed=0)
        client.set_task("simple_calculator")
        # consume first valid attempt
        client.generate("go")
        # reset to a new task
        client.set_task("user_auth")
        raw = client.generate("new task")
        spec = json.loads(raw)
        passed, _ = check_spec(spec, level=2)
        assert passed is True  # attempt 1 of new task → valid


# ─────────────────────────────────────────────────────────────────────────────
# 4. verify_fix_loop
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifyFixLoop:
    def _run(self, pass_on: int, task: str = "simple_calculator") -> BenchResult:
        client = MockLLM(f"test/p{pass_on}", pass_on_attempt=pass_on, seed=42)
        return verify_fix_loop(
            client=client,
            task=task,
            prompt=TASK_PROMPTS[task],
            level=TASK_LEVELS[task],
            max_retries=3,
            verbose=False,
        )

    def test_first_try_pass(self):
        result = self._run(1)
        assert result.final_pass is True
        assert result.attempts == 1
        assert result.error_codes == []

    def test_second_try_pass(self):
        result = self._run(2)
        assert result.final_pass is True
        assert result.attempts == 2
        assert len(result.error_codes) == 1

    def test_third_try_pass(self):
        result = self._run(3)
        assert result.final_pass is True
        assert result.attempts == 3

    def test_never_passes(self):
        result = self._run(0)
        assert result.final_pass is False
        assert result.attempts == 3  # exhausted retries
        assert len(result.error_codes) == 3

    def test_user_auth_task(self):
        result = self._run(1, task="user_auth")
        assert result.final_pass is True
        assert result.task == "user_auth"

    def test_data_pipeline_task(self):
        result = self._run(1, task="data_pipeline")
        assert result.final_pass is True
        assert result.task == "data_pipeline"

    def test_result_fields(self):
        result = self._run(1)
        assert result.model == "test/p1"
        assert result.latency_ms >= 0
        assert isinstance(result.error_codes, list)

    def test_csv_serialisation(self):
        result = self._run(2)
        row = result.to_csv_row()
        assert row["model"] == "test/p2"
        # attempts is kept as int in the dict; csv.DictWriter coerces to str on write
        assert row["attempts"] == 2
        assert row["final_pass"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 5. summarize_results
# ─────────────────────────────────────────────────────────────────────────────

class TestSummarizeResults:
    def _make_rows(self) -> list[dict]:
        return [
            {"model": "A", "task": "t1", "attempts": 1, "final_pass": True,  "error_codes": "", "latency_ms": 10},
            {"model": "A", "task": "t2", "attempts": 2, "final_pass": True,  "error_codes": "X", "latency_ms": 20},
            {"model": "B", "task": "t1", "attempts": 3, "final_pass": False, "error_codes": "X|Y|Z", "latency_ms": 30},
            {"model": "B", "task": "t2", "attempts": 1, "final_pass": True,  "error_codes": "", "latency_ms": 5},
        ]

    def test_pass_rates(self):
        summary = summarize(self._make_rows())
        assert summary["per_model"]["A"]["pass_rate"] == 1.0
        assert summary["per_model"]["B"]["pass_rate"] == 0.5
        assert summary["per_task"]["t1"]["pass_rate"] == 0.5
        assert summary["per_task"]["t2"]["pass_rate"] == 1.0

    def test_avg_attempts(self):
        summary = summarize(self._make_rows())
        assert summary["per_model"]["A"]["avg_attempts"] == 1.5
        assert summary["per_model"]["B"]["avg_attempts"] == 2.0

    def test_consensus(self):
        """t2: both pass → consensus=1.0; t1: mixed → consensus=0.5."""
        summary = summarize(self._make_rows())
        assert summary["consensus"]["t2"] == 1.0
        assert summary["consensus"]["t1"] == 0.5

    def test_overall_fields(self):
        summary = summarize(self._make_rows())
        assert summary["overall"]["total"] == 4
        assert summary["overall"]["pass_rate"] == 0.75

    def test_empty_rows(self):
        summary = summarize([])
        assert summary["overall"]["total"] == 0
        assert summary["overall"]["pass_rate"] is None

    def test_load_csv_roundtrip(self):
        """Write a CSV then read it back; values should match."""
        rows = [
            BenchResult("m1", "t1", 1, True, [], 12.3),
            BenchResult("m2", "t2", 2, False, ["ERR"], 45.6),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=["model", "task", "attempts", "final_pass", "error_codes", "latency_ms"])
            writer.writeheader()
            for r in rows:
                writer.writerow(r.to_csv_row())
            tmp_path = Path(f.name)

        loaded = load_csv(tmp_path)
        assert len(loaded) == 2
        assert loaded[0]["model"] == "m1"
        assert loaded[0]["final_pass"] is True
        assert loaded[1]["final_pass"] is False
        tmp_path.unlink()


# ─────────────────────────────────────────────────────────────────────────────
# 6. End-to-end benchmark run (mock mode)
# ─────────────────────────────────────────────────────────────────────────────

class TestEndToEnd:
    def test_run_benchmark_mock(self):
        """Full mock run: 4 models × 3 tasks = 12 results."""
        clients = build_clients(real_api=False)
        results = run_benchmark(clients=clients, verbose=False, save=False)
        assert len(results) == 12

    def test_benchmark_results_structure(self):
        clients = build_clients(real_api=False)
        results = run_benchmark(clients=clients, verbose=False, save=False)
        for r in results:
            assert isinstance(r, BenchResult)
            assert r.task in TASK_PROMPTS
            assert r.attempts >= 1
            assert isinstance(r.final_pass, bool)

    def test_perfect_llm_always_passes(self):
        """The 'perfect-llm' mock (pass_on_attempt=1) should pass all 3 tasks."""
        clients = [MockLLM("mock/perfect-llm", pass_on_attempt=1, seed=1)]
        results = run_benchmark(clients=clients, verbose=False, save=False)
        for r in results:
            assert r.final_pass is True, f"Expected pass for task {r.task}"

    def test_failing_llm_never_passes(self):
        """The 'failing-llm' mock (pass_on_attempt=0) should fail all 3 tasks."""
        clients = [MockLLM("mock/failing-llm", pass_on_attempt=0, seed=4)]
        results = run_benchmark(clients=clients, verbose=False, save=False)
        for r in results:
            assert r.final_pass is False, f"Expected fail for task {r.task}"

    def test_save_creates_csv(self, tmp_path, monkeypatch):
        """--save should create a CSV in benchmarks/results/."""
        import benchmarks.verify_fix_loop as vfl
        # Redirect RESULTS_DIR to tmp_path
        monkeypatch.setattr(vfl, "RESULTS_DIR", tmp_path)
        clients = [MockLLM("test/save", pass_on_attempt=1, seed=0)]
        run_benchmark(clients=clients, verbose=False, save=True)
        csvs = list(tmp_path.glob("verify_fix_loop_*.csv"))
        assert len(csvs) == 1
        loaded = load_csv(csvs[0])
        assert len(loaded) == 3  # 3 tasks


# ─────────────────────────────────────────────────────────────────────────────
# 7. Template validity
# ─────────────────────────────────────────────────────────────────────────────

class TestTemplates:
    @pytest.mark.parametrize("task,level", [
        ("simple_calculator", 2),
        ("user_auth", 2),
        ("data_pipeline", 3),
    ])
    def test_template_is_valid(self, task, level):
        """Reference templates must pass the NAIL Checker."""
        spec = _load_template(task)
        assert spec, f"Template for {task} could not be loaded"
        passed, err = check_spec(spec, level=level)
        assert passed is True, f"Template {task} failed checker: {err}"
