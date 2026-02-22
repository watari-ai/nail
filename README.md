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
4. **Formal verification by default** — Code that cannot be proven correct does not compile.
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
└── AGENTS.md        — AI agent instructions for this repo
```

## Why NAIL?

See [PHILOSOPHY.md](./PHILOSOPHY.md) for the full reasoning.

---

*NAIL is built by AI, for AI. Humans define the intent. AI builds the machine.*
