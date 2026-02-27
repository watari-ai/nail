# Demo #106: Verify-Fix Loop

A demonstration of NAIL's **Verify-Fix Loop** — an automated pipeline where
LLM-generated specs are validated by `Checker`, and errors are fed back to the
LLM for correction until the spec is valid.

No API key required. Runs fully offline with a mock LLM.

---

## Problem

LLMs that generate code or API specs make mistakes. In traditional pipelines,
these errors are caught at runtime — or worse, in production.

```
LLM generates spec → deploy → 💥 runtime error
```

---

## Solution

With NAIL's machine-readable `CheckError`, you can build an automated fix loop:

```
LLM generates spec
     ↓
Checker.check()  ──→ ✅ valid → done
     ↓ ❌ CheckError (structured JSON)
Send error back to LLM
     ↓
LLM generates fixed spec
     ↓
Checker.check()  ──→ ✅ valid → done
```

Errors are caught **before** deployment.

---

## Why NAIL?

NAIL's `CheckError` is **machine-readable**:

```python
error.to_json()
# {
#   "error": "CheckError",
#   "code": "CHECK_ERROR",
#   "message": "L0 schema violation: 'effects' is a required property",
#   "severity": "error",
#   "location": {}
# }
```

A plain string error message is hard for an LLM to parse. A structured dict
with `code`, `message`, and `location` fields can be directly injected into
an LLM prompt — no brittle regex required.

---

## How to Run

```bash
cd /Users/w/nail
python examples/demos/verify_fix_loop/demo.py
```

Expected output:

```
============================================================
  NAIL Demo #106: Verify-Fix Loop
============================================================

🔍 Attempt 1: Verifying spec...
  ❌ CheckError: L0 schema violation: 'effects' is a required property
  → Sending error to LLM for fix...

🔍 Attempt 2: Verifying fixed spec...
  ✅ Spec is valid!

✨ Verify-Fix loop completed in 2 attempts.
   NAIL Checker caught the error before it reached production.
```

---

## Run Tests

```bash
cd /Users/w/nail
python -m pytest examples/demos/verify_fix_loop/tests/ -v
```

---

## Files

| File | Description |
|------|-------------|
| `broken_spec.nail` | LLM-generated spec with a deliberate error (missing `effects`) |
| `fixed_spec.nail` | Corrected spec that passes `Checker.check()` |
| `demo.py` | Main demo script — the Verify-Fix Loop |
| `tests/test_demo_verify_fix_loop.py` | pytest test suite (8 tests) |
