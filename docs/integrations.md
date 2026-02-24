# NAIL Integrations

Adapters that bring NAIL's effect system vocabulary to external LLM frameworks.

---

## Function Calling Effect Annotations

**Module:** `integrations/function_calling.py`  
**Proposal:** `proposals/function-calling-effects.md`

### Why?

OpenAI and Anthropic function-calling schemas describe parameter types precisely —
but say nothing about *side effects*. A sandbox runtime enforcing safety policies
has no schema-level answer to questions like:

- Does `send_email` touch the network?
- Does `read_file` access the filesystem?
- Is `pure_calc` safe to run without any capabilities?

This integration extends tool schemas with a NAIL `effects` field that answers
those questions declaratively — no runtime inference, no per-tool hardcoding.

---

### Effect Vocabulary (from `SPEC.md §3`)

| Effect | Meaning |
|--------|---------|
| `"IO"` | Standard I/O (stdin / stdout) |
| `"FS"` | Filesystem access (read or write) |
| `"NET"` | Network access (HTTP, DNS, sockets) |
| `"TIME"` | Current time access |
| `"RAND"` | Random number generation |
| `"MUT"` | Mutable global state |
| `[]` | **Pure** — zero side effects |
| `["*"]` | **Unknown** — effects not declared |

---

### Quick Start

```python
from integrations.function_calling import (
    from_openai,
    from_anthropic,
    to_nail_annotated,
    filter_by_effects,
    annotate_openai_tool_list,
)

# --- 1. Parse an existing OpenAI schema ---
read_file_schema = {
    "name": "read_file",
    "description": "Read contents of a file from disk",
    "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}

fn = from_openai(read_file_schema)
print(fn.name)          # "read_file"
print(fn.effects)       # None  ← unknown, no annotation yet
print(fn.is_unknown())  # True

# --- 2. Annotate with NAIL effects ---
annotated = to_nail_annotated(fn, ["FS"])
print(annotated.effects)    # ["FS"]
print(annotated.is_pure())  # False

# Serialise back to dict (ready to pass to OpenAI / Anthropic SDKs)
print(annotated.to_dict())
# {
#   "name": "read_file",
#   "description": "Read contents of a file from disk",
#   "effects": ["FS"],
#   "parameters": { ... }
# }

# --- 3. Declare a pure function ---
calc_schema = {"name": "pure_calc", "parameters": {...}}
pure_fn = to_nail_annotated(from_openai(calc_schema), [])
print(pure_fn.is_pure())  # True

# --- 4. Annotate an Anthropic tool ---
tool = {
    "name": "read_file",
    "description": "Read contents of a file from disk",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
    },
}
fn = from_anthropic(tool)
annotated = to_nail_annotated(fn, ["FS"])
```

---

### Batch Annotation

Annotate an entire tool list at once using an *effect map*:

```python
from integrations.function_calling import annotate_openai_tool_list

tools = [
    {"name": "send_email",  "parameters": {...}},
    {"name": "read_file",   "parameters": {...}},
    {"name": "pure_calc",   "parameters": {...}},
    {"name": "get_weather", "parameters": {...}},
]

effect_map = {
    "send_email":  ["NET", "IO"],   # uses network + stdout
    "read_file":   ["FS"],          # filesystem only
    "pure_calc":   [],              # explicitly pure
    "get_weather": ["NET", "TIME"], # network + current time
}

annotated_tools = annotate_openai_tool_list(tools, effect_map)
# Returns a list of dicts with "effects" injected.
# Tools not in effect_map get effects: ["*"] (unknown).
```

---

### Sandbox Policy Enforcement

Filter tools to only those whose effects are within an allowed set:

```python
from integrations.function_calling import (
    from_openai, to_nail_annotated, filter_by_effects
)

# Build annotated tool objects
read_file  = to_nail_annotated(from_openai(read_file_schema),  ["FS"])
send_email = to_nail_annotated(from_openai(send_email_schema), ["NET", "IO"])
pure_calc  = to_nail_annotated(from_openai(calc_schema),       [])

all_tools = [read_file, send_email, pure_calc]

# Sandbox: only filesystem access allowed
sandbox_tools = filter_by_effects(all_tools, allowed=["FS"])
# → [read_file, pure_calc]
# send_email is excluded because NET ∉ {"FS"}
# pure_calc  is included because {} ⊆ {"FS"}

# Strict sandbox: no side effects at all
pure_only = filter_by_effects(all_tools, allowed=[])
# → [pure_calc]
```

> **Note:** Functions with *unknown* effects (`effects=None`) are **always excluded**
> from filtered results. Unknown is treated as potentially unrestricted — a
> conservative safe default.

---

### Capability Check

Quickly test whether a function requires a particular effect:

```python
from integrations.function_calling import requires_any

if requires_any(tool, ["NET"]):
    raise RuntimeError(f"Tool '{tool.name}' needs network access — blocked in sandbox")
```

`requires_any` returns `True` (conservative) for functions with unknown effects.

---

### Effect Validation

```python
from integrations.function_calling import validate_effects

validate_effects(["FS", "NET"])  # ✅ ok
validate_effects([])             # ✅ ok (pure)
validate_effects(["DISK"])       # ❌ ValueError: Unknown NAIL effect kind: 'DISK'
```

---

### NAILFunction API Reference

| Method / Property | Description |
|---|---|
| `fn.name` | Function name |
| `fn.description` | Human-readable description |
| `fn.effects` | `list[str]` or `None` (unknown) |
| `fn.parameters` | OpenAI-style parameter schema or `None` |
| `fn.input_schema` | Anthropic-style input schema or `None` |
| `fn.fmt` | Original format: `"openai"` / `"anthropic"` / `"nail"` |
| `fn.is_pure()` | `True` iff `effects == []` |
| `fn.is_unknown()` | `True` iff `effects is None` |
| `fn.has_effect(kind)` | `True` iff *kind* is in declared effects (conservative for unknown) |
| `fn.to_dict()` | Serialise to annotated dict |

---

### Design Principles

1. **Backward compatible** — Schemas without `effects` remain valid; they are
   treated as `["*"]` (unknown/unrestricted) at the policy layer.

2. **Explicit pure declaration** — `"effects": []` is an intentional signal, not
   an absent field. A missing field and an empty list have distinct semantics.

3. **Conservative unknown** — When effects are undeclared, all policy helpers
   (`has_effect`, `requires_any`) assume the worst. Sandboxes exclude unknowns.

4. **Immutable annotation** — `to_nail_annotated` never mutates the source
   function; it returns a new `NAILFunction` object.

5. **Shared vocabulary** — The same effect kinds used in NAIL function
   declarations (`SPEC.md §3`) appear in tool schemas verbatim. No translation layer.

---

### Relationship to NAIL Effect System

This integration is a direct projection of NAIL's L2 effect system onto the
Function Calling domain:

| NAIL function | Function Calling schema |
|---|---|
| `"effects": []` | `"effects": []` |
| `"effects": ["NET"]` | `"effects": ["NET"]` |
| `"effects": ["FS", "IO"]` | `"effects": ["FS", "IO"]` |

For tools implemented as NAIL functions, the `effects` field in the JSON schema
can be auto-derived from the NAIL function's own effect declaration — no manual
annotation needed.

For tools implemented in other languages, `effects` is a **trusted declaration**
verified by convention, code review, or static analysis tooling.

---

### Running Tests

```bash
python3 -m pytest tests/test_function_calling.py -v
```

44 test cases covering:
- `from_openai` / `from_anthropic` parsing
- `to_nail_annotated` annotation and immutability
- `filter_by_effects` sandbox policy enforcement
- `requires_any` capability checks
- `validate_effects` error handling
- Batch helpers
- Full sandbox scenario (read_file + send_email + pure_calc)
