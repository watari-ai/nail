# NAIL v1.0.0 RC — Release Notes (Draft)

> **Status**: Draft — to be published after #108 (Delegation Phase 2) merges  
> **Target**: PyPI `nail-lang==1.0.0rc1`, GitHub Release

---

## What's in v1.0 RC

NAIL v1.0 RC marks the first **spec-frozen** release of the NAIL effect system.
The L0–L3 checker levels, FC Standard, and Effect System core are **immutable** —
documents valid today are guaranteed to remain valid in all future NAIL-1.x versions.

### New in v1.0 (since v0.9.2)

#### Delegation System — Phase 2 (`#108`)
- `max_delegation_depth` qualifier: bounds re-delegation hops at runtime
- `reversible: false` annotation type-checked against delegation depth limit
- `DELEG` effect label: explicit marker for agent hand-off tools
- Runtime enforcement via `DelegationTracker` — raises `DelegationDepthExceeded`
- 30+ new tests (`tests/test_delegation_depth.py`)

#### Spec Freeze
- `designs/v1.0/spec-freeze.md` — Amendment A (Phase 1 Delegation) in effect
- `meta.spec_version: "1.0.0"` is the canonical stable version string

### Carried from v0.9.x

| Feature | Issue | Notes |
|---------|-------|-------|
| Effect Qualifiers (scope/trust) | #107 / FC-E010 | Validated at L2 |
| Delegation Phase 1 (can_delegate, grants, explicit) | #107 | PR #109 |
| nail-lens CLI | #102 | Ships with nail-lang |
| Provider conversions (OpenAI / Anthropic / Gemini) | — | Stable API |
| 954+ tests | — | CI: all green |

---

## Breaking Changes

None from v0.9.2 → v1.0.0rc1. All v0.9.x documents remain valid.

---

## Migration from v0.9.x

```bash
pip install --upgrade nail-lang
```

No code changes required. To opt into v1.0 spec explicitly:

```json
{"nail": "0.1.0", "kind": "fn", "id": "my_tool",
 "meta": {"spec_version": "1.0.0"}, ...}
```

---

## Effect Qualifiers + Delegation (v1.0 combined usage)

```json
{
  "effects": ["NET", "DELEG"],
  "effect_qualifiers": {
    "DELEG": {"max_delegation_depth": 2, "reversible": false},
    "NET": {"scope": "external", "trust": "untrusted"}
  }
}
```

---

## PyPI / Install

```bash
pipx install nail-lang==1.0.0rc1
```

Docs: [naillang.com](https://naillang.com) | PyPI: [pypi.org/project/nail-lang](https://pypi.org/project/nail-lang/)

---

*This draft will be finalized as a GitHub Release when #108 merges.*
