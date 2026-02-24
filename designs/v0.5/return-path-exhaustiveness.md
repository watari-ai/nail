# Design: Return-Path Exhaustiveness Check (v0.5 / Issue #43)

**Status:** Design complete, awaiting implementation  
**Author:** Watari  
**Date:** 2026-02-24

---

## 1. Problem

The NAIL checker currently does not verify that every code path in a function body terminates with a `return` op. This means a function can silently fall through — returning `null` or undefined behavior — without a compile-time error.

**Example (should fail, currently passes):**

```json
{
  "kind": "fn", "id": "risky", "effects": [], 
  "params": [{"id": "x", "type": {"type": "int", "bits": 64, "overflow": "panic"}}],
  "returns": {"type": "int", "bits": 64, "overflow": "panic"},
  "body": [
    {
      "op": "if",
      "cond": {"op": ">", "l": {"ref": "x"}, "r": {"lit": 0}},
      "then": [{"op": "return", "val": {"ref": "x"}}]
    }
  ]
}
```

The negative branch falls through without a `return`. This should be a `CheckError`.

---

## 2. Formal Definition

A statement list `S` is **return-exhaustive** if:

1. The list is non-empty AND the last element is a `return` op, OR  
2. The last element is an `if` op where **both** `then` and `else` lists are return-exhaustive, OR  
3. The last element is a `match_enum` op where **every** case body list is return-exhaustive.

Anything else is NOT return-exhaustive → `CheckError`.

**Special case:** A function returning `{"type": "unit"}` (void) is exempted — an implicit return at end-of-body is allowed for unit functions.

---

## 3. Implementation Plan

### 3.1 Add helper function in `checker.py`

```python
def _is_return_exhaustive(body: list) -> bool:
    """Return True if the statement list guarantees a return on all paths."""
    if not body:
        return False
    last = body[-1]
    op = last.get("op")
    
    if op == "return":
        return True
    
    if op == "if":
        then_body = last.get("then", [])
        else_body = last.get("else", [])
        # Both branches must exist and be exhaustive
        if not else_body:
            return False  # Missing else → not exhaustive
        return _is_return_exhaustive(then_body) and _is_return_exhaustive(else_body)
    
    if op == "match_enum":
        cases = last.get("cases", [])
        if not cases:
            return False
        # Every case must be exhaustive
        return all(_is_return_exhaustive(c.get("body", [])) for c in cases)
    
    return False
```

### 3.2 Call in `_check_fn_body` (or equivalent)

After the existing type/effect checking of the function body, add:

```python
# Only check for non-unit return types
if fn_returns != {"type": "unit"}:
    if not _is_return_exhaustive(fn_body):
        raise CheckError(
            f"[{fn_id}] Not all code paths return a value. "
            f"Ensure every if/match_enum branch has a return."
        )
```

### 3.3 Update SPEC.md

Add to §2 (Function Definitions):

> **Return-path exhaustiveness:** The checker verifies that every execution path in a function body terminates with a `return` op. For functions with non-`unit` return types, an `if` without an `else`, or a `match_enum` missing a case return, is a `CheckError`. Functions returning `unit` are exempt.

---

## 4. Test Cases

### 4.1 Should FAIL (missing else-return)
```json
{
  "op": "if",
  "cond": {"op": ">", "l": {"ref": "x"}, "r": {"lit": 0}},
  "then": [{"op": "return", "val": {"ref": "x"}}]
  // no "else" → CheckError
}
```

### 4.2 Should PASS (both branches return)
```json
{
  "op": "if",
  "cond": {"op": ">", "l": {"ref": "x"}, "r": {"lit": 0}},
  "then": [{"op": "return", "val": {"ref": "x"}}],
  "else": [{"op": "return", "val": {"op": "neg", "val": {"ref": "x"}}}]
}
```

### 4.3 Should FAIL (match_enum case missing return)
```json
{"op": "match_enum", "val": {"ref": "c"}, "cases": [
  {"tag": "Red",   "body": [{"op": "return", "val": {"lit": 1}}]},
  {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
  {"tag": "Blue",  "body": [{"op": "let", "id": "x", "val": {"lit": 3}}]}
  // Blue branch doesn't return → CheckError
]}
```

### 4.4 Should PASS (unit return type — exempt)
```json
{
  "kind": "fn", "id": "log", "effects": ["IO"],
  "params": [{"id": "msg", "type": {"type": "string"}}],
  "returns": {"type": "unit"},
  "body": [{"op": "print", "val": {"ref": "msg"}}]
  // No return needed for unit functions
}
```

### 4.5 Should PASS (nested if/else, all paths return)
```json
{
  "op": "if",
  "cond": ...,
  "then": [
    {"op": "if", "cond": ...,
     "then": [{"op": "return", "val": {"lit": 1}}],
     "else": [{"op": "return", "val": {"lit": 2}}]}
  ],
  "else": [{"op": "return", "val": {"lit": 3}}]
}
```

---

## 5. Edge Cases

| Case | Expected |
|------|----------|
| Empty body, non-unit return | CheckError |
| Only `let` ops, no return | CheckError |
| Return inside a loop | Consider loop as NOT exhaustive (loop may not execute) |
| Nested match_enum | Recursively check each case body |
| `else: []` (empty else) | CheckError (empty list is not exhaustive) |

---

## 6. Relationship to Existing Checks

- **Enum variant exhaustiveness** (already implemented): checks that `match_enum` covers all declared variants.  
- **Return-path exhaustiveness** (this issue): checks that each covered variant's body actually returns.

These are orthogonal: you can have all variants covered but one branch doesn't return. Both checks must pass independently.

---

## 7. Acceptance Criteria (from Issue #43)

- [x] Design document complete
- [ ] `_is_return_exhaustive()` helper in `checker.py`
- [ ] Called after existing body type-check for non-unit functions
- [ ] Test: missing else-return → `CheckError`
- [ ] Test: all-paths-returning → passes
- [ ] SPEC.md updated with return-path exhaustiveness rule
