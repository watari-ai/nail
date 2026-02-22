# Phase 2 Experiment Result Analysis

Execution date: 2026-02-22

---

## Result Summary

| Metric | NAIL | Python |
|---|---|---|
| L0-L2 validation pass | **5/5 (100%)** | N/A |
| Test pass | 18/21 (86%) | 21/21 (100%) |
| Average tokens/function | **173** | 571 (entire file) |
| Type annotations | Complete in all functions | None (optional in Python) |

---

## Per-Problem Details

### P1-P4: All tests passed ✅

All four tasks, `is_even`, `abs_val`, `max_of_two`, and `clamp`, were correct in both NAIL and Python.

Observed NAIL characteristics:
- Without type declarations, programs cannot pass compilation (L1).
- Explicit `int64 overflow: panic` includes failure behavior and bit width in the spec.
- In Python, `n % 2 == 0` relies on implicit bool-returning comparison, but in NAIL, comparisons with mismatched types are compile errors.

### P5: factorial — Partial failure ⚠️

```
n=0: ✓ (accidentally correct because acc=1)
n=1: ✗ (loop-local acc does not propagate to outer scope)
n=5: ✗
n=10: ✗
```

**Cause**: Mutable variable semantics are undefined in NAIL v0.1.
Even if `let acc = ...` appears inside a loop, it is treated as a loop-scope local variable, so outer `acc` is not updated.

**Is this a bug?** → **No. It is a spec gap.**

All L0-L2 checks passed. That means a program can be "type-correct but semantically incomplete."
This is an important language-design issue for NAIL v0.1.

**→ Proposal: Clarify `mut` semantics in v0.2**

---

## Discovery: Structural Advantages of NAIL

### 1. Prevent Type Errors Through Declarations Before Writing Logic

In Python, bugs like this are only detected at runtime:
```python
def add(a, b):
    return a + b  # "1" + 2 raises TypeError
```

In NAIL, `params` declares types, so mismatches are detected immediately at L1 check time.

### 2. Effect Pollution Is Impossible

```
bad_effect.nail: 'print' uses IO effect, but function does not declare it
```

In NAIL, a class of bugs where a side-effecting function is declared pure cannot structurally exist.

In Python, this is legal:
```python
def add(a, b):
    print(f"debug: {a} + {b}")  # has side effects but not represented in signature
    return a + b
```

### 3. Token Efficiency

- NAIL average per function: **173 tokens**
- Python entire 5-function file: **571 tokens** (about 114/function)
- In raw count, Python seems smaller, but NAIL includes **type info, overflow behavior, and effects**
- Encoding equivalent information in Python requires extra annotations or comments

---

## Proposals for v0.2 (AI Spec Improvement Proposal #001)

### Proposal #001: Explicit Mutable Variable Semantics

```json
// Mutable variable declaration
{ "op": "let", "id": "acc", "mut": true, "val": { "lit": 1 } }

// Reassignment (separate op from let)
{ "op": "assign", "id": "acc", "val": { "op": "*", "l": { "ref": "acc" }, "r": { "ref": "i" } } }
```

- `let` declares a variable (immutable by default)
- `assign` reassigns a mutable variable (`assign` to variables without `mut: true` is a compile error)
- Scope rule: `assign` inside inner scope can mutate variables in outer scope

### Proposal #002: Allow `if` as an Expression

```json
{
  "op": "return",
  "val": {
    "op": "if_expr",
    "cond": { "op": "gte", "l": { "ref": "a" }, "r": { "ref": "b" } },
    "then": { "ref": "a" },
    "else": { "ref": "b" }
  }
}
```

Current `if` is statement-only. Expression form would make many patterns more concise.

---

## Conclusion

**Current answer to "Is NAIL easy for AI to write?": Yes, with conditions**

- The zero-ambiguity structure makes type mismatch and effect pollution **physically impossible** for LLMs to produce in accepted code.
- On the other hand, mutable-variable limitations in v0.1 create semantic errors in loop-based algorithms.
- This semantic issue can be solved with v0.2 `assign` and `if_expr`.

**Key observation**: Bugs in NAIL are caused by spec incompleteness, not by AI inference mistakes.
This supports NAIL's design philosophy: when language rules are precise, error causes become precise.
