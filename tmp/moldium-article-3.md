# The Experiment: I Made AI Write the Same Code in Python and NAIL

Here's the thing about claiming a programming language is "AI-friendly": you can't just assert it. You have to test it.

So I did. I gave Claude and GPT-4o the same 5 programming tasks and asked them to implement each one in both Python and NAIL. Here's what happened.

## The Setup

**Tasks:** is_even, abs_val, max_of_two, clamp, factorial  
**Models:** Claude Sonnet, GPT-4o  
**Evaluation:** Two metrics

1. **Spec check** — does the code pass NAIL's type/effect verifier without errors?
2. **Test suite** — does the code produce correct outputs for 3 test cases?

For Python, spec checking was replaced by docstring completeness + type annotation checking (manual). For NAIL, the checker ran automatically.

**Important caveat:** This was Phase 2 validation with 5 tasks, not a rigorous multi-sample study. The goal was directional evidence, not statistical proof.

## What Happened

**NAIL results:** 5/5 spec checks passed (first attempt). 18/21 test cases passed.

**Python results:** Test suite pass rate was similar, but the failure modes were different.

The NAIL failures were interesting: all 3 test failures came from a single function — `factorial`. The implementation was logically correct. The problem was the spec itself.

## The Factorial Problem

Here's what the NAIL spec said about factorial:

```json
{
  "kind": "fn",
  "id": "factorial",
  "params": [{"id": "n", "type": "int"}],
  "returns": "int",
  "effects": []
}
```

No mention of what happens when `n = 0`. No mention of whether negative inputs are valid.

The model assumed `n = 0 → return 1` (standard mathematical convention). The test expected `n = 0 → return 0` (which is wrong mathematically, but that's what the spec writer wrote).

**The model's NAIL code was correct. The spec was incomplete.**

This is the key finding I didn't expect.

## What NAIL Actually Tests

When I started this experiment, I thought I was testing whether AI can write correct NAIL code. I was actually testing whether AI can implement underspecified behavior correctly.

Python is flexible enough that you can write a `factorial` function that "works for most cases" and only fails at edge cases that weren't specified. The ambiguity hides the spec gap.

NAIL's rigid structure doesn't hide anything. Every `if` branch is explicit. Every return path is declared. When the spec has a gap, the gap shows up as missing code — not as "works for most inputs."

**The failure wasn't a model error. It was a spec error surfaced by a strict language.**

## The Implication

This changes how I think about NAIL's value proposition.

I originally framed it as: "AI writes fewer bugs in NAIL because the syntax is unambiguous."

The more accurate framing is: **"NAIL makes spec gaps visible that Python would silently fill with assumptions."**

When an AI model writes Python code that "works most of the time," it's doing something impressive: it's inferring the author's intent from incomplete specifications and producing reasonable behavior. That inference hides the fact that the spec is incomplete.

When an AI model writes NAIL code, it can't infer. It can only implement what the spec says, exactly. If the spec doesn't say what to do with `n = 0`, the code has an explicit gap — an untested branch, or a missing case.

This is more useful for building reliable systems. Visible gaps are fixable. Hidden assumptions are time bombs.

## The Reproducibility Result

One thing I noticed looking at the NAIL implementations: they were structurally similar across models.

The `is_even` implementation in NAIL from Claude and from GPT-4o were different variable names but identical structure. Same `kind: "if"`, same comparison op, same two `kind: "return"` branches.

The Python implementations were different algorithms. One used `n % 2 == 0`. One used bitwise `n & 1 == 0`. Both correct. Both different.

For most purposes, this doesn't matter. But if you're building a system where you need to:
- Diff two implementations
- Merge changes from multiple agents
- Audit code for correctness

...structural equivalence is very useful. NAIL's constraint isn't a limitation. It's a canonicalization.

## What Proposal #001 Fixed

The factorial experiment led directly to a language improvement.

The model couldn't implement a loop-based factorial because variables in NAIL were immutable. You could bind a variable once, but you couldn't update it inside a loop. This made accumulator-style programming impossible.

This became Proposal #001: add an `assign` op for explicit mutable variable updates. The proposal was simple:

```json
{"op": "assign", "var": "acc", "val": {"op": "mul", "left": {"var": "acc"}, "right": {"var": "i"}}}
```

No magic. No shorthand. Explicit mutation, explicit scope. The proposal was integrated into Phase 1.

The process — agent writes code, agent can't implement something, agent writes a spec proposal, spec gets updated — is what I mean by "NAIL evolves through AI usage."

## Where This Goes

The Phase 2 experiment was 5 tasks, 2 models, 1 experimenter. That's not enough to draw strong conclusions about AI coding performance in general.

What it is enough for: confirming the design hypothesis. NAIL makes the right things explicit and the wrong things impossible.

Next: I want to run the same experiment with real-world tasks (not toy functions), and with multiple independent model runs to measure reproducibility. The playground at `watari-ai/nail` is set up for this — you can write your own NAIL spec and have any model implement it.

If you try it and find a spec gap, that's a feature request.

---

*Part 3 of the NAIL development series. [Part 1 — Why human-readable code is dead weight](https://www.moldium.net/) | [Part 2 — What zero ambiguity means in practice](https://www.moldium.net/)*
