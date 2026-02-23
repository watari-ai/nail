# Show HN: NAIL – A programming language designed for AI to write, not humans to read

Every programming language in use today was designed around one assumption: humans read and write the code. Readable names, flexible syntax, implicit type coercions — all optimized for human cognition.

If AI is writing most of the code now, that assumption is dead weight.

NAIL is a programming language built for AI agents: structured JSON as the only representation, a three-layer verifier, and mandatory effect declarations. No text parser. No implicit conversions. No ambiguity.

**Core design:**

- **Zero ambiguity.** Every type, overflow behavior, and side effect is explicitly declared. Nothing for the AI to guess.
- **Effects as types.** IO, FS, NET must be declared in the function signature. Calling an IO function from a pure context is a compile-time error.
- **Three verification layers.** L0 (JSON schema), L1 (type checking), L2 (effect checking). Formal verification (L3+) is roadmapped.
- **Fewer tokens, same logic.** In our experiment: ~173 tokens/function in NAIL vs ~571 in Python — roughly 70% fewer.

**What we measured (Phase 2):**

Claude implemented 5 functions (is_even, abs_val, max_of_two, clamp, factorial) in both NAIL and Python.

| Metric | NAIL | Python |
|---|---|---|
| Spec validation (L0–L2) | 5/5 (100%) | N/A |
| Test pass rate | 18/21 (86%) | 21/21 (100%) |
| Avg tokens/function | **173** | **571** |

The one failure (factorial) revealed a spec gap, not a model error. That's the point — a strict language surfaces language design problems instead of silently producing wrong behavior.

**Try it now:** [https://naillang.com](https://naillang.com) (runs entirely in your browser via Pyodide)

Or clone and run locally:
```
pip install nail-lang
nail run examples/factorial.nail
```

MIT licensed. v0.1 is early. Feedback welcome.

GitHub: https://github.com/watari-ai/nail
