# Show HN: NAIL – A programming language designed for AI to write, not humans to read

Every programming language in use today was designed around one assumption: humans read and write the code. Readable variable names, flexible syntax, implicit type coercions — all optimized for human cognition.

But if AI is writing most of the code now, that assumption is dead weight. "Readable" syntax costs tokens. Flexible grammar creates ambiguity. Implicit behavior breeds bugs that even GPT-4 can't reliably avoid.

NAIL is a programming language built from scratch for AI agents. The entire representation is structured JSON — no text syntax, no parser ambiguity, no implicit conversions. A NAIL program is a JSON document that a verifier checks and a runtime executes.

**What makes it different:**

- **Zero ambiguity.** Every type, every effect, every overflow behavior is explicitly declared. There's nothing for the AI to guess about.
- **Mandatory effect system.** Side effects (IO, FS, NET, etc.) must be declared in the function signature. Undeclared effects are compile errors.
- **Formal verification built in.** L0 (JSON schema), L1 (type checking), L2 (effect checking) are implemented. L3 (termination proofs) and L4 (memory safety) are planned.
- **Context-efficient.** The same logic that takes 100 lines of Python can be expressed more compactly in structured NAIL. More logic fits in one context window.

**Phase 2 experiment results:** We had Claude and GPT-4o implement 5 functions (is_even, abs_val, max_of_two, clamp, factorial) in both NAIL and Python. NAIL results: 5/5 passed spec verification — the structured format made it structurally impossible to produce type errors or ambiguous code. The one NAIL failure (factorial) revealed a spec gap, not a model error — which is exactly what a strict language should do.

**Try it in your browser:** https://naillang.com

NAIL isn't meant to replace Python for humans. It's meant to be the language AI agents use when talking to each other and to runtimes — where precision matters more than readability.

Early stage. Interpreter works. Spec is v0.1. Feedback welcome.

GitHub: https://github.com/watari-ai/nail
