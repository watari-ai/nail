# NAIL v1.1 Draft Tests - Issue #112: Delegation Audit
"""
NAIL v1.1 — Routing Hints as Declarative Qualifiers Tests (Draft)

These tests define the expected behaviour of routing hint qualifiers.
All tests are skipped until implementation lands (Issue #112).

Spec reference: designs/v1.1/routing-hints.md

To run: pytest tests/test_v11_delegation_audit.py -v
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="v1.1 draft - not implemented yet")

# ---------------------------------------------------------------------------
# Minimal fixtures
# ---------------------------------------------------------------------------

EFFECT_LIGHT_PUBLIC = {
    "kind": "effect",
    "id": "summarize_article",
    "complexity_tier": "light",
    "persona_required": False,
    "privacy_tier": "public",
    "estimated_tokens": 800,
}

EFFECT_HEAVY_INTERNAL = {
    "kind": "effect",
    "id": "generate_personalized_report",
    "complexity_tier": "heavy",
    "persona_required": True,
    "privacy_tier": "internal",
    "estimated_tokens": 4000,
}

EFFECT_CONFIDENTIAL_STRICT = {
    "kind": "effect",
    "id": "analyze_medical_record",
    "complexity_tier": "heavy",
    "persona_required": True,
    "privacy_tier": "confidential",
    "routing": "strict",
    "estimated_tokens": 2000,
}

EFFECT_NET_NO_PRIVACY = {
    "kind": "effect",
    "id": "fetch_and_summarize",
    "effect_type": "NET",
    "complexity_tier": "light",
    "persona_required": False,
    # privacy_tier intentionally absent
}


# ===========================================================================
# Test 1: Valid routing qualifiers on kind:effect pass linting
# ===========================================================================


def test_valid_routing_qualifiers_pass_lint():
    """A well-formed effect with all routing qualifiers passes nail fc check with no warnings.

    Spec: Example 1 — complexity_tier: light, persona_required: false, privacy_tier: public
    produces no linting warnings.
    """
    from nail_lang.routing import lint_routing_qualifiers

    result = lint_routing_qualifiers(EFFECT_LIGHT_PUBLIC)

    assert result.is_valid
    assert len(result.errors) == 0
    assert len(result.warnings) == 0


# ===========================================================================
# Test 2: NET effect without privacy_tier emits ROUTING_PRIVACY_MISSING
# ===========================================================================


def test_net_effect_without_privacy_tier_emits_warning():
    """An effect with effect_type: NET and no privacy_tier emits ROUTING_PRIVACY_MISSING.

    Spec: ROUTING_PRIVACY_MISSING — Effect has a NET effect type AND privacy_tier not set.
    Message: "privacy_tier not set on NET effect; data residency is unspecified"
    """
    from nail_lang.routing import lint_routing_qualifiers

    result = lint_routing_qualifiers(EFFECT_NET_NO_PRIVACY)

    warning_codes = [w.code for w in result.warnings]
    assert "ROUTING_PRIVACY_MISSING" in warning_codes


# ===========================================================================
# Test 3: persona_required without privacy_tier emits ROUTING_PERSONA_NO_PRIVACY
# ===========================================================================


def test_persona_required_without_privacy_tier_emits_warning():
    """persona_required: true without privacy_tier emits ROUTING_PERSONA_NO_PRIVACY.

    Spec: ROUTING_PERSONA_NO_PRIVACY — persona_required is true but privacy_tier absent.
    """
    from nail_lang.routing import lint_routing_qualifiers

    effect = {
        "kind": "effect",
        "id": "user_greeting",
        "persona_required": True,
        "complexity_tier": "light",
        # privacy_tier absent
    }

    result = lint_routing_qualifiers(effect)

    warning_codes = [w.code for w in result.warnings]
    assert "ROUTING_PERSONA_NO_PRIVACY" in warning_codes


# ===========================================================================
# Test 4: confidential + data_visibility:pass emits ROUTING_PRIVACY_LEAK
# ===========================================================================


def test_confidential_with_pass_visibility_emits_warning():
    """privacy_tier: confidential + data_visibility: pass emits ROUTING_PRIVACY_LEAK.

    Spec: ROUTING_PRIVACY_LEAK — confidential data may transit a remote layer via pass.
    """
    from nail_lang.routing import lint_routing_qualifiers

    effect = {
        "kind": "effect",
        "id": "confidential_forward",
        "privacy_tier": "confidential",
        "data_visibility": "pass",
        "complexity_tier": "light",
    }

    result = lint_routing_qualifiers(effect)

    warning_codes = [w.code for w in result.warnings]
    assert "ROUTING_PRIVACY_LEAK" in warning_codes


# ===========================================================================
# Test 5: heavy + max_delegation_depth:0 emits ROUTING_DEPTH_CONFLICT info
# ===========================================================================


def test_heavy_with_zero_delegation_depth_emits_info():
    """complexity_tier: heavy + max_delegation_depth: 0 emits ROUTING_DEPTH_CONFLICT.

    Spec: ROUTING_DEPTH_CONFLICT — heavy effects typically need delegation.
    Severity: Info (not error).
    """
    from nail_lang.routing import lint_routing_qualifiers

    effect = {
        "kind": "effect",
        "id": "heavy_no_delegate",
        "complexity_tier": "heavy",
        "privacy_tier": "internal",
        "max_delegation_depth": 0,
    }

    result = lint_routing_qualifiers(effect)

    info_codes = [n.code for n in result.infos]
    assert "ROUTING_DEPTH_CONFLICT" in info_codes


# ===========================================================================
# Test 6: persona_required + privacy_tier:public emits ROUTING_PERSONA_PUBLIC advisory
# ===========================================================================


def test_persona_required_with_public_tier_emits_advisory():
    """persona_required: true + privacy_tier: public emits ROUTING_PERSONA_PUBLIC advisory.

    Spec: ROUTING_PERSONA_PUBLIC — personal context used in a public-tier effect.
    Severity: Advisory.
    """
    from nail_lang.routing import lint_routing_qualifiers

    effect = {
        "kind": "effect",
        "id": "persona_public_effect",
        "persona_required": True,
        "privacy_tier": "public",
        "complexity_tier": "light",
    }

    result = lint_routing_qualifiers(effect)

    advisory_codes = [a.code for a in result.advisories]
    assert "ROUTING_PERSONA_PUBLIC" in advisory_codes


# ===========================================================================
# Test 7: routing:strict on confidential effect emits UNIMPLEMENTED_STRICT_ROUTING (Phase A)
# ===========================================================================


def test_routing_strict_emits_unimplemented_info_in_phase_a():
    """routing: strict in Phase A emits UNIMPLEMENTED_STRICT_ROUTING informational note.

    Spec: "In Phase A, routing: strict is parsed and stored but has no runtime enforcement.
    nail fc check will emit UNIMPLEMENTED_STRICT_ROUTING when it encounters routing: strict."
    """
    from nail_lang.routing import lint_routing_qualifiers

    result = lint_routing_qualifiers(EFFECT_CONFIDENTIAL_STRICT)

    info_codes = [n.code for n in result.infos]
    assert "UNIMPLEMENTED_STRICT_ROUTING" in info_codes


# ===========================================================================
# Test 8: heavy + confidential + strict raises ROUTING_STRICT_CONFLICT error
# ===========================================================================


def test_heavy_confidential_strict_raises_conflict_error():
    """complexity_tier: heavy + privacy_tier: confidential + routing: strict is invalid.

    Spec: ROUTING_STRICT_CONFLICT — strict routing constraints are unsatisfiable:
    heavy requires cloud, confidential forbids cloud → no legal route exists.
    """
    from nail_lang.routing import RoutingStrictConflictError, lint_routing_qualifiers

    contradictory_effect = {
        "kind": "effect",
        "id": "impossible_route",
        "complexity_tier": "heavy",
        "privacy_tier": "confidential",
        "routing": "strict",
    }

    result = lint_routing_qualifiers(contradictory_effect)

    error_codes = [e.code for e in result.errors]
    assert "ROUTING_STRICT_CONFLICT" in error_codes


# ===========================================================================
# Test 9: complexity_tier accepts only "light" or "heavy"
# ===========================================================================


def test_complexity_tier_invalid_value_raises_schema_error():
    """complexity_tier must be 'light' or 'heavy'. Invalid values raise a schema error.

    Spec: complexity_tier: "light" | "heavy" (enum).
    """
    from nail_lang.routing import RoutingSchemaError, lint_routing_qualifiers

    effect_bad_tier = {
        "kind": "effect",
        "id": "bad_tier",
        "complexity_tier": "medium",  # invalid
        "privacy_tier": "public",
    }

    with pytest.raises(RoutingSchemaError) as exc_info:
        lint_routing_qualifiers(effect_bad_tier)

    err = exc_info.value
    assert "complexity_tier" in err.field


# ===========================================================================
# Test 10: privacy_tier accepts only "public", "internal", "confidential"
# ===========================================================================


def test_privacy_tier_invalid_value_raises_schema_error():
    """privacy_tier must be 'public', 'internal', or 'confidential'. Others raise error.

    Spec: privacy_tier: "public" | "internal" | "confidential" (enum).
    """
    from nail_lang.routing import RoutingSchemaError, lint_routing_qualifiers

    effect_bad_privacy = {
        "kind": "effect",
        "id": "bad_privacy",
        "complexity_tier": "light",
        "privacy_tier": "secret",  # invalid
    }

    with pytest.raises(RoutingSchemaError) as exc_info:
        lint_routing_qualifiers(effect_bad_privacy)

    err = exc_info.value
    assert "privacy_tier" in err.field


# ===========================================================================
# Test 11: estimated_tokens is optional; when absent, no error is raised
# ===========================================================================


def test_estimated_tokens_is_optional():
    """estimated_tokens is an optional field. Its absence must not produce any error or warning.

    Spec: estimated_tokens is optional. "There is no validation of the declared value
    against actual usage in Phase A."
    """
    from nail_lang.routing import lint_routing_qualifiers

    effect_no_tokens = {
        "kind": "effect",
        "id": "no_token_hint",
        "complexity_tier": "light",
        "privacy_tier": "public",
        "persona_required": False,
        # estimated_tokens absent
    }

    result = lint_routing_qualifiers(effect_no_tokens)

    assert result.is_valid
    error_and_warning_codes = [i.code for i in result.errors + result.warnings]
    assert not any("TOKEN" in c for c in error_and_warning_codes)


# ===========================================================================
# Test 12: Files without routing qualifiers behave identically to v1.0 (compat)
# ===========================================================================


def test_effect_without_routing_qualifiers_is_backward_compatible():
    """An effect with no routing qualifiers passes without any routing-related diagnostics.

    Spec: Compatibility section — "Files without routing qualifiers behave identically
    to v1.0. nail fc check only emits new warnings; it does not break existing passing checks."
    """
    from nail_lang.routing import lint_routing_qualifiers

    v10_effect = {
        "kind": "effect",
        "id": "legacy_effect",
        "effects": {"allow": ["NET"]},
        # no routing qualifiers
    }

    result = lint_routing_qualifiers(v10_effect)

    routing_codes = [
        i.code for i in result.errors + result.warnings + result.infos
        if i.code.startswith("ROUTING_") or "STRICT" in i.code
    ]
    assert len(routing_codes) == 0, (
        f"v1.0 file should produce no routing diagnostics, got: {routing_codes}"
    )
