"""
NAIL v1.1 — RAG Context Kind Phase A Tests (Draft)

These tests define the expected behavior of `kind: context` documents.
All tests are skipped until implementation lands (Issue #111 Phase A).

Spec reference: designs/v1.1/rag-context-kind.md

To run: pytest tests/test_v11_rag_context.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="v1.1 not yet implemented — Issue #111 Phase A")

# ---------------------------------------------------------------------------
# Minimal valid context document for reuse across tests
# ---------------------------------------------------------------------------

VALID_CONTEXT_DOC = {
    "kind": "context",
    "id": "auth_flow_ctx_001",
    "source": {
        "document_id": "docs/auth/oauth2-flow.md",
        "chunk_index": 3,
        "retrieval_score": 0.91,
        "score_scale": "normalized_0_1",
    },
    "valid_until": "2026-12-31",
    "facts": [
        {
            "key": "oauth2.pkce_required",
            "value": True,
            "type": "bool",
            "fact_confidence": 0.95,
        },
        {
            "key": "oauth2.token_lifetime_seconds",
            "value": 3600,
            "type": "int",
            "fact_confidence": 0.99,
        },
    ],
    "relations": [
        {"target_id": "auth_flow_ctx_002", "relation": "precedes"},
    ],
}


# ===========================================================================
# Test 1: Valid context document passes fc check
# ===========================================================================


def test_valid_context_document_passes_fc_check():
    """A well-formed `kind: context` document passes the NAIL fc checker without errors.

    This is the baseline smoke test: a minimal but complete context doc
    (kind, id, source, facts) must pass validation cleanly.
    """
    from nail_lang.fc_context import check_context_document

    errors = check_context_document(VALID_CONTEXT_DOC)

    assert errors == [], f"Expected no errors, got: {errors}"


# ===========================================================================
# Test 2: context kind with retrieval_score and fact_confidence
# ===========================================================================


def test_context_kind_retrieval_score_and_fact_confidence():
    """source.retrieval_score and facts[].fact_confidence are parsed and accessible.

    After parsing, the resulting ContextDocument object exposes both scores.
    Validates the two-level confidence model described in the spec:
      - retrieval_score: chunk-level relevance set by the retriever
      - fact_confidence: per-fact reliability set by the knowledge curator
    """
    from nail_lang.fc_context import parse_context_document

    doc = parse_context_document(VALID_CONTEXT_DOC)

    assert doc.source.retrieval_score == 0.91
    assert doc.source.score_scale == "normalized_0_1"
    assert doc.facts[0].key == "oauth2.pkce_required"
    assert doc.facts[0].fact_confidence == 0.95
    assert doc.facts[1].key == "oauth2.token_lifetime_seconds"
    assert doc.facts[1].fact_confidence == 0.99


# ===========================================================================
# Test 3: context kind with valid_until field
# ===========================================================================


def test_context_kind_valid_until_field():
    """valid_until is parsed as an ISO 8601 date and accessible on the document.

    The field is optional; when present it marks the temporal horizon beyond
    which the facts should no longer be trusted.
    """
    from nail_lang.fc_context import parse_context_document

    doc = parse_context_document(VALID_CONTEXT_DOC)

    assert doc.valid_until is not None
    # Must be parseable as a date — check string representation
    assert str(doc.valid_until) == "2026-12-31"


# ===========================================================================
# Test 4: context kind with facts array
# ===========================================================================


def test_context_kind_facts_array():
    """facts array is parsed into typed fact objects with key, value, and type fields.

    The facts list must contain at least one item (enforced by the schema).
    Each fact carries key, value, type, and optionally fact_confidence.
    """
    from nail_lang.fc_context import parse_context_document

    doc_data = {
        "kind": "context",
        "id": "payments_ctx_001",
        "source": {
            "document_id": "specs/payments/v3-openapi.yaml",
            "chunk_index": 12,
            "retrieval_score": 17.4,
            "score_scale": "bm25_raw",
        },
        "facts": [
            {"key": "payments.max_amount_jpy", "value": 1000000, "type": "int", "fact_confidence": 1.0},
            {"key": "payments.idempotency_key_required", "value": True, "type": "bool", "fact_confidence": 1.0},
            {"key": "payments.webhook_retry_policy", "value": "exponential_backoff_3x", "type": "string", "fact_confidence": 0.88},
            {"key": "payments.deprecated_endpoint", "value": "/v2/charge", "type": "string", "fact_confidence": 1.0},
        ],
    }

    doc = parse_context_document(doc_data)

    assert len(doc.facts) == 4
    assert doc.facts[0].key == "payments.max_amount_jpy"
    assert doc.facts[0].value == 1000000
    assert doc.facts[0].type == "int"
    assert doc.facts[2].fact_confidence == 0.88


# ===========================================================================
# Test 5: context kind with relations field
# ===========================================================================


def test_context_kind_relations_field():
    """relations field is parsed into typed relation objects with target_id and relation.

    Relations enable cross-chunk graph navigation.
    Valid relation values: precedes, follows, supports, contradicts, elaborates.
    """
    from nail_lang.fc_context import parse_context_document

    doc = parse_context_document(VALID_CONTEXT_DOC)

    assert len(doc.relations) == 1
    assert doc.relations[0].target_id == "auth_flow_ctx_002"
    assert doc.relations[0].relation == "precedes"


# ===========================================================================
# Test 6: Missing required 'source' field raises error
# ===========================================================================


def test_missing_source_field_raises_error():
    """A context document without the required 'source' field must raise a validation error.

    'source' is required (alongside 'kind', 'id', 'facts') per the JSON Schema.
    The fc checker must emit a structured error with a clear code.
    """
    from nail_lang.fc_context import check_context_document

    doc_no_source = {
        "kind": "context",
        "id": "incomplete_ctx_001",
        # 'source' is intentionally omitted
        "facts": [
            {"key": "some.fact", "value": True, "type": "bool"},
        ],
    }

    errors = check_context_document(doc_no_source)

    assert len(errors) >= 1
    codes = [e.code for e in errors]
    assert any("MISSING_REQUIRED_FIELD" in code or "source" in code.lower() for code in codes), (
        f"Expected a missing-source error, got codes: {codes}"
    )


# ===========================================================================
# Test 7: Expired valid_until emits warning
# ===========================================================================


def test_expired_valid_until_emits_warning():
    """A context document with a past valid_until date emits a CONTEXT_EXPIRED warning.

    Per spec: the L0 checker emits CONTEXT_EXPIRED when current_utc_date > valid_until.
    The boundary rule: the chunk is valid for the entire valid_until date.
    The checker must not hard-error on expiry — only warn.
    """
    from nail_lang.fc_context import check_context_document

    expired_doc = {
        "kind": "context",
        "id": "old_ctx_001",
        "source": {
            "document_id": "docs/legacy/v1-api.md",
            "chunk_index": 0,
            "retrieval_score": 0.75,
        },
        "valid_until": "2020-01-01",  # clearly in the past
        "facts": [
            {"key": "legacy.endpoint", "value": "/v1/data", "type": "string"},
        ],
    }

    errors = check_context_document(expired_doc)

    # Must emit exactly one CONTEXT_EXPIRED warning (not a hard error)
    warning_codes = [e.code for e in errors if "CONTEXT_EXPIRED" in e.code]
    assert len(warning_codes) >= 1, (
        f"Expected CONTEXT_EXPIRED warning, got errors: {[e.code for e in errors]}"
    )
    # The warning must not be treated as a blocking error
    blocking = [e for e in errors if e.severity == "error" and "CONTEXT_EXPIRED" in e.code]
    assert blocking == [], "CONTEXT_EXPIRED should be a warning, not a blocking error"


# ===========================================================================
# Test 8: retrieval_score out of range [0.0, 1.0] raises error (normalized scale)
# ===========================================================================


def test_retrieval_score_out_of_range_raises_error():
    """retrieval_score > 1.0 on normalized_0_1 scale must raise a validation error.

    When score_scale is 'normalized_0_1' (default), retrieval_score must be in [0.0, 1.0].
    Scores on other scales (bm25_raw, dot_product, custom) are not range-checked.
    """
    from nail_lang.fc_context import check_context_document

    doc_invalid_score = {
        "kind": "context",
        "id": "bad_score_ctx_001",
        "source": {
            "document_id": "docs/foo.md",
            "chunk_index": 0,
            "retrieval_score": 1.5,           # out of range for normalized_0_1
            "score_scale": "normalized_0_1",
        },
        "facts": [
            {"key": "foo.bar", "value": "baz", "type": "string"},
        ],
    }

    errors = check_context_document(doc_invalid_score)

    assert len(errors) >= 1
    codes = [e.code for e in errors]
    assert any("SCORE_OUT_OF_RANGE" in code or "retrieval_score" in code.lower() for code in codes), (
        f"Expected a score-out-of-range error, got codes: {codes}"
    )


# ===========================================================================
# Test 9: fact_confidence invalid value raises error
# ===========================================================================


def test_fact_confidence_invalid_value_raises_error():
    """fact_confidence outside [0.0, 1.0] must raise a validation error.

    Per the JSON Schema: fact_confidence is a number with minimum 0.0 and maximum 1.0.
    Both negative values and values > 1.0 must be rejected.
    """
    from nail_lang.fc_context import check_context_document

    doc_invalid_confidence = {
        "kind": "context",
        "id": "bad_confidence_ctx_001",
        "source": {
            "document_id": "docs/foo.md",
            "chunk_index": 0,
            "retrieval_score": 0.8,
        },
        "facts": [
            {
                "key": "foo.bar",
                "value": "baz",
                "type": "string",
                "fact_confidence": 1.5,  # invalid: > 1.0
            },
        ],
    }

    errors = check_context_document(doc_invalid_confidence)

    assert len(errors) >= 1
    codes = [e.code for e in errors]
    assert any(
        "FACT_CONFIDENCE" in code or "out_of_range" in code.lower() for code in codes
    ), f"Expected a fact_confidence validation error, got codes: {codes}"


# ===========================================================================
# Test 10: context kind is additive — does not break existing fn/tool_spec kinds
# ===========================================================================


def test_context_kind_is_additive():
    """Loading context kind documents does not break existing fn/tool_spec kinds.

    kind: context is a purely additive extension per the compatibility spec.
    Existing v1.0 validators and checkers must continue to work when a context
    document is present in the same program / directory.
    """
    from nail_lang.fc_context import check_context_document
    from nail_lang.fc_ir_v2 import check_program, parse_def

    # Existing v1.0 fn definitions (must continue to work unchanged)
    existing_defs = [
        parse_def({"op": "def", "name": "read_config"}),
        parse_def({
            "op": "def",
            "name": "save_report",
            "effects": {"allow": [{"op": "FS:write_file", "delegation": "explicit"}]},
            "grants": ["FS:write_file"],
        }),
    ]
    fn_errors = check_program(existing_defs)
    assert fn_errors == [], f"Existing fn kinds must pass unchanged: {fn_errors}"

    # New context kind document
    ctx_errors = check_context_document(VALID_CONTEXT_DOC)
    assert ctx_errors == [], f"Context document must pass independently: {ctx_errors}"

    # Loading both together must not cause any cross-contamination errors
    # (context docs are transparent to v1.0 program checkers)
    fn_errors_after = check_program(existing_defs)
    assert fn_errors_after == fn_errors, (
        "check_program result must not change when context docs are present"
    )
