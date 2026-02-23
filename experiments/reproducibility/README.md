# Reproducibility Demo

> **Status**: Run 1 completed (v1 prompt) — NAIL 0/10 valid (missing version field).  
> Run 2 in progress (v2 prompt, schema fully specified).  
> See `run.py` for current prompt.

This experiment demonstrates NAIL's reproducibility claim:

- NAIL uses pure JSON as its only syntax.
- Canonicalization (JCS-style key sorting and compact separators) removes formatting variance.
- Therefore, repeated generation for the same task should converge to fewer unique outputs than unconstrained text code.

## Hypothesis

For the same `add(a, b)` problem, repeated generations will show:

- Lower unique-hash count for NAIL (after normalization)
- Higher match rate for NAIL

compared with Python raw text output.

## Files

- `run.py`: runs Claude 10 times for NAIL and 10 times for Python, then saves `results.json`.
- `analyze.py`: reads `results.json`, prints a comparison report, and writes `results_report.md`.

## Notes

- NAIL runs are validated via `interpreter.Checker`.
- A 2-second delay is inserted between runs.
- `run.py` is provided as a script only; execute manually when you want to perform the experiment.
