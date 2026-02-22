# NAIL — Native AI Language

> A programming language designed to be written by AI, not humans.

## What is NAIL?

NAIL is an experimental programming language built on a simple premise:

**In the age of AI-driven development, human readability is an unnecessary constraint.**

Modern programming languages carry decades of design decisions optimized for human cognition — syntax sugar, implicit conversions, flexible formatting, multiple ways to express the same thing. These features reduce cognitive load for human developers, but they introduce ambiguity, hidden behavior, and inference overhead for AI systems.

NAIL removes that weight entirely.

## Core Design Principles

1. **AI-first, human-second** — Written and maintained by AI. Human developers interact at the specification layer, not the code layer.
2. **Zero ambiguity** — One way to express every construct. No implicit behavior. No undefined behavior.
3. **Effects as types** — All side effects (IO, network, filesystem) are declared in function signatures and enforced by the type system.
4. **Formal verification (v0.2+)** — v0.1 focuses on correct L0–L2 implementation. Full formal verification (termination proof, etc.) is a v0.2+ milestone.
5. **Minimal context** — The same logic expressed in fewer tokens than equivalent Python or JavaScript. AI inference is cheaper.
6. **Self-evolving** — The language specification itself is developed and improved by AI, with humans providing intent and constraints.

## Status

🧪 **Experimental — v0.1 draft**

This project is in early design phase. The specification is a living document.

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

### 🌐 Online (GitHub Pages)

Try NAIL instantly in your browser — no installation required:

**[https://watari-ai.github.io/nail/](https://watari-ai.github.io/nail/)**

Powered by [Pyodide](https://pyodide.org) — the Python interpreter compiled to WebAssembly. The NAIL interpreter runs entirely client-side.

#### Enable GitHub Pages (repo admins)

1. Go to **Settings → Pages** in the `watari-ai/nail` repository
2. Under **Source**, select **Deploy from a branch**
3. Set **Branch** to `main` and **Folder** to `/docs`
4. Click **Save** — the site will be live at `https://watari-ai.github.io/nail/` within a minute

### 💻 Local (FastAPI)

```bash
cd playground
python server.py
# → open http://127.0.0.1:7429
```

Features: live JSON editor, 6 built-in examples, argument passing, dark theme.
See [`playground/README.md`](./playground/README.md) for details.

## Why NAIL?

See [PHILOSOPHY.md](./PHILOSOPHY.md) for the full reasoning.

---

*NAIL is built by AI, for AI. Humans define the intent. AI builds the machine.*
