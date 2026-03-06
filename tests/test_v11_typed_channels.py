# NAIL v1.1 Draft Tests - Issue #110: Typed Channels
"""
NAIL v1.1 — Multi-Layer LLM Interface Contracts Tests (Draft)

These tests define the expected behaviour of multi-layer layer contracts.
All tests are skipped until implementation lands (Issue #110).

Spec reference: designs/v1.1/multi-layer-contracts.md

To run: pytest tests/test_v11_typed_channels.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="v1.1 draft - not implemented yet")

# ---------------------------------------------------------------------------
# Minimal fixtures
# ---------------------------------------------------------------------------

LAYER_L1 = {
    "layer": {
        "id": "l1_orchestrator",
        "level": 1,
        "locality": "cloud",
        "model_hint": "claude-3-5",
        "delegates_to": ["l2_specialist"],
    },
    "accepts": [
        {"name": "user_query", "type": "string", "required": True},
        {"name": "session_token", "type": "string", "required": True, "visibility": "retain"},
    ],
    "returns": [
        {"name": "final_answer", "type": "string"},
    ],
    "effects": {
        "allow": ["NET", "KNOWLEDGE"],
        "deny": ["FS_WRITE", "EXEC"],
    },
}

LAYER_L2 = {
    "layer": {
        "id": "l2_specialist",
        "level": 2,
        "locality": "cloud",
        "delegates_to": ["l3_local_embed"],
    },
    "accepts": [
        {"name": "user_query", "type": "string", "required": True},
    ],
    "returns": [
        {"name": "structured_answer", "type": "object"},
    ],
    "effects": {
        "allow": ["KNOWLEDGE", "NET"],
        "deny": ["PERSONA", "FS_WRITE"],
    },
}

LAYER_L3 = {
    "layer": {
        "id": "l3_local_embed",
        "level": 3,
        "locality": "local",
        "delegates_to": [],
    },
    "accepts": [
        {"name": "text", "type": "string", "required": True},
    ],
    "returns": [
        {"name": "embedding", "type": "list"},
        {"name": "label", "type": "string"},
    ],
    "effects": {
        "allow": ["KNOWLEDGE"],
        "deny": ["NET", "PERSONA", "FS_WRITE", "EXEC"],
    },
}


# ===========================================================================
# Test 1: Valid layer declaration schema is accepted
# ===========================================================================


def test_layer_declaration_valid_schema():
    """A well-formed layer block with all required fields passes schema validation.

    Required fields: id (string), level (int >= 1), locality (enum).
    Optional fields: model_hint, delegates_to.

    Spec: Layer Declaration section — all required fields must be present.
    """
    from nail_lang.layer import validate_layer

    result = validate_layer(LAYER_L1["layer"])

    assert result.is_valid
    assert result.layer_id == "l1_orchestrator"
    assert result.level == 1
    assert result.locality == "cloud"


# ===========================================================================
# Test 2: Layer missing required field raises LayerSchemaError
# ===========================================================================


def test_layer_missing_required_field_raises_error():
    """A layer block missing a required field (e.g. level) raises LayerSchemaError.

    Spec: Fields id, level, locality are all required.
    """
    from nail_lang.layer import LayerSchemaError, validate_layer

    incomplete_layer = {
        "id": "broken_layer",
        # level intentionally missing
        "locality": "cloud",
    }

    with pytest.raises(LayerSchemaError) as exc_info:
        validate_layer(incomplete_layer)

    err = exc_info.value
    assert "level" in err.missing_fields


# ===========================================================================
# Test 3: delegates_to allowlist — unlisted target raises DELEGATION_UNLISTED
# ===========================================================================


def test_delegation_to_unlisted_layer_raises_error():
    """Delegating to a layer not in delegates_to must raise DelegationUnlistedError.

    Spec: Rule 1 — A layer may only delegate to layers explicitly listed in delegates_to.
    """
    from nail_lang.layer import DelegationUnlistedError, delegate_to_layer

    with pytest.raises(DelegationUnlistedError) as exc_info:
        delegate_to_layer(
            source_layer=LAYER_L1["layer"],
            target_layer_id="unknown_layer",
        )

    err = exc_info.value
    assert err.code == "DELEGATION_UNLISTED"
    assert err.source_id == "l1_orchestrator"
    assert err.target_id == "unknown_layer"


# ===========================================================================
# Test 4: delegates_to allowlist — listed target is permitted
# ===========================================================================


def test_delegation_to_listed_layer_is_permitted():
    """Delegating to a layer listed in delegates_to succeeds without error.

    Spec: Rule 1 — Delegation to an explicitly listed layer is allowed.
    """
    from nail_lang.layer import delegate_to_layer

    result = delegate_to_layer(
        source_layer=LAYER_L1["layer"],
        target_layer_id="l2_specialist",
    )

    assert result.allowed is True
    assert result.target_id == "l2_specialist"


# ===========================================================================
# Test 5: Effect monotonicity — sub-layer effect superset raises EFFECT_ESCALATION
# ===========================================================================


def test_effect_escalation_raises_when_sublayer_has_extra_effects():
    """Sub-layer effects.allow must not exceed parent's effects.allow.

    Spec: Rule 2 — Effect monotonicity. If L2.effects.allow is not a subset of
    L1.effects.allow, checker emits EFFECT_ESCALATION.

    L1 allows {NET, KNOWLEDGE}; L2_bad allows {NET, KNOWLEDGE, FS_WRITE} → escalation.
    """
    from nail_lang.layer import EffectEscalationError, check_effect_monotonicity

    l2_bad = dict(LAYER_L2)
    l2_bad["effects"] = {"allow": ["KNOWLEDGE", "NET", "FS_WRITE"]}

    with pytest.raises(EffectEscalationError) as exc_info:
        check_effect_monotonicity(
            parent_layer=LAYER_L1,
            child_layer=l2_bad,
        )

    err = exc_info.value
    assert err.code == "EFFECT_ESCALATION"
    assert "FS_WRITE" in err.escalated_effects


# ===========================================================================
# Test 6: Effect monotonicity — valid sub-layer (subset) passes
# ===========================================================================


def test_effect_monotonicity_passes_when_sublayer_is_subset():
    """Sub-layer effects.allow that is a subset of parent's passes the check.

    Spec: Rule 2 — L2.effects.allow ⊆ L1.effects.allow is valid.
    """
    from nail_lang.layer import check_effect_monotonicity

    result = check_effect_monotonicity(
        parent_layer=LAYER_L1,
        child_layer=LAYER_L2,
    )

    assert result.is_valid


# ===========================================================================
# Test 7: retain field must not appear in sub-layer invocation payload
# ===========================================================================


def test_retain_field_not_forwarded_to_sublayer_raises_leak():
    """A field marked visibility: retain must not appear in the sub-layer invocation payload.

    Spec: Rule 3 — Retain field isolation. Checker emits DELEGATION_LEAK if a retain
    field is observed in a downstream delegation call.
    """
    from nail_lang.layer import DelegationLeakError, check_delegation_payload

    leaked_payload = {
        "user_query": "What is NAIL?",
        "session_token": "secret-token-123",  # retain field leaked
    }

    with pytest.raises(DelegationLeakError) as exc_info:
        check_delegation_payload(
            source_layer=LAYER_L1,
            target_layer=LAYER_L2,
            payload=leaked_payload,
        )

    err = exc_info.value
    assert err.code == "DELEGATION_LEAK"
    assert "session_token" in err.leaked_fields


# ===========================================================================
# Test 8: Valid payload without retain fields passes delegation check
# ===========================================================================


def test_valid_payload_without_retain_fields_passes():
    """A payload that omits retain fields is accepted without DELEGATION_LEAK.

    Spec: Rule 3 — If no retain field appears in the payload, check passes.
    """
    from nail_lang.layer import check_delegation_payload

    valid_payload = {
        "user_query": "What is NAIL?",
    }

    result = check_delegation_payload(
        source_layer=LAYER_L1,
        target_layer=LAYER_L2,
        payload=valid_payload,
    )

    assert result.is_valid


# ===========================================================================
# Test 9: Layer level inversion emits LAYER_LEVEL_INVERSION warning
# ===========================================================================


def test_layer_level_inversion_emits_warning():
    """A higher-level (deeper) layer delegating to a lower-level layer emits a warning.

    Spec: LAYER_LEVEL_INVERSION warning — higher level number delegating to a lower
    level number is semantically inverted (L3 → L1 is unusual).
    """
    from nail_lang.layer import check_layer_level_order

    l3_delegates_up = dict(LAYER_L3["layer"])
    l3_delegates_up["delegates_to"] = ["l1_orchestrator"]

    result = check_layer_level_order(
        source_layer=l3_delegates_up,
        target_layer=LAYER_L1["layer"],
    )

    assert not result.is_error
    assert any(w.code == "LAYER_LEVEL_INVERSION" for w in result.warnings)


# ===========================================================================
# Test 10: Delegation cycle detection raises DELEGATION_CYCLE
# ===========================================================================


def test_delegation_cycle_raises_error():
    """A delegation graph that contains a cycle raises DelegationCycleError.

    Spec: DELEGATION_CYCLE — delegation graph must be a DAG. Cycles are errors.

    Example: L1 → L2, L2 → L1 (mutual delegation).
    """
    from nail_lang.layer import DelegationCycleError, validate_delegation_graph

    cyclic_graph = {
        "l1": {"delegates_to": ["l2"]},
        "l2": {"delegates_to": ["l1"]},
    }

    with pytest.raises(DelegationCycleError) as exc_info:
        validate_delegation_graph(cyclic_graph)

    err = exc_info.value
    assert err.code == "DELEGATION_CYCLE"
    assert set(err.cycle) == {"l1", "l2"}


# ===========================================================================
# Test 11: File without layer block is backward compatible (v1.0)
# ===========================================================================


def test_file_without_layer_block_is_backward_compatible():
    """A NAIL file without a layer block behaves as v1.0 (no layer-contract checks applied).

    Spec: Compatibility section — "Files without a layer block behave identically to v1.0."
    """
    from nail_lang.layer import parse_layer_contract

    nail_v10_doc = {
        "kind": "effect",
        "id": "legacy_effect",
        "effects": {"allow": ["NET"]},
    }

    contract = parse_layer_contract(nail_v10_doc)

    assert contract is None or contract.is_legacy_compat


# ===========================================================================
# Test 12: effects deny overrides allow when same effect appears in both
# ===========================================================================


def test_deny_takes_precedence_over_allow():
    """If an effect appears in both effects.allow and effects.deny, deny wins.

    Spec: "If the same effect appears in both effects.allow and effects.deny,
    deny takes precedence."
    """
    from nail_lang.layer import resolve_effective_effects

    layer_with_conflict = {
        "layer": {"id": "conflict_layer", "level": 2, "locality": "cloud"},
        "effects": {
            "allow": ["NET", "FS_WRITE"],
            "deny": ["FS_WRITE"],
        },
    }

    policy = resolve_effective_effects(layer_with_conflict)

    assert "FS_WRITE" not in policy.effective_allow
    assert "NET" in policy.effective_allow
