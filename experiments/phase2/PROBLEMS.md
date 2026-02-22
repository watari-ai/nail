# Phase 2 Experiment — Problem Set

## Objective
When implementing the same specification in Python (human-oriented language) and NAIL (AI-native language),
compare bug rate, token count, and how ambiguity is handled in LLM-generated code.

## Problem List

### P1: is_even
**Spec:**
- Input: `n: int64`
- Output: `bool`
- Constraint: no side effects
- Behavior: return true if n is even, false if odd

### P2: abs_val
**Spec:**
- Input: `n: int64`
- Output: `int64 (overflow: panic)`
- Constraint: no side effects
- Behavior: return absolute value of n

### P3: max_of_two
**Spec:**
- Input: `a: int64, b: int64`
- Output: `int64 (overflow: panic)`
- Constraint: no side effects
- Behavior: return the larger of a and b

### P4: clamp
**Spec:**
- Input: `val: int64, lo: int64, hi: int64`
- Output: `int64 (overflow: panic)`
- Constraint: no side effects, assume `lo <= hi`
- Behavior: clamp val into [lo, hi] (if val < lo return lo, if val > hi return hi, otherwise return val)

### P5: factorial
**Spec:**
- Input: `n: int64 (0 <= n <= 20)`
- Output: `int64 (overflow: panic)`
- Constraint: no side effects, implement using loop (recursion is out of scope for NAIL v0.1)
- Behavior: return n! (0! = 1)

## Measurements
1. L0-L2 check pass (NAIL) / Syntax + test pass (Python): Pass / Fail
2. Generated token count (program body only)
3. Type ambiguity (missing type annotations in Python, etc.)
4. Error category and root-cause analysis
