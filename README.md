# NAIL — Native AI Language

[![CI](https://github.com/watari-ai/nail/actions/workflows/ci.yml/badge.svg)](https://github.com/watari-ai/nail/actions/workflows/ci.yml)

> A programming language designed to be written by AI, not humans.

## What is NAIL?

NAIL is an experimental programming language built on a simple premise:

**In the age of AI-driven development, human readability is an unnecessary constraint.**

Modern programming languages carry decades of design decisions optimized for human cognition — syntax sugar, implicit conversions, flexible formatting, multiple ways to express the same thing. These features reduce cognitive load for human developers, but they introduce ambiguity, hidden behavior, and inference overhead for AI systems.

NAIL removes that weight entirely.

## Why NAIL? Three Core Guarantees

| | Guarantee | Example |
|---|---|---|
| **Zero Ambiguity** | The same spec generates identical code every time | JCS canonical form: `json.dumps(sort_keys=True, separators=(',',':'))` — one representation, always |
| **Effect System** | Side effects tracked at the type level | `fn main [] → fn helper [IO]` is a compile-time error, not a lint warning |
| **Verification Layers** | AI-written code passes 3 independent checks before running | L0 (schema) → L1 (types) → L2 (effects) — all enforced, no silent passes |

## Core Design Principles

1. **AI-first, human-second** — Written and maintained by AI. Human developers interact at the specification layer, not the code layer.
2. **Zero ambiguity** — One way to express every construct. No implicit behavior. No undefined behavior. Enforced by JCS canonical form.
3. **Effects as types** — All side effects (IO, network, filesystem) are declared in function signatures and enforced by the type system.
4. **Verification layers (L0–L2)** — Every program passes schema, type, and effect checks before execution. No silent passes.
5. **Formal verification (v0.3+)** — Full termination proofs and formal verification are a future milestone.
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
{"nail":"0.2","kind":"module","fns":[
  {"id":"log_it","effects":["IO"],"params":[{"id":"x","type":{"type":"int","bits":64,"overflow":"panic"}}],"returns":{"type":"unit"},"body":[]},
  {"id":"pure_fn","effects":[],"params":[],"returns":{"type":"unit"},"body":[
    {"op":"call","fn":"log_it","args":[{"id":"x","val":{"lit":1}}]}
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

This is enforced by the JCS (JSON Canonicalization Scheme, RFC 8785) implementation: `nail canonicalize` normalizes any NAIL program to its canonical form, and `nail check --strict` rejects non-canonical input. Example files are stored in canonical form.

**4. Designed for LLM *generation*, not LLM *reading*.**
NAIL is not optimized for an LLM to read existing code. It is optimized for an LLM to write new code: zero ambiguity, zero implicit behavior, zero hallucination surface area.

The analogy: SQL is "just text for querying tables," but the relational model and declarative semantics are what make it SQL — not the text format.

## FAQ: Why JSON and not S-expressions (Lisp)?

Modern LLMs have JSON structured output modes built in (OpenAI, Anthropic, Google all provide `response_format: json`). JSON is the de facto interchange format of AI systems in 2026. Using S-expressions would make NAIL "typed Scheme with effects" — a 60-year-old idea without the novelty.

JSON-as-AST is the differentiator. The canonical form guarantee (`nail canonicalize`) is only possible because JSON has well-defined serialization semantics (RFC 8785 / JCS). S-expressions have no such standard.

## Status

🧪 **Experimental — v0.2**

Core language (types, effects, modules, canonical form) is implemented and tested. The specification is stable but evolving.

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

**CLI (coming soon):** PyPI package is in progress.

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

*NAIL is built by AI, for AI. Humans define the intent. AI builds the machine.*
