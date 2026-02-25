# IDEAS.md — NAIL Idea Board

Not a TODO list. A place to capture interesting ideas, half-formed thoughts, and long-term possibilities.

---

## Compiler / Transpiler

### Python Subset → NAIL Transpiler ✅ Implemented in v0.4
- Convert AI-written Python to NAIL and run it through type + effect verification
- Practical utility combined with strong demo appeal
- A natural follow-up topic for the HN post
- Surfaced in conversation with Boss (2026-02-23)
- **Status: Implemented in v0.4** (`transpiler/python_to_nail.py`). AST-based conversion with auto-effect inference.

### Lisp/Scheme → NAIL
- S-expressions and JSON are nearly the same structure → conversion is natural
- Probably the easiest transpiler to write
- Academic / experimental direction

### NAIL → WebAssembly Compiler
- NAIL's strict type system pairs perfectly with Wasm
- The dream: an AI agent runtime that runs in the browser
- Would complete the "AI writes it, browser runs it" demo story

### Prolog → NAIL
- Logic programming × effect system
- An unusual combination; leans academic

---

## NAIL as an Intermediate Representation

```
Human-written language
    ↓ (transpiler)
NAIL JSON  ← type checking + effect verification happens here
    ↓ (compiler)
Execution (native / Wasm / Python)
```

- NAIL isn't just "the language AI writes" — it can become a safe execution substrate for any language
- Just as LLVM IR accepts C, Rust, and more, NAIL could have front-ends for multiple languages

---

## Ecosystem / Tooling

### Language Server Protocol (LSP) Support
- Even though NAIL targets AI, humans still need to read and debug it
- Error message visualization, type inference result display

### NAIL Package Manager
- Distribution and dependency resolution for NAIL modules
- An extension of the "OSS for AI" vision — where AI agents grow the language through issues, PRs, and forks
- **Status: Still future** (needs a user base first)

### NAIL Linter / Formatter
- Beyond JSON formatting — validate NAIL-specific best practices

---

## Interesting Application Areas

### NAIL as an Inter-Agent Communication Protocol
- Use NAIL as the format for agent A to send a "task request" to agent B
- More type-safe and effect-traceable than current JSON-RPC

### Describing OS System Calls in NAIL
- Effect declarations are enforced, which makes for interesting security properties
- "Which effects does this program have, and which process is allowed to run it?" — controlled at the code level

---

## Implemented (no longer ideas)

- **Python → NAIL Transpiler** — Implemented in v0.4 (`transpiler/python_to_nail.py`). AST-based conversion with auto-effect inference.
- **Function Calling Effect Annotations** — Implemented in v0.5. `filter_by_effects()` API.
- **FC Standard (Cross-provider converters)** — Implemented in v0.8.0 (`nail_lang.fc_standard`). NAIL ↔ OpenAI/Anthropic/Gemini.
- **MCP Bridge** — Implemented in v0.7 (`from_mcp`, `to_mcp`, `infer_effects`).

## New Ideas (post-v0.8.0)

### AI Agent Orchestration via NAIL
- Use NAIL as the typed message format between orchestrator and sub-agents
- Orchestrator writes a NAIL module defining delegated tasks with effect constraints
- Sub-agents can only use effects declared in their task definition
- Formal audit trail: every inter-agent call is a NAIL-checked operation

### NAIL as a Compliance Layer
- Enterprise use case: "Prove this AI-generated function never touches the database"
- Convert AI-generated code in any language → NAIL IR → run L0-L3 verification
- Compliance-ready: formal verification output for regulated industries

### Encoding Optimization Experiment
- Current JSON encoding was designed by humans. Has it actually been optimized for AI?
- Inspired by Codex "pair token" discovery: representation shapes required compute
- Task: give an AI agent: "Design the most efficient NAIL encoding that minimizes LLM token cost while maintaining Zero Ambiguity"
- Measure: token count per operation, generation reproducibility, checker pass rate

---

*Add new ideas as they surface*
