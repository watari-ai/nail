# Reproducibility Experiment v2 — Report

## Overview

- Problems: `clamp`, `fibonacci`, `fizzbuzz_count`
- Runs per problem per language: **5**

## Per-Problem Results

| Problem | Language | Unique Hashes | Runs | Valid | Match Rate |
|---------|----------|:-------------:|:----:|:-----:|:----------:|
| `clamp` | NAIL   | **1** | 5 | 5/5 | 100.0% |
| `clamp` | Python | **1** | 5 | N/A | 100.0% |
| `fibonacci` | NAIL   | **5** | 5 | 5/5 | 20.0% |
| `fibonacci` | Python | **3** | 5 | N/A | 60.0% |
| `fizzbuzz_count` | NAIL   | **2** | 5 | 5/5 | 60.0% |
| `fizzbuzz_count` | Python | **1** | 5 | N/A | 100.0% |

## Hash Distribution

### `clamp`

**NAIL** — 1 unique hash(es):

| Hash (first 16 chars) | Count |
|----------------------|-------|
| `148c436fe5228e0f...` | 5 |

**PYTHON** — 1 unique hash(es):

| Hash (first 16 chars) | Count |
|----------------------|-------|
| `a385f191b3af78d8...` | 5 |

### `fibonacci`

**NAIL** — 5 unique hash(es):

| Hash (first 16 chars) | Count |
|----------------------|-------|
| `bc54b4d4a42c9e9b...` | 1 |
| `60b0bf1d6763dbf8...` | 1 |
| `634216baea2aa22b...` | 1 |
| `09930cb2d47bdf29...` | 1 |
| `5e75f8ee789187ad...` | 1 |

**PYTHON** — 3 unique hash(es):

| Hash (first 16 chars) | Count |
|----------------------|-------|
| `f217b699d9a9a25d...` | 3 |
| `504d2792e461073b...` | 1 |
| `6b3bf0e1e7ec15e3...` | 1 |

### `fizzbuzz_count`

**NAIL** — 2 unique hash(es):

| Hash (first 16 chars) | Count |
|----------------------|-------|
| `3a318714b0385792...` | 3 |
| `1e9850e8edaed3ac...` | 2 |

**PYTHON** — 1 unique hash(es):

| Hash (first 16 chars) | Count |
|----------------------|-------|
| `b8083cb7e91d01e7...` | 5 |

## Overall

- NAIL: **8** unique hashes / 15 runs (valid: 15)
- Python: **5** unique hashes / 15 runs
- Ratio: Python has **0.6x** more unique hashes than NAIL

## Interpretation

Lower unique-hash count and higher match rate indicate higher output reproducibility. For NAIL, canonical JSON normalization (JCS) eliminates key-order variance before hashing, ensuring that structurally identical programs always produce the same hash.

**Hypothesis (pre-experiment):** NAIL would produce fewer unique hashes than Python, since JCS canonical form eliminates syntactic variance. **Result: hypothesis rejected.** Python showed equal or higher reproducibility on non-trivial problems. JCS eliminates *syntactic* variance (key order, whitespace) but not *algorithmic* variance (loop structure, variable naming strategy). Python converges because canonical implementations dominate training data; NAIL has no such prior — a cold-start problem, not a design flaw. The key finding: **valid 15/15** — every LLM-generated NAIL program passed the checker.
