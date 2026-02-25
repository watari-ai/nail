#!/usr/bin/env python3
"""NAIL Token Efficiency Benchmark
====================================
Compares token usage for equivalent function semantics across:
  - NAIL (canonical JSON)
  - Python (with full type annotations + docstrings for effects)
  - TypeScript (with JSDoc + generics)
  - OpenAI FC JSON (tool_call schema)

Tokenizer: tiktoken cl100k_base (GPT-4 / GPT-3.5-turbo compatible)
Fallback: character count if tiktoken is unavailable.

Usage:
  python benchmarks/token_efficiency.py
  python benchmarks/token_efficiency.py --output json
  python benchmarks/token_efficiency.py --output csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from pathlib import Path
from typing import NamedTuple

# ── Tokenizer setup ──────────────────────────────────────────────────────────

try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

    TOKENIZER = "tiktoken:cl100k_base"
except ImportError:  # pragma: no cover
    def count_tokens(text: str) -> int:  # type: ignore[misc]
        # Rough approximation: 1 token ≈ 4 chars (OpenAI rule of thumb)
        return (len(text) + 3) // 4

    TOKENIZER = "char_approx"


# ── Benchmark scenarios ──────────────────────────────────────────────────────

class Scenario(NamedTuple):
    name: str
    description: str
    nail: str
    python: str
    typescript: str
    openai_fc: str


# ── Scenario 1: Simple typed function ────────────────────────────────────────
# add(a: int64, b: int64) -> int64
# Both NAIL and target languages encode the same semantics (types + body).

S1_NAIL = '{"body":[{"op":"return","val":{"l":{"ref":"a"},"op":"+","r":{"ref":"b"}}}],"effects":[],"id":"add","kind":"fn","nail":"0.9","params":[{"id":"a","type":{"bits":64,"overflow":"panic","type":"int"}},{"id":"b","type":{"bits":64,"overflow":"panic","type":"int"}}],"returns":{"bits":64,"overflow":"panic","type":"int"}}'

S1_PYTHON = """\
def add(a: int, b: int) -> int:
    return a + b"""

S1_TYPESCRIPT = """\
function add(a: number, b: number): number {
    return a + b;
}"""

# OpenAI FC schema for equivalent tool (function calling format)
S1_OPENAI_FC = json.dumps({
    "type": "function",
    "function": {
        "name": "add",
        "description": "Add two 64-bit integers and return the result.",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "First operand (int64)"},
                "b": {"type": "integer", "description": "Second operand (int64)"},
            },
            "required": ["a", "b"],
        },
    },
}, separators=(",", ":"))

SCENARIO_1 = Scenario(
    name="simple_typed_function",
    description="add(a: int64, b: int64) -> int64 — pure arithmetic",
    nail=S1_NAIL,
    python=S1_PYTHON,
    typescript=S1_TYPESCRIPT,
    openai_fc=S1_OPENAI_FC,
)

# ── Scenario 2: Effect-annotated function ────────────────────────────────────
# read_file(path: str) -> str  with FS effect
# In NAIL: effects encoded in JSON. In Python/TS: requires docstring/comments.
# In OpenAI FC: no standard way to declare side effects.

S2_NAIL = '{"effects":["FS"],"id":"read_file","kind":"fn","nail":"0.9","params":[{"id":"path","type":{"encoding":"utf8","type":"string"}},{"id":"encoding","default":"utf-8","type":{"encoding":"utf8","type":"string"}}],"returns":{"encoding":"utf8","type":"string"}}'

S2_PYTHON = """\
def read_file(path: str, encoding: str = "utf-8") -> str:
    \"\"\"Read file contents from the local filesystem.

    Effects:
        FS: reads from the local filesystem

    Args:
        path: Absolute or relative path to the file.
        encoding: Text encoding (default: utf-8).

    Returns:
        File contents as a string.
    \"\"\"
    with open(path, encoding=encoding) as f:
        return f.read()"""

S2_TYPESCRIPT = """\
/**
 * Read file contents from the local filesystem.
 *
 * @effects FS - reads from the local filesystem
 * @param path - Absolute or relative path to the file
 * @param encoding - Text encoding (default: "utf-8")
 * @returns File contents as a string
 */
function readFile(path: string, encoding: string = "utf-8"): string {
    return require("fs").readFileSync(path, encoding);
}"""

S2_OPENAI_FC = json.dumps({
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file from the local filesystem.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to the file."},
                "encoding": {"type": "string", "description": "Text encoding.", "default": "utf-8"},
            },
            "required": ["path"],
        },
    },
}, separators=(",", ":"))

SCENARIO_2 = Scenario(
    name="effect_annotated_function",
    description="read_file(path, encoding) -> str [FS] — filesystem access with effect declaration",
    nail=S2_NAIL,
    python=S2_PYTHON,
    typescript=S2_TYPESCRIPT,
    openai_fc=S2_OPENAI_FC,
)

# ── Scenario 3: Result type / error handling ──────────────────────────────────
# safe_div(a: int64, b: int64) -> Result<int64, str>
# NAIL natively encodes Result; Python needs Union/tuple; TS needs custom type.

S3_NAIL = '{"body":[{"cond":{"l":{"ref":"b"},"op":"eq","r":{"lit":0}},"else":[{"op":"return","val":{"op":"ok","val":{"l":{"ref":"a"},"op":"/","r":{"ref":"b"}}}}],"op":"if","then":[{"op":"return","val":{"op":"err","val":{"lit":"division by zero"}}}]}],"effects":[],"id":"safe_div","kind":"fn","nail":"0.9","params":[{"id":"a","type":{"bits":64,"overflow":"panic","type":"int"}},{"id":"b","type":{"bits":64,"overflow":"panic","type":"int"}}],"returns":{"err":{"encoding":"utf8","type":"string"},"ok":{"bits":64,"overflow":"panic","type":"int"},"type":"result"}}'

S3_PYTHON = """\
from typing import Union

def safe_div(a: int, b: int) -> Union[int, str]:
    \"\"\"Divide a by b, returning an error string on division by zero.

    Returns:
        int: quotient if b != 0
        str: \"division by zero\" error message if b == 0
    \"\"\"
    if b == 0:
        return "division by zero"
    return a // b"""

S3_TYPESCRIPT = """\
type Result<T, E> = { ok: true; value: T } | { ok: false; error: E };

/**
 * Divide a by b, returning a Result type.
 * @returns Result<number, string> - ok=quotient or error="division by zero"
 */
function safeDiv(a: number, b: number): Result<number, string> {
    if (b === 0) {
        return { ok: false, error: "division by zero" };
    }
    return { ok: true, value: Math.floor(a / b) };
}"""

S3_OPENAI_FC = json.dumps({
    "type": "function",
    "function": {
        "name": "safe_div",
        "description": "Divide a by b. Returns ok/value on success or ok/error on division by zero.",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "Numerator (int64)"},
                "b": {"type": "integer", "description": "Denominator (int64); must not be zero"},
            },
            "required": ["a", "b"],
        },
    },
}, separators=(",", ":"))

SCENARIO_3 = Scenario(
    name="result_type_function",
    description="safe_div(a, b) -> Result<int64, str> — structured error handling",
    nail=S3_NAIL,
    python=S3_PYTHON,
    typescript=S3_TYPESCRIPT,
    openai_fc=S3_OPENAI_FC,
)

# ── Scenario 4: FC Standard multi-tool module ─────────────────────────────────
# Full tool module: read_file + write_file + http_get
# NAIL FC Standard (canonical) vs equivalent in other formats.
# This is NAIL's target domain: AI tool definitions for function calling.

S4_NAIL = '{"doc":"Multi-provider tool module (NAIL FC Standard v0.8).","id":"file_tools","kind":"module","nail":"0.9","tools":[{"function":{"description":"Read the contents of a file from the local filesystem.","effects":["FS"],"name":"read_file","parameters":{"properties":{"encoding":{"default":"utf-8","description":"Text encoding.","type":"string"},"path":{"description":"Absolute path to the file.","type":"string"}},"required":["path"],"type":"object"}},"type":"function"},{"function":{"description":"Write content to a file on the local filesystem.","effects":["FS"],"name":"write_file","parameters":{"properties":{"content":{"description":"Text content to write.","type":"string"},"overwrite":{"default":false,"description":"Overwrite if exists.","type":"boolean"},"path":{"description":"Destination file path.","type":"string"}},"required":["path","content"],"type":"object"}},"type":"function"},{"function":{"description":"Send an HTTP GET request and return the response body.","effects":["NET"],"name":"http_get","parameters":{"properties":{"url":{"description":"Target URL.","type":"string"}},"required":["url"],"type":"object"}},"type":"function"}]}'

S4_PYTHON = """\
class FileTools:
    \"\"\"Multi-provider tool module with effect annotations.\"\"\"

    @staticmethod
    def read_file(path: str, encoding: str = "utf-8") -> str:
        \"\"\"Read the contents of a file from the local filesystem.

        Effects: FS
        Args:
            path: Absolute path to the file.
            encoding: Text encoding.
        \"\"\"
        ...

    @staticmethod
    def write_file(path: str, content: str, overwrite: bool = False) -> None:
        \"\"\"Write content to a file on the local filesystem.

        Effects: FS
        Args:
            path: Destination file path.
            content: Text content to write.
            overwrite: Overwrite if exists.
        \"\"\"
        ...

    @staticmethod
    def http_get(url: str) -> str:
        \"\"\"Send an HTTP GET request and return the response body.

        Effects: NET
        Args:
            url: Target URL.
        \"\"\"
        ..."""

S4_TYPESCRIPT = """\
/**
 * Multi-provider tool module with effect annotations.
 */
interface FileTools {
    /**
     * Read the contents of a file from the local filesystem.
     * @effects FS
     * @param path - Absolute path to the file
     * @param encoding - Text encoding (default: "utf-8")
     */
    readFile(path: string, encoding?: string): string;

    /**
     * Write content to a file on the local filesystem.
     * @effects FS
     * @param path - Destination file path
     * @param content - Text content to write
     * @param overwrite - Overwrite if exists (default: false)
     */
    writeFile(path: string, content: string, overwrite?: boolean): void;

    /**
     * Send an HTTP GET request and return the response body.
     * @effects NET
     * @param url - Target URL
     */
    httpGet(url: string): string;
}"""

# OpenAI FC JSON for the same 3 tools (standard format, no effects)
S4_OPENAI_FC = json.dumps([
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the file."},
                    "encoding": {"type": "string", "description": "Text encoding.", "default": "utf-8"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file on the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Destination file path."},
                    "content": {"type": "string", "description": "Text content to write."},
                    "overwrite": {"type": "boolean", "description": "Overwrite if exists.", "default": False},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Send an HTTP GET request and return the response body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target URL."},
                },
                "required": ["url"],
            },
        },
    },
], separators=(",", ":"))

SCENARIO_4 = Scenario(
    name="fc_standard_module",
    description="Multi-tool module: read_file[FS] + write_file[FS] + http_get[NET]",
    nail=S4_NAIL,
    python=S4_PYTHON,
    typescript=S4_TYPESCRIPT,
    openai_fc=S4_OPENAI_FC,
)

# ── All scenarios ─────────────────────────────────────────────────────────────

ALL_SCENARIOS: list[Scenario] = [SCENARIO_1, SCENARIO_2, SCENARIO_3, SCENARIO_4]


# ── Measurement ───────────────────────────────────────────────────────────────

class Result(NamedTuple):
    scenario: str
    description: str
    nail_tokens: int
    python_tokens: int
    typescript_tokens: int
    openai_fc_tokens: int
    nail_vs_python_pct: float     # negative = NAIL uses fewer tokens
    nail_vs_typescript_pct: float
    nail_vs_openai_fc_pct: float


def measure(scenario: Scenario) -> Result:
    nail_t = count_tokens(scenario.nail)
    py_t = count_tokens(scenario.python)
    ts_t = count_tokens(scenario.typescript)
    ofc_t = count_tokens(scenario.openai_fc)

    def pct(nail: int, other: int) -> float:
        """How many % more/fewer tokens does NAIL use relative to other?
        Negative = NAIL is more efficient (uses fewer tokens).
        """
        if other == 0:
            return 0.0
        return round((nail - other) / other * 100, 1)

    return Result(
        scenario=scenario.name,
        description=scenario.description,
        nail_tokens=nail_t,
        python_tokens=py_t,
        typescript_tokens=ts_t,
        openai_fc_tokens=ofc_t,
        nail_vs_python_pct=pct(nail_t, py_t),
        nail_vs_typescript_pct=pct(nail_t, ts_t),
        nail_vs_openai_fc_pct=pct(nail_t, ofc_t),
    )


# ── Output formatters ─────────────────────────────────────────────────────────

def _pct_str(pct: float) -> str:
    """Human-readable percentage with sign and direction indicator."""
    if pct < 0:
        return f"{pct:+.1f}% (NAIL saves {-pct:.0f}%)"
    elif pct > 0:
        return f"{pct:+.1f}% (NAIL costs {pct:.0f}% more)"
    return "0.0% (equal)"


def print_table(results: list[Result]) -> None:
    print(f"\n{'='*78}")
    print("NAIL Token Efficiency Benchmark")
    print(f"Tokenizer: {TOKENIZER}")
    print(f"{'='*78}\n")

    # Per-scenario table
    header = f"{'Scenario':<32} {'NAIL':>6} {'Python':>7} {'TypeScript':>11} {'OpenAI FC':>10}"
    print(header)
    print("-" * len(header))
    for r in results:
        label = r.scenario[:30]
        print(f"{label:<32} {r.nail_tokens:>6} {r.python_tokens:>7} {r.typescript_tokens:>11} {r.openai_fc_tokens:>10}")

    print()

    # Relative efficiency summary
    print("Relative Efficiency (NAIL vs others):")
    print(f"  {'Scenario':<32} {'vs Python':>30} {'vs TypeScript':>35} {'vs OpenAI FC':>35}")
    print("  " + "-" * 105)
    for r in results:
        label = r.scenario[:30]
        print(
            f"  {label:<32} "
            f"{_pct_str(r.nail_vs_python_pct):>30} "
            f"{_pct_str(r.nail_vs_typescript_pct):>35} "
            f"{_pct_str(r.nail_vs_openai_fc_pct):>35}"
        )

    print()

    # Aggregate summary
    avg_vs_py = sum(r.nail_vs_python_pct for r in results) / len(results)
    avg_vs_ts = sum(r.nail_vs_typescript_pct for r in results) / len(results)
    avg_vs_ofc = sum(r.nail_vs_openai_fc_pct for r in results) / len(results)

    # Effect-annotated scenarios only (S2, S4 — where effects matter)
    effect_results = [r for r in results if "effect" in r.scenario or "fc_standard" in r.scenario]
    eff_avg_vs_py = sum(r.nail_vs_python_pct for r in effect_results) / len(effect_results)
    eff_avg_vs_ts = sum(r.nail_vs_typescript_pct for r in effect_results) / len(effect_results)

    print("Aggregate averages (all scenarios):")
    print(f"  NAIL vs Python:     {avg_vs_py:+.1f}% average")
    print(f"  NAIL vs TypeScript: {avg_vs_ts:+.1f}% average")
    print(f"  NAIL vs OpenAI FC:  {avg_vs_ofc:+.1f}% average")
    print()
    print("Effect-annotated scenarios only (S2 + S4):")
    print(f"  NAIL vs Python:     {eff_avg_vs_py:+.1f}% average")
    print(f"  NAIL vs TypeScript: {eff_avg_vs_ts:+.1f}% average")
    print(f"  (OpenAI FC has no effect encoding — structurally incomparable)")
    print()


def to_json_output(results: list[Result]) -> dict:
    return {
        "tokenizer": TOKENIZER,
        "results": [r._asdict() for r in results],
        "summary": {
            "avg_nail_vs_python_pct": round(
                sum(r.nail_vs_python_pct for r in results) / len(results), 1
            ),
            "avg_nail_vs_typescript_pct": round(
                sum(r.nail_vs_typescript_pct for r in results) / len(results), 1
            ),
            "avg_nail_vs_openai_fc_pct": round(
                sum(r.nail_vs_openai_fc_pct for r in results) / len(results), 1
            ),
        },
    }


def to_csv_output(results: list[Result]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "scenario", "description",
        "nail_tokens", "python_tokens", "typescript_tokens", "openai_fc_tokens",
        "nail_vs_python_pct", "nail_vs_typescript_pct", "nail_vs_openai_fc_pct",
    ])
    for r in results:
        writer.writerow(list(r))
    return buf.getvalue()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="NAIL Token Efficiency Benchmark")
    parser.add_argument(
        "--output",
        choices=["table", "json", "csv", "all"],
        default="all",
        help="Output format (default: all)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save results to benchmarks/results/",
    )
    args = parser.parse_args()

    results = [measure(s) for s in ALL_SCENARIOS]

    if args.output in ("table", "all"):
        print_table(results)

    json_data = to_json_output(results)

    if args.output in ("json", "all"):
        print(json.dumps(json_data, indent=2))

    if args.output in ("csv", "all"):
        if args.output == "csv":
            print(to_csv_output(results))

    # Always save results to benchmarks/results/
    repo_root = Path(__file__).resolve().parent.parent
    results_dir = repo_root / "benchmarks" / "results"
    results_dir.mkdir(exist_ok=True)

    json_path = results_dir / "token_efficiency.json"
    csv_path = results_dir / "token_efficiency.csv"

    json_path.write_text(json.dumps(json_data, indent=2))
    csv_path.write_text(to_csv_output(results))

    if args.output == "all":
        print(f"\nResults saved:")
        print(f"  {json_path}")
        print(f"  {csv_path}")


if __name__ == "__main__":
    main()
