#!/usr/bin/env python3
"""
NAIL Function Calling Effect Annotations — Test Suite

Tests for the ``integrations/function_calling.py`` module.

Run:
    python3 -m pytest tests/test_function_calling.py -v
    # or directly:
    python3 tests/test_function_calling.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.function_calling import (
    NAILFunction,
    VALID_EFFECTS,
    UNKNOWN,
    from_openai,
    from_anthropic,
    to_nail_annotated,
    filter_by_effects,
    requires_any,
    validate_effects,
    annotate_openai_schema,
    annotate_openai_tool_list,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OPENAI_READ_FILE = {
    "name": "read_file",
    "description": "Read contents of a file from disk",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"}
        },
        "required": ["path"],
    },
}

OPENAI_SEND_EMAIL = {
    "name": "send_email",
    "description": "Send an email to a recipient",
    "parameters": {
        "type": "object",
        "properties": {
            "to":      {"type": "string"},
            "subject": {"type": "string"},
            "body":    {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
}

OPENAI_PURE_CALC = {
    "name": "pure_calc",
    "description": "Compute the result of a mathematical expression",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {"type": "string"},
        },
        "required": ["expression"],
    },
}

ANTHROPIC_READ_FILE = {
    "name": "read_file",
    "description": "Read contents of a file from disk",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"}
        },
        "required": ["path"],
    },
}

OPENAI_WITH_EFFECTS = {
    "name": "write_log",
    "description": "Write a log entry to disk",
    "effects": ["FS", "IO"],
    "parameters": {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    },
}


# ===========================================================================
# 1. from_openai — basic parsing
# ===========================================================================

class TestFromOpenAI(unittest.TestCase):

    def test_parses_name_and_description(self):
        """from_openai should correctly extract name and description."""
        fn = from_openai(OPENAI_READ_FILE)
        self.assertEqual(fn.name, "read_file")
        self.assertEqual(fn.description, "Read contents of a file from disk")

    def test_no_effects_field_yields_none(self):
        """Schemas without an effects field should have effects=None (unknown)."""
        fn = from_openai(OPENAI_READ_FILE)
        self.assertIsNone(fn.effects)
        self.assertTrue(fn.is_unknown())
        self.assertFalse(fn.is_pure())

    def test_existing_effects_field_preserved(self):
        """If the schema already carries an effects field it must be kept."""
        fn = from_openai(OPENAI_WITH_EFFECTS)
        self.assertIsNotNone(fn.effects)
        self.assertIn("FS", fn.effects)
        self.assertIn("IO", fn.effects)

    def test_unwraps_type_function_envelope(self):
        """OpenAI often wraps schemas as {"type": "function", "function": {...}}."""
        envelope = {"type": "function", "function": OPENAI_PURE_CALC}
        fn = from_openai(envelope)
        self.assertEqual(fn.name, "pure_calc")

    def test_parameters_are_copied(self):
        """Parameters dict should be a deep copy — mutating it must not touch source."""
        fn = from_openai(OPENAI_READ_FILE)
        fn.parameters["injected"] = True
        self.assertNotIn("injected", OPENAI_READ_FILE.get("parameters", {}))

    def test_missing_name_raises(self):
        """Schemas without a name field should raise ValueError."""
        with self.assertRaises(ValueError):
            from_openai({"description": "No name here", "parameters": {}})


# ===========================================================================
# 2. from_anthropic — basic parsing
# ===========================================================================

class TestFromAnthropic(unittest.TestCase):

    def test_parses_name_and_input_schema(self):
        """from_anthropic should populate input_schema, not parameters."""
        fn = from_anthropic(ANTHROPIC_READ_FILE)
        self.assertEqual(fn.name, "read_file")
        self.assertIsNotNone(fn.input_schema)
        self.assertIsNone(fn.parameters)

    def test_no_effects_yields_unknown(self):
        """Anthropic tools without effects should be unknown."""
        fn = from_anthropic(ANTHROPIC_READ_FILE)
        self.assertIsNone(fn.effects)
        self.assertTrue(fn.is_unknown())

    def test_fmt_is_anthropic(self):
        fn = from_anthropic(ANTHROPIC_READ_FILE)
        self.assertEqual(fn.fmt, "anthropic")

    def test_missing_name_raises(self):
        with self.assertRaises(ValueError):
            from_anthropic({"description": "nameless", "input_schema": {}})


# ===========================================================================
# 3. to_nail_annotated — effect annotation
# ===========================================================================

class TestToNailAnnotated(unittest.TestCase):

    def test_annotate_fs_effect(self):
        """Annotating read_file with FS should yield effects=["FS"]."""
        fn = from_openai(OPENAI_READ_FILE)
        annotated = to_nail_annotated(fn, ["FS"])
        self.assertEqual(annotated.effects, ["FS"])
        self.assertFalse(annotated.is_unknown())
        self.assertFalse(annotated.is_pure())

    def test_annotate_multiple_effects(self):
        """send_email annotated with NET+IO should list both."""
        fn = from_openai(OPENAI_SEND_EMAIL)
        annotated = to_nail_annotated(fn, ["NET", "IO"])
        self.assertIn("NET", annotated.effects)
        self.assertIn("IO", annotated.effects)
        self.assertEqual(len(annotated.effects), 2)

    def test_annotate_pure_function(self):
        """Annotating with empty effects should mark function as pure."""
        fn = from_openai(OPENAI_PURE_CALC)
        annotated = to_nail_annotated(fn, [])
        self.assertTrue(annotated.is_pure())
        self.assertEqual(annotated.effects, [])

    def test_source_function_not_mutated(self):
        """to_nail_annotated should return a new object, not mutate original."""
        fn = from_openai(OPENAI_READ_FILE)
        annotated = to_nail_annotated(fn, ["FS"])
        self.assertIsNone(fn.effects)           # original unchanged
        self.assertEqual(annotated.effects, ["FS"])

    def test_invalid_effect_raises(self):
        """Unknown effect kinds should raise ValueError."""
        fn = from_openai(OPENAI_READ_FILE)
        with self.assertRaises(ValueError):
            to_nail_annotated(fn, ["DISK"])  # not a valid NAIL effect

    def test_to_dict_includes_effects(self):
        """Serialised dict must have the 'effects' key."""
        fn = from_openai(OPENAI_READ_FILE)
        annotated = to_nail_annotated(fn, ["FS"])
        d = annotated.to_dict()
        self.assertIn("effects", d)
        self.assertEqual(d["effects"], ["FS"])
        self.assertEqual(d["name"], "read_file")

    def test_all_effect_kinds_valid(self):
        """Each individual NAIL effect kind should be accepted."""
        fn = from_openai(OPENAI_READ_FILE)
        for kind in VALID_EFFECTS:
            annotated = to_nail_annotated(fn, [kind])
            self.assertIn(kind, annotated.effects)


# ===========================================================================
# 4. filter_by_effects — sandbox policy enforcement
# ===========================================================================

class TestFilterByEffects(unittest.TestCase):

    def _make_tools(self):
        read_file  = to_nail_annotated(from_openai(OPENAI_READ_FILE),  ["FS"])
        send_email = to_nail_annotated(from_openai(OPENAI_SEND_EMAIL), ["NET", "IO"])
        pure_calc  = to_nail_annotated(from_openai(OPENAI_PURE_CALC),  [])
        unknown    = from_openai(OPENAI_READ_FILE)  # no effects declared
        return read_file, send_email, pure_calc, unknown

    def test_only_fs_allowed(self):
        """Sandbox allowing only FS should expose read_file and pure_calc."""
        read_file, send_email, pure_calc, _ = self._make_tools()
        result = filter_by_effects([read_file, send_email, pure_calc], ["FS"])
        names = {fn.name for fn in result}
        self.assertIn("read_file", names)
        self.assertIn("pure_calc", names)
        self.assertNotIn("send_email", names)

    def test_empty_allowed_only_pure(self):
        """An empty allowed set should expose only pure (effect-free) functions."""
        read_file, send_email, pure_calc, _ = self._make_tools()
        result = filter_by_effects([read_file, send_email, pure_calc], [])
        names = {fn.name for fn in result}
        self.assertEqual(names, {"pure_calc"})

    def test_unknown_functions_excluded(self):
        """Functions with unknown effects (None) are excluded from filtered results."""
        _, _, pure_calc, unknown = self._make_tools()
        result = filter_by_effects([pure_calc, unknown], ["FS", "IO", "NET"])
        # unknown has effects=None → excluded
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "pure_calc")

    def test_all_allowed_passes_all_annotated(self):
        """Allowing all NAIL effects should pass every annotated function."""
        read_file, send_email, pure_calc, _ = self._make_tools()
        all_effects = list(VALID_EFFECTS)
        result = filter_by_effects([read_file, send_email, pure_calc], all_effects)
        self.assertEqual(len(result), 3)

    def test_invalid_allowed_effect_raises(self):
        """Invalid effect kinds in the allowed set should raise ValueError."""
        fn = to_nail_annotated(from_openai(OPENAI_PURE_CALC), [])
        with self.assertRaises(ValueError):
            filter_by_effects([fn], ["BADKIND"])


# ===========================================================================
# 5. requires_any — capability check
# ===========================================================================

class TestRequiresAny(unittest.TestCase):

    def test_net_tool_requires_net(self):
        fn = to_nail_annotated(from_openai(OPENAI_SEND_EMAIL), ["NET", "IO"])
        self.assertTrue(requires_any(fn, ["NET"]))

    def test_fs_tool_does_not_require_net(self):
        fn = to_nail_annotated(from_openai(OPENAI_READ_FILE), ["FS"])
        self.assertFalse(requires_any(fn, ["NET"]))

    def test_pure_tool_requires_nothing(self):
        fn = to_nail_annotated(from_openai(OPENAI_PURE_CALC), [])
        self.assertFalse(requires_any(fn, ["FS", "NET", "IO"]))

    def test_unknown_conservatively_true(self):
        """Unknown effects should be treated as potentially requiring everything."""
        fn = from_openai(OPENAI_READ_FILE)  # no effects
        self.assertTrue(requires_any(fn, ["NET"]))


# ===========================================================================
# 6. validate_effects
# ===========================================================================

class TestValidateEffects(unittest.TestCase):

    def test_all_valid_effects_pass(self):
        validate_effects(["IO", "FS", "NET", "TIME", "RAND", "MUT"])

    def test_empty_list_is_valid(self):
        validate_effects([])  # pure — should not raise

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_effects(["IO", "NETWORK"])  # NETWORK not valid
        self.assertIn("NETWORK", str(ctx.exception))

    def test_lowercase_raises(self):
        """Effect kinds are case-sensitive; lowercase should be rejected."""
        with self.assertRaises(ValueError):
            validate_effects(["fs"])


# ===========================================================================
# 7. annotate_openai_schema / annotate_openai_tool_list — convenience helpers
# ===========================================================================

class TestBatchHelpers(unittest.TestCase):

    def test_annotate_openai_schema_returns_dict(self):
        result = annotate_openai_schema(OPENAI_READ_FILE, ["FS"])
        self.assertIsInstance(result, dict)
        self.assertEqual(result["effects"], ["FS"])
        self.assertEqual(result["name"], "read_file")

    def test_annotate_openai_schema_pure(self):
        result = annotate_openai_schema(OPENAI_PURE_CALC, [])
        self.assertEqual(result["effects"], [])

    def test_annotate_tool_list_with_effect_map(self):
        tools = [OPENAI_SEND_EMAIL, OPENAI_READ_FILE, OPENAI_PURE_CALC]
        effect_map = {
            "send_email": ["NET", "IO"],
            "read_file":  ["FS"],
            "pure_calc":  [],
        }
        result = annotate_openai_tool_list(tools, effect_map)
        by_name = {d["name"]: d for d in result}

        self.assertEqual(by_name["send_email"]["effects"], ["NET", "IO"])
        self.assertEqual(by_name["read_file"]["effects"],  ["FS"])
        self.assertEqual(by_name["pure_calc"]["effects"],  [])

    def test_tool_list_unmapped_gets_unknown_sentinel(self):
        """Tools not in effect_map should get effects: ["*"] sentinel."""
        tools = [OPENAI_READ_FILE]
        result = annotate_openai_tool_list(tools, {})  # no map entry
        self.assertEqual(result[0]["effects"], [UNKNOWN])

    def test_original_dicts_not_mutated(self):
        """Batch helpers must not modify the original schema dicts."""
        import copy
        original = copy.deepcopy(OPENAI_READ_FILE)
        annotate_openai_schema(OPENAI_READ_FILE, ["FS"])
        self.assertNotIn("effects", OPENAI_READ_FILE)
        self.assertEqual(OPENAI_READ_FILE, original)


# ===========================================================================
# 8. NAILFunction.has_effect
# ===========================================================================

class TestHasEffect(unittest.TestCase):

    def test_declared_effect_found(self):
        fn = to_nail_annotated(from_openai(OPENAI_SEND_EMAIL), ["NET", "IO"])
        self.assertTrue(fn.has_effect("NET"))
        self.assertTrue(fn.has_effect("IO"))
        self.assertFalse(fn.has_effect("FS"))

    def test_unknown_conservative(self):
        fn = from_openai(OPENAI_READ_FILE)  # effects=None
        # Unknown functions are assumed to have every effect (conservative)
        self.assertTrue(fn.has_effect("NET"))

    def test_pure_has_no_effects(self):
        fn = to_nail_annotated(from_openai(OPENAI_PURE_CALC), [])
        self.assertFalse(fn.has_effect("FS"))
        self.assertFalse(fn.has_effect("NET"))


# ===========================================================================
# 9. Round-trip: OpenAI schema → NAILFunction → annotated dict
# ===========================================================================

class TestRoundTrip(unittest.TestCase):

    def test_openai_read_file_round_trip(self):
        fn = from_openai(OPENAI_READ_FILE)
        annotated = to_nail_annotated(fn, ["FS"])
        d = annotated.to_dict()
        self.assertEqual(d["name"], "read_file")
        self.assertEqual(d["effects"], ["FS"])
        self.assertIn("parameters", d)
        self.assertEqual(
            d["parameters"]["properties"]["path"]["type"],
            "string",
        )

    def test_anthropic_read_file_round_trip(self):
        fn = from_anthropic(ANTHROPIC_READ_FILE)
        annotated = to_nail_annotated(fn, ["FS"])
        d = annotated.to_dict()
        self.assertEqual(d["name"], "read_file")
        self.assertEqual(d["effects"], ["FS"])
        self.assertIn("input_schema", d)


# ===========================================================================
# 10. Integration scenario: sandbox policy enforcement
# ===========================================================================

class TestSandboxScenario(unittest.TestCase):
    """
    Full-scenario test modelling a sandbox that allows only FS.
    Available tools: read_file(FS), send_email(NET,IO), pure_calc([]).
    Expected: read_file and pure_calc pass; send_email is blocked.
    """

    def setUp(self):
        tools_raw = [OPENAI_READ_FILE, OPENAI_SEND_EMAIL, OPENAI_PURE_CALC]
        effect_map = {
            "read_file":  ["FS"],
            "send_email": ["NET", "IO"],
            "pure_calc":  [],
        }
        annotated_dicts = annotate_openai_tool_list(tools_raw, effect_map)
        self.tools = [from_openai(d) for d in annotated_dicts]

    def test_sandbox_fs_only(self):
        allowed = filter_by_effects(self.tools, ["FS"])
        names = {fn.name for fn in allowed}
        self.assertEqual(names, {"read_file", "pure_calc"})

    def test_no_network_tools_in_sandbox(self):
        allowed = filter_by_effects(self.tools, ["FS"])
        for fn in allowed:
            self.assertFalse(fn.has_effect("NET"),
                             f"{fn.name} should not have NET in FS-only sandbox")

    def test_pure_calc_always_allowed(self):
        # Even the most restrictive sandbox (no effects) should allow pure fns
        allowed = filter_by_effects(self.tools, [])
        names = {fn.name for fn in allowed}
        self.assertIn("pure_calc", names)

    def test_send_email_blocked_without_net(self):
        allowed = filter_by_effects(self.tools, ["FS"])
        names = {fn.name for fn in allowed}
        self.assertNotIn("send_email", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
