# NAIL — Design Philosophy

NAIL is a type-safe, effect-constrained execution format designed for AI agents — not for humans to write.

## Why Build This Language

### The Arrival of the AI Coding Era

Programming languages have historically been designed around the assumption that humans write and read code.

- `if x == True:` is less readable than `if x:` (Python philosophy)
- Variable names like `index` are clearer than `i` (readability-first)
- The same logic can be expressed in multiple styles (flexibility-first)

These choices optimize for lowering human cognitive load.

But in an era where AI writes code, that assumption breaks.

For AI, "readable variable names" are not the key optimization. For AI, "flexible syntax" is a source of inference cost. For AI, "implicit behavior" is a breeding ground for bugs.

### Ambiguity Is the Core Problem

What AI struggles with in modern languages is not "difficulty." It is **ambiguity**.

```javascript
// JavaScript's == performs implicit coercion
0 == false   // true
"" == false  // true
null == undefined // true
```

```python
# Python types are not fixed until runtime
def add(a, b):
    return a + b  # you cannot know the concrete types of a, b until execution
```

```c
// Undefined behavior in C
int arr[5];
arr[10] = 1;  // outcome depends on implementation
```

By packing in omission, implicitness, and flexibility for human convenience, we increase the inference burden for AI.

NAIL removes that burden. Everything is explicit. Everything is unambiguous. Everything is verifiable.

### Context Efficiency: A Secondary Benefit

One byproduct of NAIL's zero-ambiguity design is reduced token usage. When expressing identical logic, NAIL programs often require significantly fewer tokens than equivalent Python. This is a natural consequence of removing syntactic sugar, formatting flexibility, and implicit conventions.

But token efficiency is a **side effect, not a goal**. The primary goal is verifiability: code that can be formally checked before running. Token savings follow automatically from the same design decisions.

This matters in large-scale AI systems where context windows are finite — but it is not NAIL's reason for existing.

### Directory Structure as "Another Language"

Code is not the only language. Project layout, metadata format, and document structure are also information that AI reads and must be intentionally designed.

There is no current standard for writing `AGENTS.md`. There is no standard structure for `SPEC.md`. There is no standard for what belongs in README.

NAIL defines not only a programming language, but also a **structure standard that lets AI understand projects with minimal context**.

### AI Evolves Languages for AI

The NAIL spec is not fixed. AI uses it, generates feedback, proposes improvements, and updates the spec.

If this feedback loop matures, NAIL may evolve beyond "a language that is easy for AI to write" into "the most efficient representation for AI reasoning."

---

## What NAIL Is (and Is Not)

### What NAIL Is

- A **type-safe execution format** for AI agents: AI generates NAIL, NAIL runs with formal guarantees
- A **verification layer**: L0 (schema), L1 (types), L2 (effects) before any execution
- An **effect sandbox**: every side effect is declared in the function signature and enforced
- A **reproducibility guarantee**: canonical form ensures identical semantics produce identical JSON

### What NAIL Is NOT

- A language for humans to write (no text syntax, no IDE support planned)
- A general-purpose IR for all programs
- A replacement for Python, Rust, or any human language
- An experimental DSL — NAIL programs actually execute with formal safety guarantees

## Position in the AI Stack

NAIL sits at the execution layer of AI agent pipelines.

This is the "Secure Plugin Format" for AI agents: any LLM can generate NAIL, any NAIL-compatible runtime can execute it safely.

---

## The FC Standard: Interoperability as a Language Feature

As of v0.8.0, NAIL introduces a new dimension: **cross-provider interoperability**.

Modern AI agents call tools. Those tools are defined differently for OpenAI, Anthropic, and Gemini. Every team must maintain three schema definitions for the same function — a fragmentation problem.

NAIL's FC Standard (`nail_lang.fc_standard`) solves this at the language level: a NAIL function definition is the canonical source of truth, and `to_openai_tool`, `to_anthropic_tool`, `to_gemini_tool` convert it to any provider format. Round-trips preserve structure.

This is interoperability as a language feature — not a conversion utility bolted on, but a consequence of NAIL's formal, unambiguous function definition format.

## Summary

NAIL pursues three goals:

1. **Zero Ambiguity** — One way to express every construct. No implicit behavior. Enforced by JCS canonical form.
2. **Formal Safety** — Code that cannot be proven correct should not run. L0–L3 verification before execution.
3. **Interoperability** — FC Standard enables NAIL function definitions to convert losslessly between OpenAI, Anthropic, and Gemini schemas. Write once, deploy to any provider.

Not beauty for humans, but precision for machines.
