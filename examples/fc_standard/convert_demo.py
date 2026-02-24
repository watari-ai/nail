"""FC Standard convert demo — examples/fc_standard/convert_demo.py

Demonstrates converting NAIL tool definitions to OpenAI, Anthropic, and Gemini
formats using the nail_lang FC Standard API (Issue #64, v0.8.0).

Run:
    python3 examples/fc_standard/convert_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nail_lang import (
    to_openai_tool,
    to_anthropic_tool,
    to_gemini_tool,
    from_openai_tool,
    from_anthropic_tool,
    from_gemini_tool,
    convert_tools,
)


# ── Sample NAIL tools (with effect annotations) ────────────────────────────────

NAIL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["path"],
            },
            "effects": ["FS"],
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Send an HTTP GET request to a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target URL"},
                },
                "required": ["url"],
            },
            "effects": ["NET"],
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_uuid",
            "description": "Generate a random UUID v4.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
            "effects": ["RAND"],
        },
    },
]


def _header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def _dump(obj: object) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def demo_to_openai() -> None:
    _header("NAIL → OpenAI (effects stripped)")
    for tool in NAIL_TOOLS:
        result = to_openai_tool(tool)
        print(f"\n[{tool['function']['name']}]")
        _dump(result)
        assert "effects" not in result["function"], "Effects must be removed!"


def demo_to_anthropic() -> None:
    _header("NAIL → Anthropic (input_schema, flat dict)")
    for tool in NAIL_TOOLS:
        result = to_anthropic_tool(tool)
        print(f"\n[{tool['function']['name']}]")
        _dump(result)
        assert "input_schema" in result, "Must have input_schema!"
        assert "type" not in result, "Anthropic format has no type wrapper!"


def demo_to_gemini() -> None:
    _header("NAIL → Gemini (flat dict, parameters key)")
    for tool in NAIL_TOOLS:
        result = to_gemini_tool(tool)
        print(f"\n[{tool['function']['name']}]")
        _dump(result)
        assert "parameters" in result, "Must have parameters!"
        assert "type" not in result, "Gemini format has no type wrapper!"


def demo_from_anthropic() -> None:
    _header("Anthropic → NAIL (auto-infer effects)")
    anthropic_tools = [
        {
            "name": "write_file",
            "description": "Write data to a file on disk.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        }
    ]
    for tool in anthropic_tools:
        result = from_anthropic_tool(tool)
        print(f"\n[{tool['name']}]")
        _dump(result)
        assert result["function"]["effects"] == ["FS"], f"Expected FS, got {result['function']['effects']}"


def demo_from_gemini() -> None:
    _header("Gemini → NAIL (auto-infer effects)")
    gemini_tools = [
        {
            "name": "run_command",
            "description": "Execute a shell command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                },
                "required": ["command"],
            },
        }
    ]
    for tool in gemini_tools:
        result = from_gemini_tool(tool)
        print(f"\n[{tool['name']}]")
        _dump(result)
        # run_command should infer PROC
        assert result["function"]["effects"] == ["PROC"], f"Expected PROC, got {result['function']['effects']}"


def demo_convert_tools_batch() -> None:
    _header("Batch: NAIL → all providers via convert_tools()")

    for target in ("openai", "anthropic", "gemini"):
        converted = convert_tools(NAIL_TOOLS, source="nail", target=target)
        print(f"\n--- target={target!r} ---")
        _dump(converted)
        print(f"  → {len(converted)} tools converted to {target!r} format ✓")

    _header("Batch: Anthropic → Gemini (cross-provider)")
    anthropic_batch = convert_tools(NAIL_TOOLS, source="nail", target="anthropic")
    gemini_batch = convert_tools(anthropic_batch, source="anthropic", target="gemini")
    print(f"\n  → {len(gemini_batch)} tools Anthropic→Gemini ✓")
    _dump(gemini_batch)


def main() -> None:
    print("=" * 60)
    print("  NAIL v0.8.0 — FC Standard Conversion Demo")
    print("  Issue #64: OpenAI / Anthropic / Gemini converters")
    print("=" * 60)

    demo_to_openai()
    demo_to_anthropic()
    demo_to_gemini()
    demo_from_anthropic()
    demo_from_gemini()
    demo_convert_tools_batch()

    print("\n\n✅  All conversions completed successfully!")


if __name__ == "__main__":
    main()
