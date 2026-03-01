"""Tests for nail_lang.fc_ir_v2 — Delegation-aware Effect Qualifiers (Phase 1).

Issue #107: Implements the Zone of Indifference concept from DeepMind's
"Intelligent AI Delegation" paper as first-class type rules in NAIL.

Spec summary
------------
- ``effects.allow`` elements can be strings (backward-compat) or objects with
  ``{op, reversible, delegation}`` fields.
- ``delegation: "explicit"`` requires the caller to list the op in ``grants``.
- Absence or ``delegation: "implicit"`` does not require grants.
- ``reversible`` is metadata only — it does not affect Phase 1 type rules.
- Matching is exact (no wildcards or prefix matching in Phase 1).
- FC-E010 (ExplicitDelegationViolation) is raised for missing grants.

Run with:
    python3 -m pytest tests/test_delegation_qualifiers.py -v
"""

from __future__ import annotations

import pytest

from nail_lang.fc_ir_v2 import (
    DelegationError,
    EffectQualifier,
    FcDef,
    check_call,
    check_program,
    parse_def,
    parse_effect_qualifier,
    parse_effects,
)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_def(
    name: str,
    allow: list | None = None,
    grants: list | None = None,
    body: list | None = None,
) -> dict:
    """Build a minimal ``op: "def"`` dict for testing."""
    d: dict = {"op": "def", "name": name}
    if allow is not None:
        d["effects"] = {"allow": allow}
    if grants is not None:
        d["grants"] = grants
    if body is not None:
        d["body"] = body
    return d


# ===========================================================================
# 1. parse_effect_qualifier — unit tests
# ===========================================================================


class TestParseEffectQualifier:
    """Unit tests for the effect qualifier parser."""

    def test_string_form_defaults_to_implicit(self):
        """A plain string qualifier defaults to delegation='implicit'."""
        q = parse_effect_qualifier("FS:write_file")
        assert q.op == "FS:write_file"
        assert q.delegation == "implicit"
        assert q.reversible is True

    def test_object_form_explicit_delegation(self):
        """Object form with delegation='explicit' parses correctly."""
        q = parse_effect_qualifier(
            {"op": "FS:write_file", "reversible": False, "delegation": "explicit"}
        )
        assert q.op == "FS:write_file"
        assert q.reversible is False
        assert q.delegation == "explicit"
        assert q.is_explicit() is True

    def test_object_form_implicit_delegation(self):
        """Object form with delegation='implicit' parses correctly."""
        q = parse_effect_qualifier({"op": "NET:fetch", "delegation": "implicit"})
        assert q.op == "NET:fetch"
        assert q.delegation == "implicit"
        assert q.is_explicit() is False

    def test_object_form_defaults_implicit(self):
        """Object form without delegation field defaults to 'implicit'."""
        q = parse_effect_qualifier({"op": "NET:fetch"})
        assert q.delegation == "implicit"
        assert q.is_explicit() is False

    def test_object_form_reversible_default_true(self):
        """Object form without reversible field defaults to True."""
        q = parse_effect_qualifier({"op": "FS:read_file"})
        assert q.reversible is True

    def test_invalid_delegation_value_raises(self):
        """Unknown delegation value must raise DelegationError."""
        with pytest.raises(DelegationError) as exc_info:
            parse_effect_qualifier({"op": "FS:write_file", "delegation": "maybe"})
        assert exc_info.value.code == "FC_PARSE_ERROR"

    def test_missing_op_field_raises(self):
        """Object form without 'op' field must raise DelegationError."""
        with pytest.raises(DelegationError) as exc_info:
            parse_effect_qualifier({"delegation": "explicit"})
        assert exc_info.value.code == "FC_PARSE_ERROR"

    def test_empty_string_op_raises(self):
        """Empty string qualifier must raise DelegationError."""
        with pytest.raises(DelegationError):
            parse_effect_qualifier("")

    def test_non_bool_reversible_raises(self):
        """Non-boolean 'reversible' field must raise DelegationError."""
        with pytest.raises(DelegationError) as exc_info:
            parse_effect_qualifier({"op": "FS:write_file", "reversible": "no"})
        assert exc_info.value.code == "FC_PARSE_ERROR"

    def test_invalid_type_raises(self):
        """Integer qualifier must raise DelegationError."""
        with pytest.raises(DelegationError) as exc_info:
            parse_effect_qualifier(42)
        assert exc_info.value.code == "FC_PARSE_ERROR"


# ===========================================================================
# 2. parse_effects — unit tests
# ===========================================================================


class TestParseEffects:
    """Unit tests for the effects block parser."""

    def test_none_returns_empty(self):
        """None effects field returns an empty list."""
        assert parse_effects(None) == []

    def test_empty_allow_returns_empty(self):
        """Empty allow list returns an empty list of qualifiers."""
        assert parse_effects({"allow": []}) == []

    def test_mixed_string_and_object(self):
        """Mixed string and object elements are all parsed correctly."""
        qualifiers = parse_effects(
            {
                "allow": [
                    "NET:fetch",
                    {"op": "FS:write_file", "delegation": "explicit"},
                ]
            }
        )
        assert len(qualifiers) == 2
        assert qualifiers[0].op == "NET:fetch"
        assert qualifiers[0].delegation == "implicit"
        assert qualifiers[1].op == "FS:write_file"
        assert qualifiers[1].delegation == "explicit"

    def test_non_dict_effects_raises(self):
        """effects field as a list (instead of object) must raise."""
        with pytest.raises(DelegationError) as exc_info:
            parse_effects(["FS:write_file"])
        assert exc_info.value.code == "FC_PARSE_ERROR"

    def test_allow_non_list_raises(self):
        """effects.allow as a string must raise DelegationError."""
        with pytest.raises(DelegationError) as exc_info:
            parse_effects({"allow": "FS:write_file"})
        assert exc_info.value.code == "FC_PARSE_ERROR"


# ===========================================================================
# 3. parse_def — unit tests
# ===========================================================================


class TestParseDef:
    """Unit tests for the function definition parser."""

    def test_minimal_def(self):
        """A minimal def with only op and name parses correctly."""
        fc = parse_def({"op": "def", "name": "hello"})
        assert fc.name == "hello"
        assert fc.qualifiers == []
        assert fc.grants == []
        assert fc.body == []

    def test_def_with_effects_and_grants(self):
        """A def with effects and grants parses all fields."""
        fc = parse_def(
            make_def(
                "save_report",
                allow=[{"op": "FS:write_file", "delegation": "explicit"}],
                grants=["FS:write_file"],
                body=[],
            )
        )
        assert fc.name == "save_report"
        assert len(fc.qualifiers) == 1
        assert fc.qualifiers[0].op == "FS:write_file"
        assert fc.qualifiers[0].is_explicit() is True
        assert fc.grants == ["FS:write_file"]

    def test_wrong_op_raises(self):
        """A dict with op != 'def' must raise DelegationError."""
        with pytest.raises(DelegationError) as exc_info:
            parse_def({"op": "call", "name": "foo"})
        assert exc_info.value.code == "FC_PARSE_ERROR"

    def test_missing_name_raises(self):
        """A def without 'name' must raise DelegationError."""
        with pytest.raises(DelegationError):
            parse_def({"op": "def"})

    def test_grants_non_list_raises(self):
        """grants as a string must raise DelegationError."""
        with pytest.raises(DelegationError):
            parse_def({"op": "def", "name": "f", "grants": "FS:write_file"})

    def test_grants_non_string_item_raises(self):
        """grants with a non-string item must raise DelegationError."""
        with pytest.raises(DelegationError):
            parse_def({"op": "def", "name": "f", "grants": [42]})


# ===========================================================================
# 4. check_call — core delegation type rules
# ===========================================================================


class TestCheckCallExplicitDelegationRequiresGrants:
    """FC-E010 must be raised when callee has explicit delegation but caller lacks grants."""

    def test_explicit_delegation_requires_grants(self):
        """Callee with explicit delegation op: caller without grants → FC-E010.

        This is the primary regression test for Phase 1.
        """
        callee = make_def(
            "write_report",
            allow=[{"op": "FS:write_file", "delegation": "explicit"}],
        )
        caller = make_def(
            "run_pipeline",
            allow=["NET:fetch"],
            grants=[],  # missing FS:write_file
            body=[{"op": "call", "fn": "write_report"}],
        )
        errors = check_call(caller, callee)

        assert len(errors) == 1
        assert errors[0].code == "FC-E010"
        assert "FS:write_file" in errors[0].message
        assert errors[0].op == "FS:write_file"
        assert errors[0].callee == "write_report"

    def test_multiple_explicit_ops_all_must_be_granted(self):
        """All explicit-delegation ops must be in caller's grants — not just one."""
        callee = make_def(
            "callee",
            allow=[
                {"op": "FS:write_file", "delegation": "explicit"},
                {"op": "NET:post", "delegation": "explicit"},
            ],
        )
        caller = make_def(
            "caller",
            grants=["FS:write_file"],  # NET:post is missing
        )
        errors = check_call(caller, callee)

        assert len(errors) == 1
        assert errors[0].code == "FC-E010"
        assert errors[0].op == "NET:post"

    def test_all_explicit_ops_missing_produces_one_error_per_op(self):
        """Each missing explicit op produces a separate FC-E010 error."""
        callee = make_def(
            "callee",
            allow=[
                {"op": "FS:write_file", "delegation": "explicit"},
                {"op": "NET:post", "delegation": "explicit"},
            ],
        )
        caller = make_def("caller", grants=[])
        errors = check_call(caller, callee)

        assert len(errors) == 2
        assert all(e.code == "FC-E010" for e in errors)
        ops = {e.op for e in errors}
        assert ops == {"FS:write_file", "NET:post"}


class TestCheckCallExplicitDelegationWithGrantsPasses:
    """No FC-E010 when caller's grants cover all explicit-delegation ops."""

    def test_explicit_delegation_with_grants_passes(self):
        """Callee with explicit delegation: caller has matching grants → no error."""
        callee = make_def(
            "save_report",
            allow=[{"op": "FS:write_file", "delegation": "explicit"}],
        )
        caller = make_def(
            "run_pipeline",
            grants=["FS:write_file"],  # present
            body=[{"op": "call", "fn": "save_report"}],
        )
        errors = check_call(caller, callee)
        assert errors == []

    def test_extra_grants_beyond_required_are_fine(self):
        """Caller may grant more ops than callee requires — no error."""
        callee = make_def(
            "callee",
            allow=[{"op": "FS:write_file", "delegation": "explicit"}],
        )
        caller = make_def(
            "caller",
            grants=["FS:write_file", "NET:post", "IO:print"],  # more than needed
        )
        errors = check_call(caller, callee)
        assert errors == []

    def test_grants_matching_is_exact(self):
        """Grants matching is exact string equality — a prefix is not sufficient."""
        callee = make_def(
            "callee",
            allow=[{"op": "FS:write_file", "delegation": "explicit"}],
        )
        # "FS:write" is a prefix of "FS:write_file" but must NOT match
        caller = make_def("caller", grants=["FS:write"])
        errors = check_call(caller, callee)
        assert len(errors) == 1
        assert errors[0].code == "FC-E010"

    def test_grants_matching_no_wildcards(self):
        """Wildcard grants (e.g. 'FS:*') are not supported in Phase 1."""
        callee = make_def(
            "callee",
            allow=[{"op": "FS:write_file", "delegation": "explicit"}],
        )
        caller = make_def("caller", grants=["FS:*"])
        errors = check_call(caller, callee)
        # "FS:*" != "FS:write_file" → FC-E010
        assert len(errors) == 1


class TestCheckCallImplicitDelegationNoGrantsNeeded:
    """Implicit delegation ops never require grants from the caller."""

    def test_implicit_delegation_no_grants_needed(self):
        """Callee with implicit delegation: caller needs no grants → no error."""
        callee = make_def(
            "read_config",
            allow=[{"op": "FS:read_file", "delegation": "implicit"}],
        )
        caller = make_def(
            "run_pipeline",
            grants=[],  # empty grants are fine for implicit
            body=[{"op": "call", "fn": "read_config"}],
        )
        errors = check_call(caller, callee)
        assert errors == []

    def test_implicit_is_default_when_delegation_omitted(self):
        """Object form without 'delegation' key defaults to implicit — no grants needed."""
        callee = make_def(
            "callee",
            allow=[{"op": "FS:read_file"}],  # no delegation field
        )
        caller = make_def("caller", grants=[])
        errors = check_call(caller, callee)
        assert errors == []

    def test_mix_implicit_and_explicit_only_explicit_checked(self):
        """Only explicit-delegation ops require grants; implicit ops are always free."""
        callee = make_def(
            "callee",
            allow=[
                {"op": "FS:read_file", "delegation": "implicit"},
                {"op": "FS:write_file", "delegation": "explicit"},
            ],
        )
        caller = make_def("caller", grants=["FS:write_file"])  # only explicit op
        errors = check_call(caller, callee)
        assert errors == []


class TestReversibleIsMetadataOnly:
    """reversible field is purely metadata — it does not affect Phase 1 type rules."""

    def test_reversible_false_without_grants_still_passes_if_implicit(self):
        """reversible=false with implicit delegation: caller needs no grants → no error."""
        callee = make_def(
            "delete_records",
            allow=[{"op": "DB:delete", "reversible": False, "delegation": "implicit"}],
        )
        caller = make_def("caller", grants=[])
        errors = check_call(caller, callee)
        assert errors == []

    def test_reversible_true_with_explicit_still_requires_grants(self):
        """reversible=true with explicit delegation: grants are still required."""
        callee = make_def(
            "write_log",
            allow=[{"op": "FS:write_file", "reversible": True, "delegation": "explicit"}],
        )
        caller = make_def("caller", grants=[])
        errors = check_call(caller, callee)
        assert len(errors) == 1
        assert errors[0].code == "FC-E010"

    def test_reversible_false_with_explicit_still_requires_grants(self):
        """reversible=false with explicit delegation: grants are required (reversible is metadata only).

        This is the primary test for reversible being metadata-only:
        reversible=false adds no extra enforcement beyond delegation='explicit'.
        """
        callee = make_def(
            "write_report",
            allow=[{"op": "FS:write_file", "reversible": False, "delegation": "explicit"}],
        )
        caller = make_def("caller", grants=[])
        errors = check_call(caller, callee)
        assert len(errors) == 1
        assert errors[0].code == "FC-E010"
        assert errors[0].op == "FS:write_file"

    def test_reversible_stored_on_qualifier(self):
        """The reversible flag is preserved on the parsed qualifier object."""
        fc = parse_def(
            make_def(
                "f",
                allow=[{"op": "FS:write_file", "reversible": False, "delegation": "implicit"}],
            )
        )
        assert fc.qualifiers[0].reversible is False


class TestBackwardCompatStringAllow:
    """Legacy string-form allow entries must continue to work unchanged."""

    def test_backward_compat_string_allow(self):
        """String allow entry defaults to implicit delegation — no grants needed."""
        callee = make_def("callee", allow=["FS:write_file"])
        caller = make_def("caller", grants=[])
        errors = check_call(caller, callee)
        assert errors == []

    def test_string_allow_parsed_as_implicit(self):
        """String allow entries are parsed as delegation='implicit'."""
        fc = parse_def(make_def("f", allow=["FS:write_file"]))
        assert len(fc.qualifiers) == 1
        assert fc.qualifiers[0].op == "FS:write_file"
        assert fc.qualifiers[0].delegation == "implicit"
        assert fc.qualifiers[0].is_explicit() is False

    def test_mixed_string_and_object_in_same_allow(self):
        """String and object forms may coexist in the same allow list."""
        callee = make_def(
            "callee",
            allow=[
                "FS:read_file",  # string — implicit
                {"op": "FS:write_file", "delegation": "explicit"},  # object
            ],
        )
        # Only the explicit op requires a grant
        caller_no_grant = make_def("caller", grants=[])
        caller_with_grant = make_def("caller", grants=["FS:write_file"])

        errors_no = check_call(caller_no_grant, callee)
        errors_yes = check_call(caller_with_grant, callee)

        assert len(errors_no) == 1
        assert errors_no[0].op == "FS:write_file"
        assert errors_yes == []

    def test_callee_with_no_effects_at_all_passes(self):
        """Callee with no effects field at all: no grants required."""
        callee = make_def("pure_fn")  # no effects
        caller = make_def("caller", grants=[])
        errors = check_call(caller, callee)
        assert errors == []


# ===========================================================================
# 5. check_program — whole-program delegation checking
# ===========================================================================


class TestCheckProgram:
    """Integration tests for whole-program delegation checking via check_program."""

    def test_program_with_violation(self):
        """Program with a caller that misses grants for explicit-delegation callee → FC-E010."""
        defs = [
            make_def(
                "save_data",
                allow=[{"op": "FS:write_file", "delegation": "explicit"}],
            ),
            make_def(
                "process",
                grants=[],  # should have FS:write_file
                body=[{"op": "call", "fn": "save_data"}],
            ),
        ]
        errors = check_program(defs)
        assert len(errors) == 1
        assert errors[0].code == "FC-E010"

    def test_program_with_correct_grants(self):
        """Program where all explicit-delegation calls are properly granted → no errors."""
        defs = [
            make_def(
                "save_data",
                allow=[{"op": "FS:write_file", "delegation": "explicit"}],
            ),
            make_def(
                "process",
                grants=["FS:write_file"],
                body=[{"op": "call", "fn": "save_data"}],
            ),
        ]
        errors = check_program(defs)
        assert errors == []

    def test_program_with_only_implicit_delegation(self):
        """Program where callee has only implicit delegation: no grants required."""
        defs = [
            make_def("read_config", allow=["FS:read_file"]),  # all implicit
            make_def(
                "app",
                grants=[],
                body=[{"op": "call", "fn": "read_config"}],
            ),
        ]
        errors = check_program(defs)
        assert errors == []

    def test_no_calls_in_body_no_errors(self):
        """Functions with no call statements produce no delegation errors."""
        defs = [
            make_def(
                "standalone",
                allow=[{"op": "FS:write_file", "delegation": "explicit"}],
                grants=["FS:write_file"],
            ),
        ]
        errors = check_program(defs)
        assert errors == []

    def test_call_to_unknown_fn_is_ignored(self):
        """Calls to functions not in the program are silently ignored."""
        defs = [
            make_def(
                "caller",
                grants=[],
                body=[{"op": "call", "fn": "external_fn"}],  # not defined
            ),
        ]
        errors = check_program(defs)
        assert errors == []

    def test_program_backward_compat_string_allow(self):
        """String-form allow entries in a full program do not require grants."""
        defs = [
            make_def("read_db", allow=["DB:query"]),  # string — implicit
            make_def(
                "app",
                grants=[],
                body=[{"op": "call", "fn": "read_db"}],
            ),
        ]
        errors = check_program(defs)
        assert errors == []


# ===========================================================================
# 6. FcDef.explicit_ops() helper
# ===========================================================================


class TestFcDefExplicitOps:
    """Unit tests for FcDef.explicit_ops() computed property."""

    def test_empty_qualifiers(self):
        """No qualifiers → empty explicit ops set."""
        fc = FcDef(name="f")
        assert fc.explicit_ops() == set()

    def test_only_implicit_qualifiers(self):
        """All implicit qualifiers → empty explicit ops set."""
        fc = FcDef(name="f", qualifiers=[EffectQualifier("FS:read", delegation="implicit")])
        assert fc.explicit_ops() == set()

    def test_mixed_qualifiers(self):
        """Mixed qualifiers → only explicit ops are returned."""
        fc = FcDef(
            name="f",
            qualifiers=[
                EffectQualifier("FS:read", delegation="implicit"),
                EffectQualifier("FS:write", delegation="explicit"),
                EffectQualifier("NET:post", delegation="explicit"),
            ],
        )
        assert fc.explicit_ops() == {"FS:write", "NET:post"}


# ===========================================================================
# 7. DelegationError attributes
# ===========================================================================


class TestDelegationError:
    """Unit tests for DelegationError structured attributes."""

    def test_fc_e010_has_correct_fields(self):
        """FC-E010 error carries callee and op attributes."""
        err = DelegationError("msg", code="FC-E010", callee="callee_fn", op="FS:write")
        assert err.code == "FC-E010"
        assert err.callee == "callee_fn"
        assert err.op == "FS:write"
        assert str(err) == "msg"

    def test_to_dict_includes_all_fields(self):
        """to_dict() returns a complete machine-parseable representation."""
        err = DelegationError("msg", code="FC-E010", callee="fn", op="FS:x")
        d = err.to_dict()
        assert d["code"] == "FC-E010"
        assert d["message"] == "msg"
        assert d["callee"] == "fn"
        assert d["op"] == "FS:x"

    def test_to_dict_omits_none_fields(self):
        """to_dict() omits callee and op when they are None."""
        err = DelegationError("parse error", code="FC_PARSE_ERROR")
        d = err.to_dict()
        assert "callee" not in d
        assert "op" not in d

    def test_extra_kwargs_included_in_to_dict(self):
        """Extra keyword arguments are included in to_dict() output."""
        err = DelegationError("msg", code="FC-E010", op="x", caller="my_fn")
        d = err.to_dict()
        assert d["caller"] == "my_fn"
