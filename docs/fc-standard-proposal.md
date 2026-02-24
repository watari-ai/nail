# Effect Annotations for AI Agent Function Calling: A Formal Safety Model

**NAIL Language Project — Standard Proposal**
*Version 1.0 | February 2026*

---

## Abstract

We propose a formal model for declaring side-effect contracts on AI agent function calls. The model, implemented in the NAIL language, enables static verification and runtime enforcement of which tools an agent is permitted to invoke in a given context. We describe the specification, demonstrate its practical value in sandboxing and safety guarantees, and propose a minimal JSON schema extension compatible with existing OpenAI, Anthropic, and major AI framework Function Calling specifications.

---

## 1. Problem Statement

AI agents using Function Calling (tool use) have no standardized mechanism to declare or verify which categories of side effects a tool invokes. This creates three practical problems:

**1.1 Unsafe sandbox escapes.** A sandboxed agent meant to read data can call a tool that writes to disk or makes network requests — the sandbox boundary isn't formally enforced.

**1.2 Effect escalation in orchestration.** When Agent A calls Agent B, there is no mechanism to verify that B's tool invocations remain within A's declared effect scope.

**1.3 Opaque error attribution.** When a multi-agent pipeline fails due to an unexpected effect (e.g., a network timeout), there is no schema-level way to know which tool caused the problem.

---

## 2. The NAIL Effect Model

NAIL (an AI-native programming language with JSON as its only syntax) implements a three-tier effect system as part of its function specification.

### 2.1 Effect Categories

Five canonical effects cover the vast majority of tool behaviors:

| Effect | Description | Example Tools |
|--------|-------------|---------------|
| `IO` | Console / user-facing output | print, log, display |
| `FS` | Filesystem read or write | read_file, write_file, list_dir |
| `NET` | Network access | http_get, fetch, api_call |
| `PROC` | Process / OS execution | shell, exec, run_command |
| `RAND` | Non-deterministic output | random, uuid, timestamp |

### 2.2 Effect Declaration

In NAIL IR, every function declares its complete effect contract:

```json
{
  "fn": "read_config",
  "params": [{"name": "path", "type": "str"}],
  "returns": "str",
  "effects": ["FS"],
  "body": [...]
}
```

A function with empty effects (`"effects": []`) is a pure function. The checker verifies that the declared effects are complete — calling a `["NET"]` function from a `["IO"]` context raises a `CheckError`.

### 2.3 Static Verification (L2)

The NAIL checker (at level 2, the default) statically verifies:

1. Every function call's required effects are a subset of the caller's declared effects
2. No function calls a function with undeclared effects without escalation

```
Function 'main' declares effects: ["IO"]
Function 'main' calls 'fetch_data' which requires: ["NET"]
→ CheckError: EFFECT_VIOLATION
  missing: ["NET"]
  declared: ["IO"]
```

### 2.4 Runtime Enforcement (L2)

The NAIL runtime independently enforces effects at execution time:

- `http_get` calls verify `NET` is in the active effect set
- File operations verify `FS` is active
- Violations raise `RuntimeError` with structured JSON output

### 2.5 Sandbox Composition with `filter_by_effects()`

The `filter_by_effects()` utility accepts a tool list and an allowed effect set, returning only the tools safe for a given context:

```python
all_tools = [read_file_tool, http_get_tool, write_db_tool, log_tool]
safe_for_read_sandbox = filter_by_effects(all_tools, allowed=["FS", "IO"])
# Returns: [read_file_tool, log_tool]
# Excludes: http_get_tool (NET), write_db_tool (FS+NET)
```

---

## 3. Proposed JSON Schema Extension

We propose adding an optional `effects` field to the OpenAI and Anthropic Function Calling / Tool Use schemas. The extension is backward-compatible: tools without an `effects` field are treated as having unrestricted effects (current behavior).

### 3.1 OpenAI Function Calling Extension

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file at the given path",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string"}
      },
      "required": ["path"]
    },
    "effects": ["FS"]
  }
}
```

### 3.2 Anthropic Tool Use Extension

```json
{
  "name": "http_get",
  "description": "Fetch content from a URL",
  "input_schema": {
    "type": "object",
    "properties": {
      "url": {"type": "string"}
    },
    "required": ["url"]
  },
  "effects": ["NET"]
}
```

### 3.3 Compound Effects

A tool that reads from the network and writes to the filesystem declares both:

```json
{
  "name": "download_file",
  "description": "Download a file from a URL to a local path",
  "effects": ["NET", "FS"]
}
```

---

## 4. Safety Patterns

### 4.1 Read-Only Sandbox

An agent operating in a read-only context (audit, verification) should only receive tools with `FS` read operations:

```python
audit_tools = filter_by_effects(all_tools, allowed=["IO"])
# No network, no write, no process execution
```

### 4.2 Effect-Scoped Orchestration

When Agent A (effects: `["IO", "FS"]`) delegates to Agent B, B's tool set should be filtered to match A's declared scope:

```python
agent_b_tools = filter_by_effects(
    all_tools,
    allowed=agent_a.declared_effects
)
```

### 4.3 Fail-Safe on Undeclared Effects

When a tool with no `effects` field is invoked, the caller can choose between:
- **Permissive** (current behavior): allow all effects
- **Restrictive** (recommended for production): treat as `["IO", "FS", "NET", "PROC", "RAND"]` and apply sandbox filtering

---

## 5. Combination with Termination Proofs (L3)

NAIL v0.6 adds L3 Termination Proof verification. Combined with effect annotations, this enables two guarantees simultaneously:

1. **Effect Safety**: The agent will only invoke tools within its declared effect scope.
2. **Termination Safety**: The agent's control flow is provably finite.

A function verified at L3 with effect annotations can produce a safety certificate:

```json
{
  "function": "process_batch",
  "effects": ["FS", "IO"],
  "termination": {
    "status": "proven",
    "evidence": [
      {"kind": "loop", "step": 1, "bound": "len(items)"},
      {"kind": "recursive", "measure": "depth"}
    ]
  }
}
```

This certificate enables agent orchestrators to make deployment decisions based on formally-verified properties rather than probabilistic assessments.

---

## 6. Implementation Reference

The NAIL reference implementation is open source:

- **Repository**: https://github.com/watari-ai/nail
- **PyPI**: `pip install nail-lang` (v0.6.0)
- **Playground**: https://naillang.com
- **Tests**: 421 tests, all passing

Relevant source files:
- `interpreter/checker.py` — static effect verification (L0-L3)
- `interpreter/runtime.py` — runtime effect enforcement
- `interpreter/types.py` — effect type definitions
- `interpreter/function_calling.py` — `filter_by_effects()` implementation

---

## 7. Request for Comment

We invite feedback on:

1. **Effect taxonomy**: Are five categories sufficient? Should `READ` and `WRITE` be split within `FS`?
2. **Schema placement**: Is the `effects` field best placed at the function level or as a top-level tool property?
3. **Default behavior**: Should tools without `effects` default to permissive or restrictive?
4. **Composition rules**: How should compound effects behave in sub-agent delegation?

---

## Appendix: Effect Taxonomy Detail

| Effect | Read | Write | Examples |
|--------|------|-------|---------|
| `IO` | stdout | stdin | print, input, log, display |
| `FS` | read_file, list_dir | write_file, delete_file | file ops |
| `NET` | http_get, fetch | http_post, websocket_send | network |
| `PROC` | — | exec, shell, kill | process control |
| `RAND` | random, uuid, time.now | — | non-determinism |

*Note: `FS` covers both read and write; future versions may split into `FS_READ` and `FS_WRITE` for finer-grained sandboxing.*
