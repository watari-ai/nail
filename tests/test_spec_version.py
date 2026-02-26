"""
NAIL #101 — Spec Freeze: spec_version field validation tests.

Covers:
  - spec_version present and valid   → OK, no warnings
  - spec_version absent              → legacy_mode=True, warning (not error)
  - spec_version invalid format      → CheckError(code=UNSUPPORTED_SPEC_VERSION)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, CheckError

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
UNIT_T = {"type": "unit"}
BOOL_T = {"type": "bool"}


def _fn_spec(spec_version=None, include_meta=True):
    """Minimal valid fn spec; optionally includes meta.spec_version."""
    spec = {
        "nail": "0.9.0",
        "kind": "fn",
        "id": "add",
        "effects": [],
        "params": [
            {"id": "a", "type": INT64},
            {"id": "b", "type": INT64},
        ],
        "returns": INT64,
        "body": [
            {"op": "return", "val": {"op": "+", "l": {"ref": "a"}, "r": {"ref": "b"}}},
        ],
    }
    if include_meta and spec_version is not None:
        spec["meta"] = {"spec_version": spec_version}
    elif not include_meta:
        # meta key is entirely absent
        pass
    return spec


def _module_spec(spec_version=None, include_meta=True):
    """Minimal valid module spec; optionally includes meta.spec_version."""
    spec = {
        "nail": "0.9.0",
        "kind": "module",
        "id": "mymod",
        "exports": ["add"],
        "defs": [
            {
                "kind": "fn",
                "id": "add",
                "effects": [],
                "params": [
                    {"id": "a", "type": INT64},
                    {"id": "b", "type": INT64},
                ],
                "returns": INT64,
                "body": [
                    {"op": "return", "val": {"op": "+", "l": {"ref": "a"}, "r": {"ref": "b"}}},
                ],
            }
        ],
    }
    if include_meta and spec_version is not None:
        spec["meta"] = {"spec_version": spec_version}
    elif not include_meta:
        pass
    return spec


# ──────────────────────────────────────────────
# Tests: spec_version present and valid
# ──────────────────────────────────────────────


class TestSpecVersionValid:
    """Valid spec_version values should pass without warnings or errors."""

    @pytest.mark.parametrize("sv", [
        "1.0.0",
        "0.9.0",
        "0.9.1",
        "0.9.9",
        "0.9.10",
    ])
    def test_fn_valid_spec_version(self, sv):
        spec = _fn_spec(sv)
        checker = Checker(spec)
        checker.check()  # must not raise
        assert checker._legacy_mode is False
        assert checker.warnings == []

    @pytest.mark.parametrize("sv", [
        "1.0.0",
        "0.9.0",
        "0.9.5",
    ])
    def test_module_valid_spec_version(self, sv):
        spec = _module_spec(sv)
        checker = Checker(spec)
        checker.check()  # must not raise
        assert checker._legacy_mode is False
        assert checker.warnings == []


# ──────────────────────────────────────────────
# Tests: spec_version absent → legacy_mode
# ──────────────────────────────────────────────


class TestSpecVersionMissing:
    """Missing spec_version must NOT raise — only emit a warning and enable legacy_mode."""

    def test_fn_no_meta_at_all(self):
        spec = _fn_spec(include_meta=False)
        assert "meta" not in spec  # sanity check
        checker = Checker(spec)
        checker.check()  # MUST NOT raise
        assert checker._legacy_mode is True
        assert len(checker.warnings) == 1
        w = checker.warnings[0]
        assert isinstance(w, CheckError)
        assert w.code == "MISSING_SPEC_VERSION"
        assert w.severity == "warning"

    def test_fn_meta_without_spec_version(self):
        spec = _fn_spec(include_meta=False)
        spec["meta"] = {"author": "test"}  # meta exists but no spec_version key
        checker = Checker(spec)
        checker.check()  # MUST NOT raise
        assert checker._legacy_mode is True
        assert any(w.code == "MISSING_SPEC_VERSION" for w in checker.warnings)

    def test_module_no_meta_at_all(self):
        spec = _module_spec(include_meta=False)
        checker = Checker(spec)
        checker.check()  # MUST NOT raise
        assert checker._legacy_mode is True
        assert len(checker.warnings) == 1
        assert checker.warnings[0].code == "MISSING_SPEC_VERSION"

    def test_warning_is_not_an_exception(self):
        """Confirm that a missing spec_version does not propagate as a raised exception."""
        spec = _fn_spec(include_meta=False)
        try:
            checker = Checker(spec)
            checker.check()
        except CheckError as e:
            pytest.fail(
                f"check() raised CheckError for missing spec_version — should only warn. Error: {e}"
            )

    def test_legacy_mode_off_when_valid_version(self):
        """Sanity: legacy_mode must be False when spec_version is valid."""
        checker = Checker(_fn_spec("1.0.0"))
        checker.check()
        assert checker._legacy_mode is False


# ──────────────────────────────────────────────
# Tests: spec_version invalid format → CheckError
# ──────────────────────────────────────────────


class TestSpecVersionInvalid:
    """Invalid spec_version strings must raise CheckError(code=UNSUPPORTED_SPEC_VERSION)."""

    @pytest.mark.parametrize("bad_sv", [
        "2.0.0",
        "0.8.0",
        "0.9",           # missing patch
        "0.9.x",         # 'x' is not a number
        "v1.0.0",        # leading 'v'
        "1.0.0-rc1",     # pre-release suffix
        "latest",
        "",
        "1",
        "0.10.0",
        "0.9.0.1",       # extra segment
    ])
    def test_fn_unsupported_spec_version(self, bad_sv):
        spec = _fn_spec(bad_sv)
        checker = Checker(spec)
        with pytest.raises(CheckError) as exc_info:
            checker.check()
        err = exc_info.value
        assert err.code == "UNSUPPORTED_SPEC_VERSION", (
            f"Expected code=UNSUPPORTED_SPEC_VERSION, got code={err.code!r} "
            f"for spec_version={bad_sv!r}"
        )
        assert err.severity == "error"

    @pytest.mark.parametrize("bad_sv", [
        "2.0.0",
        "0.8.0",
        "0.9",
        "1.0.0-beta",
    ])
    def test_module_unsupported_spec_version(self, bad_sv):
        spec = _module_spec(bad_sv)
        checker = Checker(spec)
        with pytest.raises(CheckError) as exc_info:
            checker.check()
        assert exc_info.value.code == "UNSUPPORTED_SPEC_VERSION"

    def test_spec_version_null_treated_as_missing(self):
        """null spec_version should behave the same as absent (legacy_mode, warning)."""
        spec = _fn_spec(include_meta=False)
        spec["meta"] = {"spec_version": None}
        checker = Checker(spec)
        checker.check()  # should NOT raise
        assert checker._legacy_mode is True
        assert any(w.code == "MISSING_SPEC_VERSION" for w in checker.warnings)

    def test_spec_version_int_is_unsupported(self):
        """Non-string spec_version triggers UNSUPPORTED_SPEC_VERSION."""
        spec = _fn_spec(include_meta=False)
        spec["meta"] = {"spec_version": 100}
        checker = Checker(spec)
        with pytest.raises(CheckError) as exc_info:
            checker.check()
        assert exc_info.value.code == "UNSUPPORTED_SPEC_VERSION"


# ──────────────────────────────────────────────
# Tests: CheckError.severity field
# ──────────────────────────────────────────────


class TestCheckErrorSeverity:
    """CheckError supports severity='warning' vs severity='error'."""

    def test_default_severity_is_error(self):
        err = CheckError("something went wrong", code="CHECK_ERROR")
        assert err.severity == "error"

    def test_warning_severity(self):
        w = CheckError("heads up", code="MISSING_SPEC_VERSION", severity="warning")
        assert w.severity == "warning"
        assert w.code == "MISSING_SPEC_VERSION"

    def test_to_json_includes_severity(self):
        err = CheckError("boom", code="MY_CODE", severity="error")
        data = err.to_json()
        assert data["severity"] == "error"
        assert data["code"] == "MY_CODE"
        assert data["message"] == "boom"

    def test_to_json_warning(self):
        w = CheckError("soft fail", code="MISSING_SPEC_VERSION", severity="warning")
        data = w.to_json()
        assert data["severity"] == "warning"
        assert data["error"] == "CheckError"
