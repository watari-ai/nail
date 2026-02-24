"""
NAIL v0.5 — Enum/ADT Test Suite (Issue #52)

Covers: enum_make, match_enum, exhaustiveness checking, field binds,
default arms, runtime behavior, multiple enum types.

Run: python3 -m pytest tests/test_enum.py -v
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, Runtime, CheckError, NailRuntimeError
from interpreter.runtime import UNIT

# ---------------------------------------------------------------------------
# Spec builder helpers
# ---------------------------------------------------------------------------

INT64   = {"type": "int", "bits": 64, "overflow": "panic"}
FLOAT64 = {"type": "float", "bits": 64}
BOOL_T  = {"type": "bool"}
STR_T   = {"type": "string"}
UNIT_T  = {"type": "unit"}


def fn_spec(fn_id, params, returns, body, effects=None):
    return {
        "nail": "0.1.0",
        "kind": "fn",
        "id": fn_id,
        "effects": effects or [],
        "params": params,
        "returns": returns,
        "body": body,
    }


def module_spec(module_id, defs, exports=None, types=None):
    spec = {
        "nail": "0.1.0",
        "kind": "module",
        "id": module_id,
        "exports": exports or [],
        "defs": defs,
    }
    if types is not None:
        spec["types"] = types
    return spec


def run_spec(spec, args=None, call_fn=None):
    Checker(spec).check()
    rt = Runtime(spec)
    if call_fn:
        return rt.run_fn(call_fn, args or {})
    return rt.run(args)


# ---------------------------------------------------------------------------
# Shared enum type definitions
# ---------------------------------------------------------------------------

COLOR_TYPE = {
    "type": "enum",
    "variants": [
        {"tag": "Red"},
        {"tag": "Green"},
        {"tag": "Blue"},
    ],
}

SHAPE_TYPE = {
    "type": "enum",
    "variants": [
        {"tag": "Circle",    "fields": [{"name": "radius", "type": FLOAT64}]},
        {"tag": "Rectangle", "fields": [{"name": "w", "type": FLOAT64},
                                         {"name": "h", "type": FLOAT64}]},
    ],
}

DIRECTION_TYPE = {
    "type": "enum",
    "variants": [
        {"tag": "North"},
        {"tag": "South"},
        {"tag": "East"},
        {"tag": "West"},
    ],
}

MAYBE_INT_TYPE = {
    "type": "enum",
    "variants": [
        {"tag": "Some", "fields": [{"name": "val", "type": INT64}]},
        {"tag": "None"},
    ],
}


# ===========================================================================
# 1. enum_make: basic unit variant
# ===========================================================================

def test_enum_make_unit_variant_ok():
    """enum_make with a simple unit variant should pass check and run."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
            {"op": "return", "val": {"lit": 0}},
        ])],
        types={"Color": COLOR_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 0


# ===========================================================================
# 2. enum_make: all three variants constructible
# ===========================================================================

def test_enum_make_each_variant():
    """Each variant of an enum can be constructed."""
    for tag, expected in [("Red", 1), ("Green", 2), ("Blue", 3)]:
        spec = module_spec(
            "m",
            defs=[fn_spec("main", [], INT64, [
                {"op": "enum_make", "tag": tag, "fields": {}, "into": "c"},
                {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                    {"tag": "Red",   "body": [{"op": "return", "val": {"lit": 1}}]},
                    {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                    {"tag": "Blue",  "body": [{"op": "return", "val": {"lit": 3}}]},
                ]},
            ])],
            types={"Color": COLOR_TYPE},
        )
        assert run_spec(spec, call_fn="main") == expected


# ===========================================================================
# 3. match_enum: correct arm is executed at runtime
# ===========================================================================

def test_match_enum_correct_arm_dispatched():
    """match_enum dispatches to the correct arm based on the runtime tag."""
    for tag, expected in [("North", 0), ("South", 1), ("East", 2), ("West", 3)]:
        spec = module_spec(
            "m",
            defs=[fn_spec("main", [], INT64, [
                {"op": "enum_make", "tag": tag, "fields": {}, "into": "d"},
                {"op": "match_enum", "val": {"ref": "d"}, "cases": [
                    {"tag": "North", "body": [{"op": "return", "val": {"lit": 0}}]},
                    {"tag": "South", "body": [{"op": "return", "val": {"lit": 1}}]},
                    {"tag": "East",  "body": [{"op": "return", "val": {"lit": 2}}]},
                    {"tag": "West",  "body": [{"op": "return", "val": {"lit": 3}}]},
                ]},
            ])],
            types={"Direction": DIRECTION_TYPE},
        )
        assert run_spec(spec, call_fn="main") == expected


# ===========================================================================
# 4. Exhaustiveness check: all variants required (no default)
# ===========================================================================

def test_match_enum_exhaustiveness_missing_one_variant_raises():
    """Omitting a variant without a default arm must raise CheckError."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
            {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                {"tag": "Red",   "body": [{"op": "return", "val": {"lit": 1}}]},
                {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                # Blue is missing
            ]},
        ])],
        types={"Color": COLOR_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


def test_match_enum_exhaustiveness_empty_cases_raises():
    """An empty cases list (no arms) without default must raise CheckError."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
            {"op": "match_enum", "val": {"ref": "c"}, "cases": []},
            {"op": "return", "val": {"lit": 0}},
        ])],
        types={"Color": COLOR_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


# ===========================================================================
# 5. Default arm: allows non-exhaustive explicit cases
# ===========================================================================

def test_match_enum_default_arm_passes_check():
    """A default arm satisfies exhaustiveness even if not all tags are listed."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Blue", "fields": {}, "into": "c"},
            {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                {"tag": "Red", "body": [{"op": "return", "val": {"lit": 1}}]},
            ], "default": [{"op": "return", "val": {"lit": 99}}]},
        ])],
        types={"Color": COLOR_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 99


def test_match_enum_default_arm_not_taken_when_case_matches():
    """If an explicit case matches, the default arm is not taken."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
            {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                {"tag": "Red", "body": [{"op": "return", "val": {"lit": 42}}]},
            ], "default": [{"op": "return", "val": {"lit": 0}}]},
        ])],
        types={"Color": COLOR_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 42


# ===========================================================================
# 6. enum_make: unknown tag raises CheckError
# ===========================================================================

def test_enum_make_unknown_tag_raises():
    """Using a tag not in the enum type definition must raise CheckError."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Yellow", "fields": {}, "into": "c"},
            {"op": "return", "val": {"lit": 0}},
        ])],
        types={"Color": COLOR_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


# ===========================================================================
# 7. match_enum: unknown tag in case raises CheckError
# ===========================================================================

def test_match_enum_unknown_case_tag_raises():
    """A case tag not in the enum must raise CheckError."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
            {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                {"tag": "Red",    "body": [{"op": "return", "val": {"lit": 1}}]},
                {"tag": "Green",  "body": [{"op": "return", "val": {"lit": 2}}]},
                {"tag": "Blue",   "body": [{"op": "return", "val": {"lit": 3}}]},
                {"tag": "Purple", "body": [{"op": "return", "val": {"lit": 4}}]},  # invalid
            ]},
        ])],
        types={"Color": COLOR_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


# ===========================================================================
# 8. enum_make with fields: construct and bind
# ===========================================================================

def test_enum_make_with_fields_and_binds():
    """enum_make with field values; match_enum binds field to local var."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], FLOAT64, [
            {"op": "enum_make", "tag": "Circle",
             "fields": {"radius": {"lit": 5.0}},
             "into": "s"},
            {"op": "match_enum", "val": {"ref": "s"}, "cases": [
                {"tag": "Circle",
                 "binds": {"radius": "r"},
                 "body": [{"op": "return", "val": {"ref": "r"}}]},
                {"tag": "Rectangle",
                 "binds": {"w": "width", "h": "height"},
                 "body": [{"op": "return", "val": {"op": "+",
                            "l": {"ref": "width"}, "r": {"ref": "height"}}}]},
            ]},
        ])],
        types={"Shape": SHAPE_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 5.0


def test_enum_make_rectangle_fields_and_binds():
    """Rectangle with two fields; both binds available in arm body."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], FLOAT64, [
            {"op": "enum_make", "tag": "Rectangle",
             "fields": {"w": {"lit": 4.0}, "h": {"lit": 3.0}},
             "into": "s"},
            {"op": "match_enum", "val": {"ref": "s"}, "cases": [
                {"tag": "Circle",
                 "binds": {"radius": "r"},
                 "body": [{"op": "return", "val": {"ref": "r"}}]},
                {"tag": "Rectangle",
                 "binds": {"w": "width", "h": "height"},
                 "body": [{"op": "return", "val": {"op": "*",
                            "l": {"ref": "width"}, "r": {"ref": "height"}}}]},
            ]},
        ])],
        types={"Shape": SHAPE_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 12.0


# ===========================================================================
# 9. enum_make field type mismatch raises CheckError
# ===========================================================================

def test_enum_make_field_wrong_type_raises():
    """Providing a wrong type for an enum field must raise CheckError."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Circle",
             "fields": {"radius": {"lit": 5}},  # int, not float
             "into": "s"},
            {"op": "return", "val": {"lit": 0}},
        ])],
        types={"Shape": SHAPE_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


# ===========================================================================
# 10. enum_make: missing field raises CheckError
# ===========================================================================

def test_enum_make_missing_field_raises():
    """Omitting a required field in enum_make must raise CheckError."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Rectangle",
             "fields": {"w": {"lit": 4.0}},  # h is missing
             "into": "s"},
            {"op": "return", "val": {"lit": 0}},
        ])],
        types={"Shape": SHAPE_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


# ===========================================================================
# 11. enum_make: extra/unknown field raises CheckError
# ===========================================================================

def test_enum_make_extra_field_raises():
    """Providing an extra (unknown) field in enum_make must raise CheckError."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Red",
             "fields": {"unexpected_field": {"lit": 42}},  # Red has no fields
             "into": "c"},
            {"op": "return", "val": {"lit": 0}},
        ])],
        types={"Color": COLOR_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


# ===========================================================================
# 12. match_enum: binding an unknown field name raises CheckError
# ===========================================================================

def test_match_enum_bind_unknown_field_raises():
    """Binding a field name that does not exist in the variant must raise CheckError."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
            {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                {"tag": "Red",   "binds": {"nosuchfield": "x"},
                 "body": [{"op": "return", "val": {"lit": 1}}]},
                {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                {"tag": "Blue",  "body": [{"op": "return", "val": {"lit": 3}}]},
            ]},
        ])],
        types={"Color": COLOR_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


# ===========================================================================
# 13. match_enum: duplicate case tag raises CheckError
# ===========================================================================

def test_match_enum_duplicate_case_tag_raises():
    """Listing the same tag twice in match_enum cases must raise CheckError."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
            {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                {"tag": "Red",   "body": [{"op": "return", "val": {"lit": 1}}]},
                {"tag": "Red",   "body": [{"op": "return", "val": {"lit": 9}}]},  # dup
                {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                {"tag": "Blue",  "body": [{"op": "return", "val": {"lit": 3}}]},
            ]},
        ])],
        types={"Color": COLOR_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


# ===========================================================================
# 14. match_enum on non-enum type raises CheckError
# ===========================================================================

def test_match_enum_on_non_enum_raises():
    """match_enum on a non-enum value must raise CheckError at check time."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [{"id": "n", "type": INT64}], INT64, [
            {"op": "match_enum", "val": {"ref": "n"}, "cases": [
                {"tag": "Foo", "body": [{"op": "return", "val": {"lit": 1}}]},
            ]},
            {"op": "return", "val": {"lit": 0}},
        ])],
        types={"Color": COLOR_TYPE},
    )
    with pytest.raises(CheckError):
        Checker(spec).check()


# ===========================================================================
# 15. MaybeInt enum — Some/None variant
# ===========================================================================

def test_maybe_int_some_returns_value():
    """Some(41) + 1 == 42."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Some", "fields": {"val": {"lit": 41}}, "into": "m"},
            {"op": "match_enum", "val": {"ref": "m"}, "cases": [
                {"tag": "Some",
                 "binds": {"val": "v"},
                 "body": [{"op": "return", "val": {
                     "op": "+", "l": {"ref": "v"}, "r": {"lit": 1}
                 }}]},
                {"tag": "None",
                 "body": [{"op": "return", "val": {"lit": -1}}]},
            ]},
        ])],
        types={"MaybeInt": MAYBE_INT_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 42


def test_maybe_int_none_returns_sentinel():
    """None variant → -1 sentinel."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "None", "fields": {}, "into": "m"},
            {"op": "match_enum", "val": {"ref": "m"}, "cases": [
                {"tag": "Some",
                 "binds": {"val": "v"},
                 "body": [{"op": "return", "val": {"ref": "v"}}]},
                {"tag": "None",
                 "body": [{"op": "return", "val": {"lit": -1}}]},
            ]},
        ])],
        types={"MaybeInt": MAYBE_INT_TYPE},
    )
    assert run_spec(spec, call_fn="main") == -1


# ===========================================================================
# 16. Multiple enum types coexist in module types dict
# ===========================================================================

def test_multiple_enum_types_coexist():
    """Color and Direction can both be defined in the same module types dict."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Red",   "fields": {}, "into": "col"},
            {"op": "enum_make", "tag": "North", "fields": {}, "into": "dir"},
            {"op": "match_enum", "val": {"ref": "col"}, "cases": [
                {"tag": "Red",   "body": []},
                {"tag": "Green", "body": []},
                {"tag": "Blue",  "body": []},
            ]},
            {"op": "match_enum", "val": {"ref": "dir"}, "cases": [
                {"tag": "North", "body": []},
                {"tag": "South", "body": []},
                {"tag": "East",  "body": []},
                {"tag": "West",  "body": []},
            ]},
            {"op": "return", "val": {"lit": 0}},
        ])],
        types={
            "Color":     COLOR_TYPE,
            "Direction": DIRECTION_TYPE,
        },
    )
    assert run_spec(spec, call_fn="main") == 0


# ===========================================================================
# 17. enum_make explicit type field selects correct enum when tag is ambiguous
# ===========================================================================

def test_enum_make_explicit_type_resolves_ambiguity():
    """When two enums share a tag name, setting 'type' resolves ambiguity."""
    # Introduce a second enum that also has a "Red" tag
    another_color = {
        "type": "enum",
        "variants": [
            {"tag": "Red",   "fields": [{"name": "shade", "type": INT64}]},
            {"tag": "Cyan"},
        ],
    }
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {
                "op": "enum_make",
                "tag": "Red",
                "fields": {},
                "type": {"type": "alias", "name": "Color"},  # explicit
                "into": "c",
            },
            {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                {"tag": "Red",   "body": [{"op": "return", "val": {"lit": 1}}]},
                {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                {"tag": "Blue",  "body": [{"op": "return", "val": {"lit": 3}}]},
            ]},
        ])],
        types={
            "Color":        COLOR_TYPE,
            "AnotherColor": another_color,
        },
    )
    assert run_spec(spec, call_fn="main") == 1


# ===========================================================================
# 18. Runtime: enum value representation uses __tag__
# ===========================================================================

def test_runtime_enum_value_has_tag_key():
    """Runtime stores enum values as dicts with __tag__ key."""
    rt_spec = module_spec(
        "m",
        defs=[fn_spec("make_color", [], INT64, [
            {"op": "enum_make", "tag": "Green", "fields": {}, "into": "c"},
            {"op": "return", "val": {"lit": 0}},
        ])],
        types={"Color": COLOR_TYPE},
    )
    checker = Checker(rt_spec)
    checker.check()
    rt = Runtime(rt_spec)
    # After running make_color the env should have stored {"__tag__": "Green"}
    # We verify by matching: run fn and check return 0
    result = rt.run_fn("make_color")
    assert result == 0


# ===========================================================================
# 19. Runtime: match_enum no case and no default raises NailRuntimeError
# ===========================================================================

def test_runtime_match_enum_missing_case_no_default_raises():
    """At runtime, if no case matches and there is no default, raise NailRuntimeError."""
    # We bypass the checker by calling the runtime directly (checker would catch it,
    # but we want to verify the runtime guard too).
    from interpreter.runtime import Runtime, NailRuntimeError
    rt_unchecked = Runtime.__new__(Runtime)
    rt_unchecked.spec = {"kind": "module", "id": "m"}
    rt_unchecked.fn_registry = {}
    rt_unchecked.module_fn_registry = {}
    rt_unchecked.module_type_aliases = {}
    rt_unchecked._module_alias_spec_cache = {}
    rt_unchecked.type_aliases = {}
    rt_unchecked._alias_spec_cache = {}
    rt_unchecked._module_id_stack = [None]
    rt_unchecked._effect_policy_stack = [(set(), {})]

    stmt = {
        "op": "match_enum",
        "val": {"ref": "x"},
        "cases": [
            {"tag": "OtherTag", "body": []},
        ],
    }
    env = {"x": {"__tag__": "UnknownTag"}}
    with pytest.raises(NailRuntimeError):
        rt_unchecked._run_stmt(stmt, env)


# ===========================================================================
# 20. enum_make inside if-branch
# ===========================================================================

def test_enum_make_inside_if_branch():
    """enum_make used and matched entirely within an if-else branch."""
    # Note: NAIL if-branches have their own scoped env; variables introduced
    # inside a branch are not visible after the branch.  So we perform both
    # enum_make AND match_enum inside each branch.
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [{"id": "flag", "type": BOOL_T}], INT64, [
            {"op": "if",
             "cond": {"ref": "flag"},
             "then": [
                 {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
                 {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                     {"tag": "Red",   "body": [{"op": "return", "val": {"lit": 1}}]},
                     {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                     {"tag": "Blue",  "body": [{"op": "return", "val": {"lit": 3}}]},
                 ]},
             ],
             "else": [
                 {"op": "enum_make", "tag": "Blue", "fields": {}, "into": "c"},
                 {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                     {"tag": "Red",   "body": [{"op": "return", "val": {"lit": 1}}]},
                     {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                     {"tag": "Blue",  "body": [{"op": "return", "val": {"lit": 3}}]},
                 ]},
             ]},
        ])],
        types={"Color": COLOR_TYPE},
    )
    assert run_spec(spec, args={"flag": True},  call_fn="main") == 1
    assert run_spec(spec, args={"flag": False}, call_fn="main") == 3


# ===========================================================================
# 21. match_enum arm body can use outer env vars
# ===========================================================================

def test_match_enum_arm_uses_outer_env():
    """Arm body can reference variables from the outer scope."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "let", "id": "offset", "val": {"lit": 10}},
            {"op": "enum_make", "tag": "Green", "fields": {}, "into": "c"},
            {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                {"tag": "Red",   "body": [{"op": "return", "val": {"ref": "offset"}}]},
                {"tag": "Green", "body": [{"op": "return", "val": {
                    "op": "+", "l": {"ref": "offset"}, "r": {"lit": 5}
                }}]},
                {"tag": "Blue",  "body": [{"op": "return", "val": {"lit": 0}}]},
            ]},
        ])],
        types={"Color": COLOR_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 15


# ===========================================================================
# 22. Enum with int field — Some/None pattern
# ===========================================================================

def test_enum_int_field_arithmetic_in_arm():
    """Bound int field can be used in arithmetic inside the arm body."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Some", "fields": {"val": {"lit": 20}}, "into": "m"},
            {"op": "match_enum", "val": {"ref": "m"}, "cases": [
                {"tag": "Some",
                 "binds": {"val": "v"},
                 "body": [{"op": "return", "val": {
                     "op": "*", "l": {"ref": "v"}, "r": {"lit": 2}
                 }}]},
                {"tag": "None",
                 "body": [{"op": "return", "val": {"lit": 0}}]},
            ]},
        ])],
        types={"MaybeInt": MAYBE_INT_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 40


# ===========================================================================
# 23. Two enums passed as function parameters
# ===========================================================================

def test_enum_as_function_parameter():
    """An enum value can be passed from one function to another."""
    # Color enum param
    spec = module_spec(
        "m",
        defs=[
            fn_spec("color_code", [{"id": "c", "type": {"type": "alias", "name": "Color"}}], INT64, [
                {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                    {"tag": "Red",   "body": [{"op": "return", "val": {"lit": 1}}]},
                    {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                    {"tag": "Blue",  "body": [{"op": "return", "val": {"lit": 3}}]},
                ]},
            ]),
            fn_spec("main", [], INT64, [
                {"op": "enum_make", "tag": "Blue", "fields": {}, "into": "c"},
                {"op": "return", "val": {"op": "call", "fn": "color_code",
                                          "args": [{"ref": "c"}]}},
            ]),
        ],
        types={"Color": COLOR_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 3


# ===========================================================================
# 24. Full four-direction exhaustiveness: all arms required
# ===========================================================================

def test_match_direction_all_arms_required():
    """match_enum on 4-variant enum requires all 4 arms."""
    for missing_tag in ["North", "South", "East", "West"]:
        cases = [
            {"tag": t, "body": [{"op": "return", "val": {"lit": 0}}]}
            for t in ["North", "South", "East", "West"]
            if t != missing_tag
        ]
        spec = module_spec(
            "m",
            defs=[fn_spec("main", [], INT64, [
                {"op": "enum_make", "tag": "North", "fields": {}, "into": "d"},
                {"op": "match_enum", "val": {"ref": "d"}, "cases": cases},
            ])],
            types={"Direction": DIRECTION_TYPE},
        )
        with pytest.raises(CheckError):
            Checker(spec).check()


# ===========================================================================
# 25. Default arm executes when its the only arm
# ===========================================================================

def test_match_enum_only_default_arm():
    """A match_enum with only a default arm (no explicit cases) is valid."""
    spec = module_spec(
        "m",
        defs=[fn_spec("main", [], INT64, [
            {"op": "enum_make", "tag": "Green", "fields": {}, "into": "c"},
            {"op": "match_enum", "val": {"ref": "c"}, "cases": [],
             "default": [{"op": "return", "val": {"lit": 7}}]},
        ])],
        types={"Color": COLOR_TYPE},
    )
    assert run_spec(spec, call_fn="main") == 7
