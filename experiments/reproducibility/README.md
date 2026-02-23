# Reproducibility Demo

> **Status**: ✅ Experiment complete (v3 prompt).  
> NAIL: 10/10 valid, 1 unique hash (100% convergence).  
> Python: 1 unique hash (100% convergence for trivial task).  
> See `results_report.md` for full analysis.

## Key Findings

For a fully-specified deterministic function (`add`):

- All 10 NAIL runs produced **identical canonical JSON** (1 unique hash)
- Correctness guaranteed by the NAIL checker (10/10 valid)
- Python also converged (1 unique hash) — as expected for trivial tasks

The critical difference: NAIL convergence is **structurally guaranteed** by canonical form.  
Python convergence is **coincidental** (variable names, whitespace, style may vary on harder tasks).

See `experiments/phase2/` for harder multi-problem comparisons.

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
