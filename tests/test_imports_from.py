"""Tests for import "from" field — schema + checker resolution.

Issue #40: L0 schema required "from" in imports but checker ignored it.
Fix: "from" is now optional in schema AND the checker loads modules from disk
     when the "from" file path is provided and the module isn't pre-loaded.
"""

import json
import textwrap
from pathlib import Path

import pytest

from interpreter.checker import Checker, CheckError


# ── Helper specs ────────────────────────────────────────────────────────────

def _make_utils_module():
    """A simple 'utils' module that exports a 'double' function."""
    return {
        "nail": "0.5.0",
        "kind": "module",
        "id": "utils",
        "exports": ["double"],
        "defs": [
            {
                "nail": "0.5.0",
                "kind": "fn",
                "id": "double",
                "effects": [],
                "params": [
                    {"id": "n", "type": {"type": "int", "bits": 64, "overflow": "panic"}}
                ],
                "returns": {"type": "int", "bits": 64, "overflow": "panic"},
                "body": [
                    {
                        "op": "return",
                        "val": {"op": "*", "l": {"ref": "n"}, "r": {"lit": 2}},
                    }
                ],
            }
        ],
    }


def _make_caller_spec(with_from: str | None = None):
    """A module that imports 'double' from 'utils'."""
    imp = {"module": "utils", "fns": ["double"]}
    if with_from is not None:
        imp["from"] = with_from
    return {
        "nail": "0.5.0",
        "kind": "module",
        "id": "caller",
        "imports": [imp],
        "exports": ["main"],
        "defs": [
            {
                "nail": "0.5.0",
                "kind": "fn",
                "id": "main",
                "effects": ["IO"],
                "params": [],
                "returns": {"type": "unit"},
                "body": [
                    {
                        "op": "let",
                        "id": "result",
                        "type": {"type": "int", "bits": 64, "overflow": "panic"},
                        "val": {
                            "op": "call",
                            "fn": "double",
                            "module": "utils",
                            "args": [{"lit": 21}],
                        },
                    },
                    {
                        "op": "print",
                        "effect": "IO",
                        "val": {
                            "op": "int_to_str",
                            "v": {"ref": "result"},
                        },
                    },
                    {
                        "op": "return",
                        "val": {"lit": None, "type": {"type": "unit"}},
                    },
                ],
            }
        ],
    }


# ── Schema-level tests ───────────────────────────────────────────────────────

class TestSchemaOptionalFrom:
    """'from' is now optional — L0 validation should accept imports without it."""

    def test_import_without_from_passes_l0(self):
        """Import missing 'from' must not raise a schema error."""
        spec = _make_caller_spec(with_from=None)
        modules = {"utils": _make_utils_module()}
        checker = Checker(spec, modules=modules, level=1)
        checker.check()  # should not raise

    def test_import_with_from_passes_l0(self, tmp_path):
        """Import with 'from' must also pass L0."""
        utils_path = tmp_path / "utils.nail"
        utils_path.write_text(json.dumps(_make_utils_module()), encoding="utf-8")
        spec = _make_caller_spec(with_from=str(utils_path))
        checker = Checker(spec, level=1)  # no pre-loaded modules
        checker.check()  # should not raise


# ── File-resolution tests ────────────────────────────────────────────────────

class TestFromFileResolution:
    """Checker loads modules from 'from' file path when not pre-loaded."""

    def test_absolute_from_path(self, tmp_path):
        """Absolute 'from' path loads the module without pre-loading."""
        utils_path = tmp_path / "utils.nail"
        utils_path.write_text(json.dumps(_make_utils_module()), encoding="utf-8")

        spec = _make_caller_spec(with_from=str(utils_path))
        checker = Checker(spec, level=2)
        checker.check()  # should not raise

    def test_relative_from_path_resolved_against_source(self, tmp_path):
        """Relative 'from' path is resolved relative to the spec's source file."""
        utils_path = tmp_path / "utils.nail"
        utils_path.write_text(json.dumps(_make_utils_module()), encoding="utf-8")

        caller_path = tmp_path / "caller.nail"
        spec = _make_caller_spec(with_from="utils.nail")
        caller_path.write_text(json.dumps(spec), encoding="utf-8")

        # source_path tells checker where the spec lives → "utils.nail" resolves to tmp_path/utils.nail
        checker = Checker(spec, level=2, source_path=str(caller_path))
        checker.check()

    def test_preloaded_module_takes_priority(self, tmp_path):
        """If module is already in modules dict, 'from' path is not consulted."""
        # Write a BROKEN utils file — if "from" were consulted, it would fail
        broken_path = tmp_path / "broken.nail"
        broken_path.write_text('{"not": "valid"}', encoding="utf-8")

        spec = _make_caller_spec(with_from=str(broken_path))
        # Pre-load the correct module — should win
        checker = Checker(spec, modules={"utils": _make_utils_module()}, level=2)
        checker.check()  # should not raise; broken file is ignored

    def test_missing_from_file_raises_check_error(self, tmp_path):
        """'from' path that doesn't exist → CheckError MODULE_NOT_FOUND."""
        spec = _make_caller_spec(with_from="/nonexistent/path/utils.nail")
        with pytest.raises(CheckError) as exc_info:
            checker = Checker(spec, level=1)
            checker.check()
        err = exc_info.value
        assert err.code == "MODULE_NOT_FOUND"
        assert "utils" in str(err)

    def test_invalid_json_from_file_raises_check_error(self, tmp_path):
        """'from' file with invalid JSON → CheckError MODULE_LOAD_ERROR."""
        bad_path = tmp_path / "bad.nail"
        bad_path.write_text("this is not json", encoding="utf-8")

        spec = _make_caller_spec(with_from=str(bad_path))
        with pytest.raises(CheckError) as exc_info:
            checker = Checker(spec, level=1)
            checker.check()
        assert exc_info.value.code == "MODULE_LOAD_ERROR"

    def test_missing_module_without_from_gives_helpful_message(self):
        """Without 'from', the error message mentions --modules CLI flag."""
        spec = _make_caller_spec(with_from=None)  # no 'from', no pre-loaded module
        with pytest.raises(CheckError) as exc_info:
            checker = Checker(spec, level=1)
            checker.check()
        msg = str(exc_info.value)
        assert "--modules" in msg or "modules=" in msg


# ── to_json coverage ─────────────────────────────────────────────────────────

class TestModuleNotFoundToJson:
    """MODULE_NOT_FOUND errors must produce structured JSON."""

    def test_module_not_found_to_json(self, tmp_path):
        spec = _make_caller_spec(with_from="/no/such/file.nail")
        with pytest.raises(CheckError) as exc_info:
            Checker(spec, level=1).check()
        j = exc_info.value.to_json()
        assert j["error"] == "CheckError"
        assert j["code"] == "MODULE_NOT_FOUND"
        assert "utils" in j["message"]
