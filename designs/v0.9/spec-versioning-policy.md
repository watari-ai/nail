# NAIL Spec Versioning Policy

**Document version**: 0.1.0  
**Status**: Draft  
**Created**: 2026-02-26  
**Applies to**: NAIL v0.9.x and beyond  
**Audience**: Alternative implementers, external contributors

---

## 1. Version Number Scheme

NAIL uses a three-part version scheme:

```
NAIL-{major}.{minor}.{patch}
```

| Component | Incremented when... |
|-----------|---------------------|
| `major`   | Breaking changes that cannot be handled by a migration path. Reserved for fundamental redesigns (e.g., a new IR format). |
| `minor`   | Non-breaking additions, new optional features, new optional fields, or deprecations without removal. |
| `patch`   | Bug fixes, clarifications, and documentation corrections with no semantic change. |

### Examples

| Version | Typical content |
|---------|-----------------|
| `NAIL-1.0.0` | First stable spec freeze (v1.0 RC target) |
| `NAIL-1.1.0` | New optional field added to ToolDef |
| `NAIL-1.1.1` | Typo correction in §5, no semantic change |
| `NAIL-2.0.0` | fc_ir_v2 introduces incompatible root structure |

### `spec_version` Field

Starting from NAIL v0.9, the `meta.nail_version` field in fc_ir_v1 documents records the NAIL implementation version that generated the document.  
A separate `meta.spec_version` field is **reserved** for future use to record the NAIL *specification* version.

**Mandatory timing**: `meta.spec_version` becomes a **required field** (not merely optional) when the spec is frozen at NAIL-1.0.0.  
Until that point, its presence is encouraged but not enforced.

```json
"meta": {
  "nail_version": "0.9.1",
  "spec_version": "NAIL-0.9",
  "created_at": "2026-02-26T00:00:00Z"
}
```

---

## 2. Breaking vs. Non-Breaking Changes

### 2.1 Breaking Changes (require `major` bump)

A change is **breaking** if any previously valid document or implementation behaviour becomes invalid or produces different results.

| Change type | Example | Breaking |
|-------------|---------|----------|
| JSON key deletion | Remove `effects` from ToolDef | ✅ |
| JSON key rename | Rename `doc` → `description` | ✅ |
| Field type change | `effects.allow` from `array` to `object` | ✅ |
| Required field added | Add mandatory `version` to ToolDef | ✅ |
| Validation rule tightened | `doc` min length raised from 20 to 50 chars | ✅ |
| Semantics changed | `effects.kind: "capabilities"` behaviour altered | ✅ |
| Error code semantics changed | FC004 meaning redefined | ✅ |

### 2.2 Non-Breaking Changes (allow `minor` bump)

| Change type | Example | Breaking |
|-------------|---------|----------|
| Optional field added | New optional `examples` sub-field in ToolDef | ❌ |
| Validation rule relaxed | `doc` min length reduced from 20 to 10 chars | ❌ |
| New error/warn code added | FC013 WARN for new pattern | ❌ |
| New enum value added | New effect category `TIME` | ❌ |
| New CLI flag added | `--annotate-effects` flag | ❌ |
| Documentation clarified | Reword a paragraph without semantic change | ❌ |

### 2.3 Ambiguous Cases — Decision Rules

Ambiguous situations are resolved by this priority order:

1. **Implementer perspective first**: If a conformant implementation would need code changes to remain conformant, it is **breaking**.
2. **Document perspective second**: If a previously valid document would be rejected by a new checker, it is **breaking**.
3. **Warn-to-error promotions**: Promoting an existing WARN code to ERROR is **breaking** (changes exit code behaviour).

---

## 3. Deprecation Policy

### 3.1 Minimum Survival Period

A deprecated feature must remain **fully functional** for a minimum of **2 minor versions** after the deprecation notice before it can be removed.

```
NAIL-1.1.0  →  Feature X deprecated, FC_DEPR_001 WARN issued
NAIL-1.2.0  →  Feature X still functional (WARN continues)
NAIL-1.3.0  →  Feature X still functional (WARN continues)
NAIL-2.0.0  →  Feature X removed (breaking → major bump)
```

Removal before the 2-minor-version window requires an explicit exception documented in the release notes.

### 3.2 `"deprecated": true` Annotation

Deprecated features in the spec are marked inline with:

```
> ⚠️ **Deprecated** since NAIL-X.Y: Use [replacement] instead.  
> Will be removed in NAIL-(X+1).0.  
> Migration guide: [link]
```

In the NAIL JSON format, deprecated fields carry a `"deprecated": true` annotation in the schema (where applicable) and in error reporting:

```
[FC_DEPR_001] WARN: Tool 'weather.get': 'effects' uses legacy string-array format (deprecated since NAIL-0.9). Run 'nail fc canonicalize' to migrate.
```

This corresponds to the existing **FC009 WARN** for legacy effects format.

### 3.3 Mandatory Migration Guide

Every deprecation notice **must** include:

1. What is being deprecated (precise field path / behaviour)
2. Why it is being deprecated
3. The replacement to use instead
4. A step-by-step or automated migration path (prefer `nail fc canonicalize` where possible)
5. The removal timeline

Example entry in `CHANGELOG.md`:

```markdown
## Deprecated in NAIL-0.9
### Legacy effects string-array format
- **Deprecated**: `"effects": ["FS", "NET"]`
- **Reason**: Ambiguous semantics; capabilities format is more expressive
- **Replacement**: `"effects": {"kind": "capabilities", "allow": ["FS", "NET"]}`
- **Migration**: Run `nail fc canonicalize` — automatic conversion
- **Removal**: NAIL-2.0.0
```

---

## 4. FC IR v1.0 Compatibility

### 4.1 Post-Freeze Guarantee

Once `fc_ir_v1` is formally frozen (NAIL-1.0.0 target):

- The `"kind": "fc_ir_v1"` semantics are **immutable**
- Existing required fields cannot be deleted, renamed, or have their types changed
- Existing validation rules cannot be tightened in a way that would reject previously valid documents
- All changes to `fc_ir_v1` documents must be backward compatible (i.e., a NAIL-1.0 checker accepts all valid NAIL-1.0 documents without modification)

### 4.2 Extension Mechanism Post-Freeze

Future non-breaking extensions use one of these mechanisms:

| Mechanism | Use case | Example |
|-----------|----------|---------|
| New optional fields in `annotations` | Provider-specific hints | `annotations.openai.strict` |
| New optional top-level ToolDef fields | Universal optional metadata | `"tags": [...]` |
| New `kind` value | Incompatible format | `"kind": "fc_ir_v2"` |

The `annotations` object is the **primary extension point** and is guaranteed to remain an open-ended key-value store.

### 4.3 `spec_version` Adoption Timeline

| Milestone | `spec_version` status | Action required |
|-----------|----------------------|-----------------|
| NAIL 0.9.x (current) | Optional | Add to `meta` if you generate new documents |
| NAIL 1.0.0 RC | Strongly recommended | Checkers emit FC013 WARN if absent |
| NAIL 1.0.0 stable | **Required** | Checkers emit FC013 ERROR if absent |

---

## 5. Implementer Guidelines

This section is for authors of **alternative NAIL checkers** (e.g., a Rust or Go reimplementation). Use it as a checklist when tracking spec updates.

### 5.1 Tracking Spec Changes

When a new NAIL spec version is released:

- [ ] Read the `CHANGELOG.md` entry for the new version
- [ ] Identify all changes tagged `[BREAKING]` — these require code changes before upgrading
- [ ] Identify all changes tagged `[DEPRECATED]` — schedule removal tracking
- [ ] Identify all changes tagged `[NEW OPTIONAL]` — safe to add incrementally
- [ ] Run the Conformance Test Suite (see `conformance-test-suite.md`) against your implementation
- [ ] Update your implementation's reported `spec_version` string

### 5.2 Handling Unknown Fields

A conformant checker **must** follow this policy:

| Context | Unknown field behaviour |
|---------|-------------------------|
| Inside `annotations` | Silently ignore (always open) |
| Outside `annotations` (normal mode) | Issue FC011 WARN, continue processing |
| Outside `annotations` (`--strict` mode) | Issue FC011 ERROR, abort |

Do **not** reject unknown fields silently (fail-close) without a diagnostic — that makes debugging impossible.

### 5.3 Error Code Stability

Error codes (`FC001`–`FC012`, `FC_DEPR_*`) are stable identifiers. Alternative implementations must:

- Use the same error code strings (not just messages)
- Exit with code `1` when at least one ERROR is present
- Exit with code `0` when only WARNs are present (unless `--fail-on-warn` is set)
- Not invent new error codes without upstream coordination

When a new error code is introduced in a minor version, existing implementations may emit a generic fallback WARN until they implement it — this is considered conformant.

### 5.4 Validation Checklist

Every fc_ir_v1 document must be validated in this order:

- [ ] Root key `kind` equals `"fc_ir_v1"` (reject otherwise)
- [ ] `tools` is an array (may be empty)
- [ ] All `id` values are unique across `tools` (FC001)
- [ ] All `name` values (explicit + auto-generated) are unique (FC002)
- [ ] Each ToolDef's `input` has `type: "object"` (FC003)
- [ ] PURE tools (`allow: []`) declare no FS/NET/IO effects (FC004)
- [ ] Canonical form is correct when `--strict` is active (FC005)
- [ ] `doc` field is ≥ 20 characters (FC010 WARN if shorter)
- [ ] Unknown keys outside `annotations` trigger FC011
- [ ] `input.required` presence when `properties` ≥ 2 (FC012 WARN if absent)

### 5.5 Versioned Spec Documents

The canonical spec documents for each version are stored in:

```
/docs/spec-{major}.{minor}.md        # e.g. spec-1.0.md
/docs/fc-ir-v{N}.md                   # e.g. fc-ir-v1.md (frozen at v1.0)
/designs/v{major}.{minor}/            # design decision records
```

Implementers should pin to a specific `spec_version` tag in the NAIL git repository and upgrade deliberately, not automatically.

### 5.6 Compatibility Declaration

Alternative implementations should declare their compatibility in their README:

```
Conformance: NAIL-0.9 (fc_ir_v1, L0–L2)
Conformance test suite: PASS 142/142 (L0: 48, L1: 54, L2: 40)
```

See `conformance-test-suite.md` for the canonical test set and pass criteria.

---

## Appendix: Change Classification Quick Reference

```
Is an existing key being removed or renamed?              → BREAKING (major)
Is a field's type changing?                               → BREAKING (major)
Is a currently optional field becoming required?          → BREAKING (major)
Is a validation rule being tightened?                     → BREAKING (major)
Is a WARN being promoted to ERROR?                        → BREAKING (major)
Is a new optional field being added?                      → non-breaking (minor)
Is a validation rule being relaxed?                       → non-breaking (minor)
Is a new CLI flag being added?                            → non-breaking (minor)
Is a new WARN code being added?                           → non-breaking (minor)
Is documentation being clarified without semantic change? → patch
Is a bug in the spec text being corrected?                → patch
```
