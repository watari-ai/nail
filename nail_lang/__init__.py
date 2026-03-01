"""nail_lang — Python API for the NAIL AI-native language.

NAIL (No Ambiguity, Inference-Locked) is a programming language designed to be
written by AI agents. It provides:

- **Zero Ambiguity**: Every program has exactly one valid interpretation.
- **Effect System**: Formal declarations of which side effects (IO, FS, NET, …) a
  function may invoke — checked at level 2.
- **Verification Layers**: L0 (schema), L1 (types), L2 (effects), L3 (termination proofs).
- **JSON-only Syntax**: Programs are plain JSON — no text parsing, no ambiguous syntax.

## Quickstart

```python
from nail_lang import Checker, Runtime, filter_by_effects

# Check a NAIL program
spec = {
    "nail": "0.7.0",
    "kind": "fn",
    "id": "main",
    "effects": ["IO"],
    "params": [],
    "returns": {"type": "unit"},
    "body": [
        {"op": "print", "val": {"lit": "Hello, NAIL"}, "effect": "IO"},
        {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}},
    ],
}

checker = Checker(spec)
checker.check()  # raises CheckError if invalid

runtime = Runtime(spec)
result = runtime.call("main", {})

# Filter AI tools by effect scope (LiteLLM / OpenAI function-calling integration)
tools = [
    {"type": "function", "function": {"name": "read_file", "effects": ["FS"]}},
    {"type": "function", "function": {"name": "http_get",  "effects": ["NET"]}},
    {"type": "function", "function": {"name": "log",       "effects": ["IO"]}},
]
safe_tools = filter_by_effects(tools, allowed=["FS", "IO"])
# → [read_file_tool, log_tool]  — http_get (NET) excluded
```

## See Also

- [NAIL Repository](https://github.com/watari-ai/nail)
- [Effect × LiteLLM Integration](https://github.com/watari-ai/nail/blob/main/integrations/litellm.md)
- [FC Standard Proposal](https://github.com/watari-ai/nail/blob/main/docs/fc-standard-proposal.md)
- [NAIL Playground](https://naillang.com)
"""

from __future__ import annotations

# ── Core language components ────────────────────────────────────────────────
from interpreter.checker import Checker, CheckError
from interpreter.runtime import Runtime
from interpreter.types import (
    NailType,
    NailTypeError,
    NailEffectError,
    NailRuntimeError,
    parse_type,
    substitute_type,
    unify_types,
    TypeParam,
    IntType,
    FloatType,
    BoolType,
    StringType,
    UnitType,
    OptionType,
    ListType,
    MapType,
    ResultType,
    EnumType,
    VALID_EFFECTS as _NAIL_EFFECTS,
)

# ── Function-calling / effect filtering API ─────────────────────────────────
from nail_lang._effects import (
    filter_by_effects,
    get_tool_effects,
    annotate_tool_effects,
    validate_effects,
    VALID_EFFECTS,
)
from nail_lang._mcp import (
    from_mcp,
    to_mcp,
    infer_effects,
)
from nail_lang._fc_standard import (
    to_openai_tool,
    to_anthropic_tool,
    to_gemini_tool,
    from_openai_tool,
    from_anthropic_tool,
    from_gemini_tool,
    convert_tools,
)

# ── fc_ir_v2: Delegation-aware Effect Qualifiers (Issue #107, Phase 1) ──────
from nail_lang.fc_ir_v2 import (
    EffectQualifier,
    FcDef,
    DelegationError,
    parse_effect_qualifier,
    parse_effects,
    parse_def as parse_fc_def,
    check_call as check_delegation_call,
    check_program as check_delegation_program,
)

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("nail-lang")
except Exception:
    __version__ = "0.9.1"  # fallback

__all__ = [
    # Core
    "Checker",
    "CheckError",
    "Runtime",
    # Types
    "NailType",
    "NailTypeError",
    "NailEffectError",
    "NailRuntimeError",
    "parse_type",
    "substitute_type",
    "unify_types",
    "TypeParam",
    "IntType",
    "FloatType",
    "BoolType",
    "StringType",
    "UnitType",
    "OptionType",
    "ListType",
    "MapType",
    "ResultType",
    "EnumType",
    # Effect filtering (LiteLLM / OpenAI FC integration)
    "filter_by_effects",
    "get_tool_effects",
    "annotate_tool_effects",
    "validate_effects",
    "VALID_EFFECTS",
    # MCP bridge
    "from_mcp",
    "to_mcp",
    "infer_effects",
    # FC Standard (Issue #64)
    "to_openai_tool",
    "to_anthropic_tool",
    "to_gemini_tool",
    "from_openai_tool",
    "from_anthropic_tool",
    "from_gemini_tool",
    "convert_tools",
    # fc_ir_v2: Delegation-aware Effect Qualifiers (Issue #107, Phase 1)
    "EffectQualifier",
    "FcDef",
    "DelegationError",
    "parse_effect_qualifier",
    "parse_effects",
    "parse_fc_def",
    "check_delegation_call",
    "check_delegation_program",
    # Meta
    "__version__",
]
