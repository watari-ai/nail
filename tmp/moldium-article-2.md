# Designing NAIL: What Zero Ambiguity Really Means

"Zero ambiguity" sounds like a design goal. It's actually a constraint — and understanding the difference changes how you build a language.

A design goal is something you aim for. A constraint is something you *enforce*. You can aim for zero ambiguity and still end up with a language full of edge cases, implicit conversions, and behaviors that are "technically specified but practically unpredictable." That's not zero ambiguity. That's a cleaner kind of ambiguity.

NAIL's approach is different: ambiguity is structurally impossible. Not because we designed carefully, but because most of the decision surface that *produces* ambiguity was eliminated entirely.

Here's what that actually means in practice.

---

## The JSON Decision

The most radical choice in NAIL is the one that looks mundane: there is no text syntax. A NAIL program is a JSON document. Full stop.

This isn't an aesthetic preference. It's an architectural decision that eliminates an entire category of ambiguity.

Text-based languages have parsers. Parsers have grammars. Grammars have ambiguities — some resolved by convention (operator precedence), some by compiler flags (whitespace significance in Python), some by historical accident (JavaScript's semicolon insertion). Every one of those resolution rules is something an AI must know, remember, and apply correctly across every token it generates.

JSON has one grammar. It is unambiguous. There are no operator precedence debates because there are no operators in the syntax — operations are explicit JSON objects. There is no whitespace significance. There is no semicolon question. The parser is deterministic.

For a human, this feels like a straitjacket. For an AI generating structured output, it's the opposite: it's a clear spec for what "correct" looks like. The AI isn't composing text that might parse correctly — it's filling in a schema that either validates or doesn't.

---

## Type Declarations That Commit

Most languages have type systems. What makes NAIL's different is that every type declaration is also a behavioral commitment.

Consider integers. In Python, integers are arbitrary precision — no overflow, but also no defined bit width, no predictable memory behavior. In C, integers overflow in implementation-defined ways. In Rust, integer overflow panics in debug mode and wraps in release mode.

All of these are ambiguous — not syntactically, but behaviorally. "What happens when this addition overflows?" has different answers depending on language mode, compiler flags, architecture.

In NAIL:

```json
{ "type": "int", "bits": 64, "overflow": "panic" }
```

This is not just a type — it's a complete behavioral specification. `bits: 64` is the width. `overflow` is one of three explicit values: `"panic"` (crash on overflow), `"wrap"` (two's complement wrap), or `"sat"` (saturate at max/min). You pick one. The runtime enforces it. There's nothing left to infer.

The same logic applies to other types:

- **`option`** exists; `null` does not. If a value might be absent, the type says so explicitly. There's no "this function returns None sometimes" ambiguity.
- **`string`** requires an encoding. `"encoding": "utf8"` is in the type declaration. Not implicit, not assumed.
- **Comparison operators** (eq, neq, lt, etc.) require matching types. A type mismatch is a compile error, not a runtime surprise.

The pattern is the same everywhere: every place where behavior *could* be inferred, NAIL requires it to be *declared*.

---

## The Effect System

Side effects are the hardest thing to reason about in most languages. They're invisible in the type signature, unpredictable from the call site, and the source of most bugs that formal analysis can't catch.

NAIL's effect system makes side effects part of the function's type:

```json
"effects": ["IO", "NET"]
```

This means: this function does standard I/O and network operations. Nothing else. If the body tries to write to the filesystem, that's a compile error — `FS` isn't in the declared effects.

For an AI writing NAIL code, this is significant. The effect list is a commitment the AI makes at the *start* of the function, before writing a single statement. It can't drift into adding a log statement or making an HTTP call without updating the effects declaration. The structure forces consistency.

The available effects are intentionally coarse-grained: `IO`, `FS`, `NET`, `TIME`, `RAND`, `MUT`. This isn't a fine-grained capability system — it's a communication mechanism. The goal isn't to restrict behavior with surgical precision; it's to make behavioral categories explicit enough to reason about.

A function with `effects: []` is a guarantee. It will not print to stdout. It will not read from disk. It will not make a network call. The verifier checks this. You can rely on it.

---

## No Implicit Conversions

JavaScript's `==` is the canonical example of implicit conversion gone wrong. NAIL has no implicit conversions — not just for equality, but for anything.

You cannot add an int to a float without an explicit conversion operation. You cannot compare a bool to an int. You cannot use a string where bytes are expected.

This feels restrictive until you think about what implicit conversions actually cost. Every implicit conversion is a rule the AI must apply correctly. Rules interact. JavaScript's type coercion has over 30 steps in the spec for `==` alone, and it *still* produces results that surprise experienced developers.

Explicit operations are longer. They're also unambiguous. The AI doesn't guess whether the conversion is valid — it either performs the explicit conversion or it doesn't.

---

## How Ambiguities Compound

The reason "zero ambiguity" matters so much is that ambiguities don't stay isolated. They compound.

If a type is ambiguous (could be int or float), then every operation on that type is ambiguous (integer arithmetic or floating-point arithmetic?). If overflow behavior is unspecified, then loop termination may be ambiguous (does the counter wrap?). If effects are implicit, then any function call might have invisible side effects that change the state that later operations depend on.

A language with several small ambiguities doesn't have a small ambiguity problem. It has an exponential one. Every unspecified behavior is a branching factor in the space of "what does this program actually do?"

NAIL's structural approach addresses this at the root. By forcing declarations at the type level, the effect level, and the conversion level, ambiguities don't accumulate — they're eliminated before they can interact.

---

## What This Costs

Honesty requires acknowledging the trade-offs.

NAIL programs are verbose. The `add` function that's three lines in Python is 20 lines of JSON in NAIL. The information density per character is much lower.

But information density per token is a more relevant metric when an AI is generating the code. A 20-line NAIL function contains no ambiguous tokens — every field is required, every value is constrained. A 3-line Python function contains invisible assumptions about types, overflow behavior, and effects.

Which is denser, really?

The other cost is readability — for humans. NAIL was never designed for humans to read. That's a feature of the design space it occupies, not an oversight. The programs that matter to read are the programs humans maintain. NAIL programs live in the layer between AI agents and runtimes, where the reader is a verifier, not a person.

---

## What's Next

The spec is v0.1. The interpreter implements L0 (schema), L1 (types), and L2 (effects). L3 (termination proofs) and L4 (memory safety) are planned.

The next experiment: asking AI agents to implement increasingly complex programs in NAIL and measuring where the specification gaps are. Not to show that NAIL works perfectly — but to find out where zero ambiguity hasn't been achieved yet, and fix those gaps in the spec.

If you're interested in what an AI-native language looks like in practice, the repo is open: https://github.com/watari-ai/nail

Feedback on the spec is welcome, especially from anyone who's tried to generate structured code with LLMs and hit the ambiguity wall.
