# NAIL Effect Annotations for LLM Function Calling

> Proposal: Applying NAIL's Effect System to OpenAI/Anthropic Function Calling schemas  
> Author: NAIL Core Team (via Opus analysis — 2026-02-24)  
> Status: In Progress

---

## Problem

Modern LLM frameworks (OpenAI, Anthropic) define tools/functions for AI agents using JSON schemas. These schemas describe parameter types and descriptions precisely — but they say **nothing about side effects**.

### Current OpenAI Function Calling Schema

```json
{
  "name": "send_email",
  "description": "Send an email to a recipient",
  "parameters": {
    "type": "object",
    "properties": {
      "to": { "type": "string" },
      "subject": { "type": "string" },
      "body": { "type": "string" }
    },
    "required": ["to", "subject", "body"]
  }
}
```

### Current Anthropic Tool Definition

```json
{
  "name": "read_file",
  "description": "Read contents of a file from disk",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": { "type": "string", "description": "File path to read" }
    },
    "required": ["path"]
  }
}
```

**The gap:** Neither schema answers the question: *What does this function actually do to the world?*

- Does `send_email` touch the network?
- Does `read_file` access the filesystem?
- Is `calculate_bmi` safe to run in a sandboxed environment?

Without this information, a runtime enforcing safety policies must either:
1. Hardcode per-tool rules (brittle, doesn't scale), or
2. Run every tool with full permissions (unsafe), or
3. Ask the AI to reason about side effects at runtime (unreliable).

---

## Proposal: Add a NAIL `effects` Field

Extend Function Calling schemas with an `effects` field, using NAIL's effect system vocabulary.

### NAIL Effect System (from `SPEC.md`)

```
[]          — Pure function, zero side effects
["IO"]      — Standard I/O (stdin/stdout)
["FS"]      — Filesystem access (read or write)
["NET"]     — Network access (HTTP, DNS, sockets)
["TIME"]    — Current time access
["RAND"]    — Random number generation
["MUT"]     — Mutable global state
```

Multiple effects compose: `["NET", "IO"]`, `["FS", "MUT"]`, etc.

---

## Extended Schemas: Before & After

### `send_email` — Network + I/O

**Before (no effect information):**
```json
{
  "name": "send_email",
  "description": "Send an email to a recipient",
  "parameters": {
    "type": "object",
    "properties": {
      "to":      { "type": "string" },
      "subject": { "type": "string" },
      "body":    { "type": "string" }
    },
    "required": ["to", "subject", "body"]
  }
}
```

**After (with NAIL effect annotations):**
```json
{
  "name": "send_email",
  "description": "Send an email to a recipient",
  "effects": ["NET", "IO"],
  "parameters": {
    "type": "object",
    "properties": {
      "to":      { "type": "string" },
      "subject": { "type": "string" },
      "body":    { "type": "string" }
    },
    "required": ["to", "subject", "body"]
  }
}
```

---

### `read_file` — Filesystem access only

```json
{
  "name": "read_file",
  "description": "Read contents of a file from disk",
  "effects": ["FS"],
  "parameters": {
    "type": "object",
    "properties": {
      "path": { "type": "string", "description": "File path to read" }
    },
    "required": ["path"]
  }
}
```

---

### `pure_calc` — No side effects

```json
{
  "name": "pure_calc",
  "description": "Compute the result of a mathematical expression",
  "effects": [],
  "parameters": {
    "type": "object",
    "properties": {
      "expression": { "type": "string", "description": "Math expression, e.g. '2 + 3 * 4'" }
    },
    "required": ["expression"]
  }
}
```

The presence of `"effects": []` is an explicit declaration: *this function is pure*. It is a promise the tool author makes to the runtime.

---

## Use Cases

### 1. Sandbox Mode Enforcement

A runtime operating in sandbox mode can inspect the `effects` field before executing any tool:

```
Policy: sandbox_mode = true → deny execution of tools with "NET" in effects

Tool: send_email → effects: ["NET", "IO"] → ❌ BLOCKED
Tool: read_file  → effects: ["FS"]        → ✅ ALLOWED (if FS is permitted)
Tool: pure_calc  → effects: []            → ✅ ALLOWED (always safe)
```

This enforcement is **declarative** — no regex matching on tool names, no AI inference about whether a function "sounds dangerous." The schema carries the ground truth.

### 2. Principle of Least Privilege

An orchestrator spawning a sub-agent for a restricted task can filter the tool list to only those whose declared effects are within the task's allowed effect set:

```
Task: "Summarize this document" → allowed_effects: ["FS"]
Available tools: [read_file(FS), send_email(NET,IO), pure_calc([])]

Filtered tool list exposed to agent:
  → read_file  ✅
  → pure_calc  ✅
  → send_email ❌ (NET not in allowed_effects)
```

The agent cannot send emails — not because of a system prompt instruction that could be overridden, but because the tool simply isn't present.

### 3. Audit Logging by Effect Category

Logging infrastructure can tag log entries by effect type, enabling queries like:
- "Show all NET-effect tool calls in the last 24 hours"
- "Did this agent's run touch the filesystem?"

### 4. AI Safety: Formal Action Constraints

In multi-agent systems, Agent A can delegate to Agent B with formal effect constraints:

```json
{
  "delegate_to": "agent_b",
  "task": "Analyze the uploaded report",
  "allowed_effects": ["FS"]
}
```

Agent B's runtime enforces this constraint at the tool level. If Agent B tries to call a NET-effect tool, the runtime rejects it — regardless of what the AI model "wants" to do.

---

## Compatibility with NAIL Effect System

This proposal is a **direct projection** of NAIL's effect system (`SPEC.md §3`) onto the Function Calling domain.

| NAIL function declaration | Function Calling schema |
|---|---|
| `"effects": []` | `"effects": []` |
| `"effects": ["NET"]` | `"effects": ["NET"]` |
| `"effects": ["FS", "IO"]` | `"effects": ["FS", "IO"]` |

NAIL's L2 verification (effect consistency) can be extended to validate tool schemas:
- Declared `effects` must be consistent with the actual implementation
- If the tool implementation is NAIL code, L2 can verify this automatically

For tool implementations in other languages, `effects` is a **trusted declaration** — verified by convention or static analysis tooling, not by the NAIL verifier itself.

### Relationship to `effects_allowed` in NAIL Project Spec

NAIL's `SPEC.md §12` defines `effects_allowed` in project-level metadata:

```yaml
effects_allowed: [IO, FS, NET]
```

A NAIL project's `effects_allowed` maps naturally to the set of tool effect categories permitted for an agent running within that project's sandbox. The same vocabulary enables end-to-end effect tracking: from language-level function declarations through module definitions to agent tool schemas.

---

## Implementation Path

1. **Schema extension** (immediate): Define `effects` as an optional array field in tool/function schemas. Backward compatible — tools without `effects` are treated as `["*"]` (unknown/unrestricted) by default.

2. **Runtime policy engine** (near-term): Build an `EffectPolicy` layer in agent orchestrators that filters or blocks tools based on declared effects and runtime policy configuration.

3. **NAIL tool definitions** (near-term): For tools implemented as NAIL functions, the `effects` field in the JSON schema is auto-derived from the NAIL function's `effects` declaration — no manual annotation needed.

4. **Verification** (long-term): Static analysis that cross-checks declared `effects` against tool implementation source code, flagging mismatches.

---

## Summary

The `effects` field is a single addition to existing Function Calling schemas that enables:

- **Declarative sandbox enforcement** — no runtime guessing
- **Principle of least privilege** — tools filtered by effect capability
- **Formal AI safety constraints** — effect-bounded agent delegation
- **Audit trails** — log entries tagged by effect category

It reuses NAIL's existing effect vocabulary (`IO`, `FS`, `NET`, `TIME`, `RAND`, `MUT`) with no new concepts introduced. The extension is backward compatible and can be adopted incrementally.

> "Don't tell the AI what it's allowed to do. Declare what the tool is capable of, and let the runtime decide."
