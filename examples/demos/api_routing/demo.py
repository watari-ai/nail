"""NAIL Demo #104 — Multi-Provider API Routing

Demonstrates converting a single NAIL tool spec into OpenAI, Anthropic, and
Gemini function-calling formats using the nail_lang FC Standard API.

Run:
    cd examples/demos/api_routing
    python3 demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from anywhere in the repo without an editable install
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import nail_lang as nail

SPEC_PATH = Path(__file__).parent / "tool_spec.nail"


def load_and_validate(path: Path) -> list[dict]:
    """Load tool_spec.nail and validate NAIL effect annotations."""
    with path.open() as f:
        spec = json.load(f)

    tools: list[dict] = spec.get("tools", [])
    if not tools:
        raise ValueError(f"No tools found in {path}")

    # Validate that all declared effects are recognised NAIL effect labels
    for tool in tools:
        effects = tool.get("function", {}).get("effects", [])
        if effects:
            nail.validate_effects(effects)  # raises ValueError on unknown effect

    print(f"✅ Spec validated  ({len(tools)} tool(s), path={path.name})")
    return tools


def convert_and_print(tools: list[dict], provider: str) -> None:
    """Convert NAIL tools to a provider format and print the result."""
    converted = nail.convert_tools(tools, source="nail", target=provider)
    # Pretty-print first 300 chars so the output stays readable
    snippet = json.dumps(converted, indent=2, ensure_ascii=False)[:300]
    print(f"\n✅ {provider}:\n{snippet}...")


def main() -> None:
    print("=" * 60)
    print("  NAIL Demo #104 — Multi-Provider API Routing")
    print("  One spec → OpenAI / Anthropic / Gemini, zero drift")
    print("=" * 60)
    print()

    # 1. Load single NAIL spec
    tools = load_and_validate(SPEC_PATH)

    # 2. Convert to each provider format
    for provider in ("openai", "anthropic", "gemini"):
        try:
            convert_and_print(tools, provider)
        except Exception as exc:
            print(f"ℹ️  {provider}: {exc}")

    print()
    print("💡 One NAIL spec → 3 provider formats, zero drift.")


if __name__ == "__main__":
    main()
