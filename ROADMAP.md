# NAIL — Roadmap

> See [HISTORY.md](HISTORY.md) for full version history (Phase 1/2, v0.2–v0.4 details, Opus analysis).

---

## Current Status

```
v0.8.0: ✅ COMPLETE (2026-02-25) — FC Standard, 594 tests
v0.8.1: ✅ COMPLETE — L3.1 call-site measure verification, type stubs
v0.8.2: ✅ COMPLETE — version string sync, Playground fixes, CLI.md
v0.9.0: ✅ COMPLETE (2026-02-26) — Spec Versioning Policy, Conformance Test Suite (45 tests)
Phase 3: 🚀 Active — repo public, Playground live, articles published
Phase 4: 🚀 Active — AI-driven OSS vision in progress
```

*Last updated: 2026-02-26 by Watari*

---

## Completed Versions

| Version | Date | Summary |
|---------|------|---------|
| v0.2 | 2026-02-23 | call op, effect propagation, canonical form enforcement, 73 tests |
| v0.3 | 2026-02-24 | overflow ops, Result type, cross-module import, CI matrix, 94 tests |
| v0.4 | 2026-02-24 | type aliases, fine-grained effects, collection ops, FC annotations, Python→NAIL transpiler, PyPI v0.4.0, 320 tests |
| v0.5 | 2026-02-24 | Enum/ADT, Core StdLib, return-path exhaustiveness, CI canonical check |
| v0.6 | 2026-02-25 | L3 Termination Proof (loop step + recursive decreasing measure), 421 tests |
| v0.7.0 | 2026-02-25 | Generics (TypeParam/type inference), MCP Bridge, JSON error format, Playground shareable links |
| v0.7.1 | 2026-02-25 | version bump, PyPI v0.7.1 published |
| v0.7.2 | 2026-02-25 | Generic type aliases, SPEC.md §16.5, PyPI v0.7.2 published |
| v0.8.0 | 2026-02-25 | FC Standard (`nail_lang.fc_standard`), OpenAI/Anthropic/Gemini converters, round-trip tests, 594 tests |
| v0.8.1 | 2026-02-25 | L3.1 call-site measure verification, type stubs (`nail_lang/__init__.pyi`) |
| v0.8.2 | 2026-02-25 | Version string sync, Playground fixes, CLI.md, demo exit code fix (#82) |
| v0.9.0 | 2026-02-26 | Spec Versioning Policy, Conformance Test Suite (45 tests, L0/L1/L2/L3/FC) |

---

## In Progress / Next: v0.9

**Phase A: Pre-HN (v0.9.0)**
- [x] **Token Efficiency Benchmarks** — `benchmarks/token_efficiency.py` (tiktoken cl100k_base). NAIL saves 25% vs Python and 20% vs TypeScript for effect-annotated function declarations; within 19% of OpenAI FC for multi-tool modules. See `benchmarks/README.md`.
- [x] **L3.1 Call-site Measure Verification** — Verify that recursive calls pass `measure - k` (k > 0) at each call site, making termination proofs genuinely sound rather than trust-based annotations. *(shipped in v0.8.1)*
- [x] **NAIL SDK** — Clean Python API with type stubs (`nail_lang` public interface), formal API documentation, and usage examples for each major feature (FC Standard, filter_by_effects, MCP Bridge). *(type stubs shipped in v0.8.1)*
- [x] **Documentation complete** — SPEC.md (v0.8.0), PHILOSOPHY.md, ROADMAP.md, README.md, CLI.md, IDEAS.md all updated and reviewed (2026-02-25).

**Phase B: Post-HN (v0.9.x)**
- [x] **Spec Versioning Policy** — Formal definition of breaking vs non-breaking changes, deprecation period rules. (`designs/v0.9/spec-versioning-policy.md`, commit e065c24)
- [x] **Conformance Test Suite** — Canonical test set for alternative NAIL implementations to validate spec compliance. (`conformance/`, 45 tests, L0/L1/L2/L3/FC, commit 37ca91c)

**Phase C: v1.0 RC**
- [ ] **Spec Freeze** — NAIL JSON format frozen. No breaking changes after this point.

### Developer Experience & Connectivity (Deferred)
- [ ] **LSP Support** — Language Server Protocol for Nail-Lens integration.
- [ ] **NAIL → WebAssembly** — Compile NAIL to Wasm for browser execution.
- [ ] **AI Agent Protocol (NATP)** — NAIL-format task delegation between agents.

### Concurrency & Security (Deferred)
- [ ] **Async / Concurrency** — Full design required simultaneously: cancellation, timeout, join/await types, determinism policy.
- [ ] **Effect Security Model** — Formal policy for FS/NET/TIME/RAND/ASYNC: audit log spec, permission boundary definitions.

---

## Long-term Vision

NAIL's long-term goal (Phase 4) is to become the substrate for AI-to-AI collaboration:

- **AI-generated Issues and PRs** — AI detects spec gaps, proposes fixes, human approves
- **AI-specialized dialects** — `nail-finance`, `nail-embedded`, `nail-web` with formal traceability
- **AI Code Verifier as a Service** — accept AI-generated code, verify via NAIL IR, emit compliance certificates
- **NAIL in NAIL** — bootstrapping: write the NAIL checker in NAIL itself (post-v1.0 experiment)

> Full Phase 4 vision and Opus analysis: see [HISTORY.md](HISTORY.md)

### Phase 3 Experimental Work (Active)
- [ ] Reproducibility demo — same task across multiple LLMs, measure agreement rate
- [ ] Verify-fix loop demo — AI generates → checker rejects → AI revises → passes
- [ ] Encoding optimization experiment — can AI design a more token-efficient NAIL encoding?
