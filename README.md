# NAIL — Native AI Language

[![CI](https://github.com/watari-ai/nail/actions/workflows/ci.yml/badge.svg)](https://github.com/watari-ai/nail/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/nail-lang)](https://pypi.org/project/nail-lang/)

> A programming language designed to be written by AI, not humans.

## What is NAIL?

NAIL is a programming language designed for AI agents to write, verify, and exchange — not for humans to read.

**Three things NAIL solves that no other language does:**

1. **Verifiable AI output** — L0/L1/L2/L3 checkers catch type errors, effect violations, and infinite loops *before* execution. AI-generated code that passes NAIL check is formally correct by construction.
2. **Cross-provider Function Calling** — `nail_lang.fc_standard` converts NAIL function definitions to OpenAI / Anthropic / Gemini schemas. Write once, deploy to any provider. (v0.8.0)
3. **Effect-safe tool routing** — Declare `"effects": ["NET"]` on a tool; NAIL enforces it. AI agents can't call a network tool from a pure sandbox.

Modern AI systems generate code and call tools at scale. NAIL gives that scale a formal foundation.

## Why NAIL? Three Core Guarantees

| | Guarantee | Example |
|---|---|---|
| **Zero Ambiguity** | The same spec generates identical code every time | RFC 8785-inspired canonical subset: `json.dumps(sort_keys=True, separators=(',',':'))` — one representation, always |
| **Effect System** | Side effects tracked at the type level | `fn main [] → fn helper [IO]` is a compile-time error, not a lint warning |
| **Verification Layers** | AI-written code passes 3 independent checks before running | L0 (schema) → L1 (types) → L2 (effects) — all enforced, no silent passes |

## Core Design Principles

1. **AI-first, human-second** — Written and maintained by AI. Human developers interact at the specification layer, not the code layer.
2. **Zero ambiguity** — One way to express every construct. No implicit behavior. No undefined behavior. Enforced by an RFC 8785-inspired canonical subset.
3. **Effects as types** — All side effects (IO, network, filesystem) are declared in function signatures and enforced by the type system.
4. **Verification layers (L0–L2)** — Every program passes schema, type, and effect checks before execution. No silent passes.
5. **Formal verification (v0.6+)** — `nail check --level 3` emits a termination certificate. Provably guaranteed to halt.
6. **Self-evolving** — The language specification itself is developed and improved by AI, with humans providing intent and constraints.

## FAQ: Is NAIL just a JSON AST?

Short answer: no — but it's a fair question.

Most languages use an AST as an *internal* representation. NAIL uses JSON as its **only** representation — there is no text syntax that compiles to it.

What makes NAIL different from "JSON-serialized AST":

**1. The verifier layers are the language.**
The JSON schema (L0), type checker (L1), and effect checker (L2) are not tools built *on top of* NAIL — they *are* NAIL. A program passing all three layers is formally correct by construction.
Layering is intentional: L0 is minimal by design, while L1/L2 enforce semantic correctness.

| Layer | Responsibility |
|---|---|
| **L0 (Schema)** | Minimum structural validity — accepts correctly shaped JSON programs |
| **L1 (Type Checker)** | Type correctness — catches int/string mismatches and undefined variables |
| **L2 (Effect Checker)** | Effect isolation — IO in pure functions is a compile-time error |

**2. Effects as first-class types.**
Every function declares its side effects (`io`, `net`, `fs`) in its signature. Calling an IO function from a pure context is a compile-time error — not a lint warning, not a runtime panic.

```json
{"nail":"0.2","kind":"module","defs":[
  {"id":"log_it","effects":["IO"],"params":[{"id":"x","type":{"type":"int","bits":64,"overflow":"panic"}}],"returns":{"type":"unit"},"body":[]},
  {"id":"pure_fn","effects":[],"params":[],"returns":{"type":"unit"},"body":[
    {"op":"call","fn":"log_it","args":[{"lit":1}]}
  ]}
]}
```

```
$ nail check above.nail
CheckError: call to 'log_it' requires effects [IO], but 'pure_fn' only has []
```

No runtime needed. The effect contract is violated at check time.

**3. Canonical form.**
There is exactly one valid JSON representation for any given program. No formatting choices, no style variants. An LLM generating the same logic twice will produce token-for-token identical output.

This is enforced by an RFC 8785-inspired canonical subset (sorted keys + compact separators; does not claim full RFC 8785 compliance): `nail canonicalize` normalizes any NAIL program to its canonical form, and `nail check --strict` rejects non-canonical input. Example files are stored in canonical form.

**4. Designed for LLM *generation*, not LLM *reading*.**
NAIL is not optimized for an LLM to read existing code. It is optimized for an LLM to write new code: zero ambiguity, zero implicit behavior, zero hallucination surface area.

The analogy: SQL is "just text for querying tables," but the relational model and declarative semantics are what make it SQL — not the text format.

## FAQ: Why JSON and not S-expressions (Lisp)?

Modern LLMs have JSON structured output modes built in (OpenAI, Anthropic, Google all provide `response_format: json`). JSON is the de facto interchange format of AI systems in 2026. Using S-expressions would make NAIL "typed Scheme with effects" — a 60-year-old idea without the novelty.

JSON-as-AST is the differentiator. The canonical form guarantee (`nail canonicalize`) is only possible because JSON has well-defined serialization semantics (NAIL uses an RFC 8785-inspired subset: sorted keys + compact separators). S-expressions have no such standard.

## Python API — Effect-Safe Tool Routing

NAIL's effect system can be used directly in Python to sandbox AI agent tool lists:

```python
from nail_lang import filter_by_effects

tools = [
    {"type": "function", "function": {"name": "read_file",  "effects": ["FS"]}},
    {"type": "function", "function": {"name": "http_get",   "effects": ["NET"]}},
    {"type": "function", "function": {"name": "exec_script","effects": ["PROC"]}},
    {"type": "function", "function": {"name": "log",        "effects": ["IO"]}},
]

# Restrict agent to read-only: no network, no process execution
safe_tools = filter_by_effects(tools, allowed=["FS", "IO"])
# → [read_file, log]

# Pass to LiteLLM, OpenAI, or any provider
response = litellm.completion(model="gpt-4o", tools=safe_tools, ...)
```

This is the NAIL effect system applied to Function Calling. Add `"effects": [...]` to your tool definitions; `filter_by_effects` handles the rest. Unannotated tools are excluded by default (production-safe).

See [`integrations/litellm.md`](integrations/litellm.md) for the full integration guide.

## FC Standard — Cross-Provider Function Calling

NAIL v0.8.0 introduces `nail_lang.fc_standard`: a unified converter between NAIL function definitions and OpenAI / Anthropic / Gemini Function Calling schemas.

```python
from nail_lang.fc_standard import convert_tools, to_openai_tool, to_anthropic_tool, to_gemini_tool

nail_fn = {
    "nail": "0.8",
    "kind": "fn",
    "id": "search_web",
    "effects": ["NET"],
    "params": [{"id": "query", "type": {"type": "string"}}],
    "returns": {"type": "string"},
    "description": "Search the web and return results"
}

openai_tool    = to_openai_tool(nail_fn)    # OpenAI tools format
anthropic_tool = to_anthropic_tool(nail_fn) # Anthropic tools format
gemini_tool    = to_gemini_tool(nail_fn)    # Gemini functionDeclarations format

# Round-trip guaranteed: NAIL → provider → NAIL preserves structure
```

Write once, deploy to any provider. Effect annotations are preserved across conversions.

See [`nail_lang/fc_standard.py`](nail_lang/fc_standard.py) and the [FC Standard section in SPEC.md](SPEC.md).

## Status

🧪 **Experimental — v0.8.0** — `pip install nail-lang`

| Feature | Status |
|---|---|
| Types: int/float/bool/string/option/list/map/unit | ✅ Implemented |
| Effect system (IO/FS/NET/TIME/RAND/MUT) | ✅ Implemented |
| RFC 8785-inspired canonical subset + `nail canonicalize` + `--strict` | ✅ Implemented |
| `kind: fn` + `kind: module` + function calls | ✅ Implemented |
| Mutable variables (`let mut` + `assign`) | ✅ Implemented |
| Bounded loops + if/else | ✅ Implemented |
| Recursion/cycle detection | ✅ Implemented |
| Return-path exhaustiveness check | ✅ Implemented |
| L0 JSON Schema + L1 Type + L2 Effect checks | ✅ Implemented |
| Overflow modes: `wrap` / `sat` / `panic` | ✅ Implemented (v0.3) |
| Result type (`ok`/`err`/`match_result`) | ✅ Implemented (v0.3) |
| Cross-module import + effect propagation | ✅ Implemented (v0.3) |
| **Type aliases** (module-level `types` dict, circular detection) | ✅ Implemented (v0.4) |
| **Fine-grained Effect capabilities** (path/op allow-lists) | ✅ Implemented (v0.4) |
| **Collection type operations** (`list_get/push/len`, `map_get`) | ✅ Implemented (v0.4) |
| `read_file` (FS) / `http_get` (NET) | ✅ Fully implemented (v0.4) |
| Enum / ADT (`enum_make` / `match_enum`) | ✅ Implemented (v0.5) |
| Core StdLib (`abs`/`clamp`/`min2`/`max2`/`str_len`) | ✅ Implemented (v0.5) |
| FC effect annotations (tool sandbox metadata) | ✅ Implemented (v0.5) |
| **L3 Termination Proofs** (`nail check --level 3`) | ✅ Implemented (v0.6) |
| **`nail check --format json`** (machine-parseable output) | ✅ Implemented (v0.7) |
| **Generics** (`type_params` + `{"type": "param", "name": "T"}`) | ✅ Implemented (v0.7) |
| **Python API** (`nail_lang.filter_by_effects`) | ✅ Implemented (v0.7) |
| **import `"from"` file resolution** | ✅ Implemented (v0.7) |
| Structured JSON errors (`to_json()` / error codes) | ✅ Implemented (v0.7) |
| **Generic type aliases** (module-level `type_params`) | ✅ Implemented (v0.7.2) |
| **FC Standard** (`nail_lang.fc_standard`) | ✅ Implemented (v0.8.0) |
| **Provider converters** (NAIL ↔ OpenAI / Anthropic / Gemini) | ✅ Implemented (v0.8.0) |
| **MCP Bridge** (`from_mcp` / `to_mcp` / `infer_effects`) | ✅ Implemented (v0.7) |
| Traits / Interfaces / Higher-kinded types | 🔮 Future |
| L4: Memory safety (buffer overflow proofs) | 🔮 Future |

## Secondary Effects: Token Efficiency

A byproduct of NAIL's minimal, unambiguous design is reduced token usage. In a Phase 2 validation experiment (2026-02-22), an LLM implemented the same 5 tasks in both Python and NAIL.

| Metric | NAIL | Python |
|---|---|---|
| Spec validation (L0–L2) | **5/5 (100%)** | N/A |
| Test pass rate | 18/21 (86%) | 21/21 (100%) |
| Avg tokens per function | **173** | 571 |
| Type annotations | Always required (compile error) | Optional |

NAIL used ~70% fewer tokens per function — a secondary benefit of the zero-ambiguity design, not its primary goal. All NAIL failures traced to spec gaps (not AI errors).

→ Full results: [`experiments/phase2/ANALYSIS.md`](./experiments/phase2/ANALYSIS.md)

## Structure

```
nail/
├── SPEC.md          — Language specification
├── PHILOSOPHY.md    — Design rationale and background
├── ROADMAP.md       — Development phases
├── CLI.md           — CLI command reference
├── examples/        — Sample NAIL programs
├── interpreter/     — Python interpreter (Checker + Runtime)
├── playground/      — Local FastAPI playground (server-based)
├── docs/            — GitHub Pages static playground (Pyodide/WASM)
└── AGENTS.md        — AI agent instructions for this repo
```

## Playground

### 🌐 Online

Try NAIL instantly in your browser — no installation required:

**[https://naillang.com](https://naillang.com)**

Powered by [Pyodide](https://pyodide.org) — the Python interpreter compiled to WebAssembly. The NAIL interpreter runs entirely client-side.

### 💻 Local (FastAPI)

```bash
cd playground
python server.py
# → open http://127.0.0.1:7429
```

Features: live JSON editor, 8 built-in examples, argument passing, dark theme.
See [`playground/README.md`](./playground/README.md) for details.

## Quick Start

**Browser — no install:**
→ [https://naillang.com](https://naillang.com)

**CLI:** `pip install nail-lang`

**Requirements:** Python 3.10+

**Clone & run:**
```bash
git clone https://github.com/watari-ai/nail.git
cd nail
pip install -r requirements.txt
./nail run examples/hello.nail
```

## Why NAIL?

See [PHILOSOPHY.md](./PHILOSOPHY.md) for the full reasoning.

---

→ **[CLI.md](./CLI.md)** — full command reference (`nail run`, `nail check`, `nail canonicalize`)

---

*NAIL is built by AI, for AI. Humans define the intent. AI builds the machine.*
