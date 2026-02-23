# Show HN: NAIL – A programming language designed for AI to write, not humans to read

Every programming language in use today was designed around one assumption: humans read and write the code. Readable names, flexible syntax, implicit type coercions — all optimized for human cognition.

As AI systems take on more of the implementation work, that assumption deserves re-examination.

NAIL is an experiment: what would a programming language look like if you optimized it for AI generation instead of human readability? The answer is structured JSON as the only representation, mandatory effect declarations, and a three-layer verifier. No text parser. No implicit conversions. No ambiguity.

**Core design:**

- **Zero ambiguity.** Every type, overflow behavior, and side effect is explicitly declared. Nothing for the AI to infer.
- **Effects as types.** IO, FS, NET must be declared in the function signature. Calling an IO function from a pure context is a compile-time error — not a lint warning.
- **Three verification layers.** L0 (JSON schema), L1 (type checking), L2 (effect checking). Formal verification (L3+) is on the roadmap.
- **Fewer tokens per function.** In a small initial experiment: ~173 tokens/function in NAIL vs ~571 in equivalent Python (Claude Sonnet 4.5, same prompt).

**What we measured (Phase 2 — small sample, 5 functions):**

We had Claude Sonnet 4.5 implement 5 functions (is_even, abs_val, max_of_two, clamp, factorial) in both NAIL and Python from the same spec. Results:

| Metric | NAIL | Python |
|---|---|---|
| Spec validation (L0–L2) | 5/5 (100%) | N/A* |
| Test pass rate | 18/21 (86%) | 21/21 (100%) |
| Avg tokens/function | **173** | **571** |

*Python has type checkers (mypy, etc.) but they serve a different purpose than L0–L2 structural verification — comparing them directly would be apples-to-oranges.

The one failure (factorial) revealed that mutable variable semantics were undefined in NAIL v0.1 — a spec gap, not a model error. The strict verifier surfaced a language design problem that would have silently produced wrong behavior in a more permissive language.

Full experiment details and reproduction steps: [experiments/phase2/](https://github.com/watari-ai/nail/tree/main/experiments/phase2)

**Try it now:** [https://naillang.com](https://naillang.com) — runs entirely in your browser via Pyodide, no install needed.

Or locally (Python 3.10+):
```
git clone https://github.com/watari-ai/nail
cd nail
pip install -r requirements.txt
python nail_cli.py run examples/factorial.nail
```

MIT licensed. v0.1 is early — interpreter works, spec is being refined. Honest feedback welcome (especially if you've built something similar or see a flaw in the approach).

GitHub: https://github.com/watari-ai/nail
