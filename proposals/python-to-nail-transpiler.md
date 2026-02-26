# Proposal: Python → NAIL IR Transpiler

> Author: NAIL Core Team  
> Date: 2026-02-24  
> Status: Initial Implementation  
> Motivation: ROADMAP.md v0.5 Goal — "Python (typed subset) → NAIL transpiler"

---

## 1. Motivation

NAIL's adoption barrier is high: developers must write JSON by hand. The transpiler flips this:

> **"Don't write NAIL, write Python and verify with NAIL"**

AI-generated Python code gets automatically transpiled to NAIL IR, then passed through NAIL's L1 (type) and L2 (effect) checkers. Zero NAIL knowledge required.

---

## 2. Supported Python Subset

### 2.1 Function Definitions

Only top-level `def` with **complete type annotations** (all parameters + return type):

```python
def add(a: int, b: int) -> int:
    return a + b
```

Functions without annotations are **rejected** (TranspilerError).

### 2.2 Supported Types

| Python annotation | NAIL type JSON |
|---|---|
| `int` | `{"type": "int", "bits": 64, "overflow": "panic"}` |
| `float` | `{"type": "float", "bits": 64}` |
| `bool` | `{"type": "bool"}` |
| `str` | `{"type": "string"}` |
| `None` | `{"type": "unit"}` |

### 2.3 Supported Statements

| Python construct | NAIL IR op |
|---|---|
| `return expr` | `{"op": "return", "val": ...}` |
| `x: int = 5` (annotated assign) | `{"op": "let", "id": "x", "type": ..., "val": ..., "mut": true}` |
| `x = expr` (first assignment) | `{"op": "let", "id": "x", "val": ..., "mut": true}` |
| `x = expr` (re-assignment) | `{"op": "assign", "id": "x", "val": ...}` |
| `x += expr` | `{"op": "assign", "id": "x", "val": {"op": "+", "l": {"ref": "x"}, "r": ...}}` |
| `if cond: ... else: ...` | `{"op": "if", "cond": ..., "then": [...], "else": [...]}` |
| `for i in range(n)` | `{"op": "loop", "bind": "i", "from": {"lit": 0}, "to": ..., "step": {"lit": 1}, "body": [...]}` |
| `for i in range(start, end)` | `{"op": "loop", "bind": "i", "from": ..., "to": ..., "step": {"lit": 1}, "body": [...]}` |
| `for i in range(start, end, step)` | `{"op": "loop", "bind": "i", "from": ..., "to": ..., "step": ..., "body": [...]}` |
| `print(expr)` | `{"op": "print", "val": ..., "effect": "IO"}` (+ `IO` in effects) |

### 2.4 Supported Expressions

| Python expression | NAIL IR |
|---|---|
| Integer literal `42` | `{"lit": 42}` |
| Float literal `3.14` | `{"lit": 3.14}` |
| Boolean `True`/`False` | `{"lit": true}` / `{"lit": false}` |
| String literal `"hello"` | `{"lit": "hello"}` |
| Variable reference `x` | `{"ref": "x"}` |
| Arithmetic `a + b` | `{"op": "+", "l": ..., "r": ...}` |
| Comparison `a == b` | `{"op": "eq", "l": ..., "r": ...}` |
| Boolean `a and b` | `{"op": "and", "l": ..., "r": ...}` |
| Negation `not a` | `{"op": "not", "v": ...}` |
| Unary minus `-a` | `{"op": "-", "l": {"lit": 0}, "r": ...}` |
| Function call `f(a, b)` | `{"op": "call", "fn": "f", "args": [...]}` |

---

## 3. Effect Inference

Effects are automatically inferred by walking the function's AST:

| Python pattern | NAIL effect |
|---|---|
| `open(...)` called anywhere in function | `"FS"` |
| `requests.get(...)` / `requests.post(...)` etc. | `"NET"` |
| `print(...)` called anywhere in function | `"IO"` |

Multiple effects accumulate: a function calling both `open()` and `requests.get()` gets `["FS", "NET"]`.

Effects are emitted in **alphabetical order** for canonical reproducibility.

### 3.1 Detection Algorithm

```python
for node in ast.walk(fn_body):
    if isinstance(node, ast.Call):
        if func is ast.Name("open"):     → add "FS"
        if func is ast.Name("print"):    → add "IO"
        if func is ast.Attribute on ast.Name("requests"): → add "NET"
```

---

## 4. Conversion Rules (Type Hints → NAIL Types)

### 4.1 Simple Types

```
int   → {"type": "int",    "bits": 64, "overflow": "panic"}
float → {"type": "float",  "bits": 64}
bool  → {"type": "bool"}
str   → {"type": "string"}
None  → {"type": "unit"}
```

### 4.2 Return Type `None`

Python `-> None` maps to NAIL `{"type": "unit"}`. The return statement in the body becomes:

```json
{"op": "return", "val": {"lit": null, "type": {"type": "unit"}}}
```

---

## 5. Limitations (Out of Scope)

The following Python constructs are **explicitly not supported**:

| Construct | Reason |
|---|---|
| Classes (`class Foo`) | NAIL has no object system |
| Lambda expressions (`lambda x: x+1`) | NAIL has no first-class functions |
| Decorators (`@decorator`) | No equivalent in NAIL |
| `while` loops | NAIL requires bounded loops; use `for i in range(...)` |
| `try/except` | No exception system; use NAIL `result` type |
| `import` statements | Cross-module transpilation not in scope |
| `*args`, `**kwargs` | Variadic not supported in NAIL |
| List/dict comprehensions | Not in scope for initial version |
| `Optional[T]`, `List[T]` | Generic types need deeper annotation parser |
| `async/await` | NAIL has no concurrency yet |
| Unannotated functions | Rejected; all params + return must be typed |

---

## 6. Output Format

The transpiler outputs a NAIL IR dict (or canonical JSON string):

```json
{
  "nail": "0.1.0",
  "kind": "fn",
  "id": "add",
  "effects": [],
  "params": [
    {"id": "a", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
    {"id": "b", "type": {"type": "int", "bits": 64, "overflow": "panic"}}
  ],
  "returns": {"type": "int", "bits": 64, "overflow": "panic"},
  "body": [
    {"op": "return", "val": {"op": "+", "l": {"ref": "a"}, "r": {"ref": "b"}}}
  ]
}
```

Canonical form: `json.dumps(spec, sort_keys=True, separators=(',', ':'))`.

---

## 7. Integration with NAIL Checker

The transpiler output can be directly passed to `Checker`:

```python
from nail.transpiler.python_to_nail import transpile_function
from interpreter import Checker, Runtime

spec = transpile_function(python_source)
Checker(spec).check()   # Type + Effect verification
rt = Runtime(spec)
result = rt.run({"a": 1, "b": 2})
```

---

## 8. Future Extensions

- `Optional[T]` → `{"type": "option", "inner": ...}`
- `List[T]` → `{"type": "list", "inner": ..., "len": "dynamic"}`
- `Dict[K, V]` → `{"type": "map", "key": ..., "value": ...}`
- Multi-function module transpilation
- `urllib` / `httpx` → `NET` effect detection
- `subprocess` → `IO` effect detection
- CLI integration: `nail transpile script.py`
