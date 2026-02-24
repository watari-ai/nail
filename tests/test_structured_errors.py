"""
Tests for structured JSON error messages (#56).

Verifies that CheckError, NailRuntimeError, NailTypeError, and NailEffectError
produce machine-parseable JSON representations while maintaining backward
compatibility with str()-based usage.
"""
import json
import pytest

from interpreter.checker import Checker, CheckError
from interpreter.types import NailRuntimeError, NailTypeError, NailEffectError


# ---------------------------------------------------------------------------
# Helper programs
# ---------------------------------------------------------------------------

def _effect_violation_spec():
    """A module where main() calls helper() without declaring its IO effect.
    Based on examples/bad_effect_call.nail."""
    return {
        "defs": [
            {
                "body": [
                    {"effect": "IO", "op": "print", "val": {"lit": "hello"}},
                    {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}}
                ],
                "effects": ["IO"],
                "id": "helper",
                "kind": "fn",
                "nail": "0.1.0",
                "params": [],
                "returns": {"type": "unit"},
            },
            {
                "body": [
                    {"args": [], "fn": "helper", "op": "call"},
                    {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}}
                ],
                "effects": [],
                "id": "main",
                "kind": "fn",
                "nail": "0.1.0",
                "params": [],
                "returns": {"type": "unit"},
            }
        ],
        "exports": ["main", "helper"],
        "id": "effect_test",
        "kind": "module",
        "nail": "0.1.0",
    }


def _unknown_op_spec():
    return {
        "nail": "0.1.0",
        "kind": "fn",
        "id": "bad_fn",
        "params": [],
        "returns": {"type": "unit"},
        "effects": [],
        "body": [{"op": "nonexistent_op", "val": 42}]
    }


# ---------------------------------------------------------------------------
# CheckError class contract
# ---------------------------------------------------------------------------

class TestCheckErrorStructure:
    def test_default_code(self):
        err = CheckError("something went wrong")
        assert err.code == "CHECK_ERROR"

    def test_custom_code(self):
        err = CheckError("effect missing", code="EFFECT_VIOLATION")
        assert err.code == "EFFECT_VIOLATION"

    def test_str_backward_compat(self):
        """str() must still return the human-readable message."""
        msg = "something went wrong"
        err = CheckError(msg)
        assert str(err) == msg

    def test_args_backward_compat(self):
        """err.args[0] must still return the message."""
        msg = "type mismatch: expected int, got str"
        err = CheckError(msg)
        assert err.args[0] == msg

    def test_to_json_minimal(self):
        err = CheckError("basic error")
        j = err.to_json()
        assert j["error"] == "CheckError"
        assert j["code"] == "CHECK_ERROR"
        assert j["message"] == "basic error"
        assert j["location"] == {}

    def test_to_json_with_location(self):
        err = CheckError("effect missing", code="EFFECT_VIOLATION",
                         location={"fn": "main", "callee": "fetch"},
                         missing=["NET"])
        j = err.to_json()
        assert j["error"] == "CheckError"
        assert j["code"] == "EFFECT_VIOLATION"
        assert j["location"] == {"fn": "main", "callee": "fetch"}
        assert j["missing"] == ["NET"]

    def test_to_json_serializable(self):
        """to_json() output must be JSON-serializable."""
        err = CheckError("test", code="TEST_CODE",
                         location={"fn": "f"},
                         extra_list=["a", "b"])
        j = err.to_json()
        # Must not raise
        json.dumps(j)

    def test_exception_hierarchy(self):
        """CheckError must remain a subclass of Exception."""
        err = CheckError("test")
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# NailRuntimeError class contract
# ---------------------------------------------------------------------------

class TestNailRuntimeErrorStructure:
    def test_default_code(self):
        err = NailRuntimeError("runtime failure")
        assert err.code == "RUNTIME_ERROR"

    def test_str_backward_compat(self):
        msg = "undefined variable: x"
        err = NailRuntimeError(msg)
        assert str(err) == msg

    def test_to_json_minimal(self):
        err = NailRuntimeError("something failed")
        j = err.to_json()
        assert j["error"] == "NailRuntimeError"
        assert j["code"] == "RUNTIME_ERROR"
        assert "message" in j
        assert "location" in j

    def test_to_json_effect_violation(self):
        err = NailRuntimeError(
            "read_file requires FS but not declared",
            code="EFFECT_VIOLATION",
            required=["FS"]
        )
        j = err.to_json()
        assert j["code"] == "EFFECT_VIOLATION"
        assert j["required"] == ["FS"]

    def test_serializable(self):
        err = NailRuntimeError("test", code="RUNTIME_ERROR", location={"fn": "f"})
        json.dumps(err.to_json())


# ---------------------------------------------------------------------------
# NailTypeError and NailEffectError class contracts
# ---------------------------------------------------------------------------

class TestNailTypeErrorStructure:
    def test_default_code(self):
        err = NailTypeError("type mismatch")
        assert err.code == "TYPE_ERROR"

    def test_to_json(self):
        err = NailTypeError("expected int got str", code="TYPE_MISMATCH",
                            location={"fn": "main"},
                            expected="int", actual="str")
        j = err.to_json()
        assert j["error"] == "NailTypeError"
        assert j["code"] == "TYPE_MISMATCH"
        assert j["expected"] == "int"
        assert j["actual"] == "str"


class TestNailEffectErrorStructure:
    def test_default_code(self):
        err = NailEffectError("effect error")
        assert err.code == "EFFECT_ERROR"

    def test_to_json(self):
        err = NailEffectError("NET not allowed")
        j = err.to_json()
        assert j["error"] == "NailEffectError"


# ---------------------------------------------------------------------------
# Real checker raises with structured codes
# ---------------------------------------------------------------------------

class TestCheckerStructuredErrors:
    def test_effect_violation_code(self):
        """Checker raises CheckError with EFFECT_VIOLATION code for missing effects."""
        spec = _effect_violation_spec()
        checker = Checker(spec)
        with pytest.raises(CheckError) as exc_info:
            checker.check()
        err = exc_info.value
        assert err.code == "EFFECT_VIOLATION"
        j = err.to_json()
        assert j["code"] == "EFFECT_VIOLATION"
        assert "main" in j["location"].get("fn", "")
        assert "helper" in j["location"].get("callee", "")
        assert "IO" in j["missing"]

    def test_effect_violation_message_still_readable(self):
        """Even with structured code, the error message is human-readable."""
        spec = _effect_violation_spec()
        checker = Checker(spec)
        with pytest.raises(CheckError) as exc_info:
            checker.check()
        msg = str(exc_info.value)
        assert "main" in msg
        assert "helper" in msg
        assert "IO" in msg

    def test_unknown_op_code(self):
        """Checker raises UNKNOWN_OP for unrecognized ops."""
        spec = _unknown_op_spec()
        checker = Checker(spec)
        with pytest.raises(CheckError) as exc_info:
            checker.check()
        err = exc_info.value
        assert err.code == "UNKNOWN_OP"
        assert err.to_json()["op"] == "nonexistent_op"

    def test_not_canonical_code(self):
        """Checker raises NOT_CANONICAL for non-canonical JSON (requires strict=True + raw_text)."""
        # Canonical form: sort_keys=True + compact separators
        spec = {
            "body": [{"op": "return", "val": {"lit": None, "type": {"type": "unit"}}}],
            "effects": [],
            "id": "f",
            "kind": "fn",
            "nail": "0.1.0",
            "params": [],
            "returns": {"type": "unit"},
        }
        # Pass raw text with non-sorted keys (e.g. 'id' before 'body')
        non_canonical_text = '{"nail":"0.1.0","kind":"fn","id":"f","params":[],"returns":{"type":"unit"},"effects":[],"body":[{"op":"return","val":{"lit":null,"type":{"type":"unit"}}}]}'
        checker = Checker(spec, raw_text=non_canonical_text, strict=True)
        with pytest.raises(CheckError) as exc_info:
            checker.check()
        err = exc_info.value
        assert err.code == "NOT_CANONICAL"

    def test_to_json_is_json_serializable(self):
        """All structured errors from checker are JSON-serializable."""
        spec = _effect_violation_spec()
        checker = Checker(spec)
        with pytest.raises(CheckError) as exc_info:
            checker.check()
        # Should not raise
        serialized = json.dumps(exc_info.value.to_json())
        data = json.loads(serialized)
        assert data["code"] == "EFFECT_VIOLATION"
        assert "message" in data
        assert "location" in data
