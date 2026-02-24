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

### Context Efficiency as a New Metric

NAIL's defining trait is adding AI operating cost (context-window usage) as a first-class language design metric.

When expressing identical logic:
- If a Python file takes 100 lines,
- A NAIL structure may fit in 30 tokens.

Fewer tokens = more logic visible in one context = better consistency across larger systems.

This may look "hard to read" for humans. But humans are not the primary readers of NAIL. AI reads NAIL, and AI writes NAIL.

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

## Summary

NAIL pursues three goals:

1. **Zero Ambiguity** — minimize AI inference cost
2. **Formal Safety** — code that cannot be proven should not exist
3. **Context Efficiency** — represent more logic with fewer tokens

Not beauty for humans, but precision for machines.
