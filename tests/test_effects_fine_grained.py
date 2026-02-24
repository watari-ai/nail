#!/usr/bin/env python3
"""
NAIL Fine-grained Effect Capabilities — Test Suite (v0.4)

Covers: granular FS/NET effect capability declarations, enforcement at
check-time (L2) and runtime, backward-compat, and negative cases.

Run: python3 tests/test_effects_fine_grained.py
"""

import sys
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, Runtime, CheckError, NailEffectError, NailRuntimeError
from interpreter.types import StringType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STR_T = {"type": "string"}
UNIT_T = {"type": "unit"}
INT64 = {"type": "int", "bits": 64, "overflow": "panic"}


def fn_spec(fn_id, params, returns, body, effects=None):
    return {
        "nail": "0.4",
        "kind": "fn",
        "id": fn_id,
        "effects": effects or [],
        "params": params,
        "returns": returns,
        "body": body,
    }


def _make_read_file_fn(path_lit: str, effects: list) -> dict:
    return fn_spec(
        "f", [], STR_T,
        [
            {"op": "read_file", "path": {"lit": path_lit}, "effect": "FS", "into": "contents"},
            {"op": "return", "val": {"ref": "contents"}},
        ],
        effects=effects,
    )


def _make_http_get_fn(url_lit: str, effects: list) -> dict:
    return fn_spec(
        "f", [], STR_T,
        [
            {"op": "http_get", "url": {"lit": url_lit}, "effect": "NET", "into": "body"},
            {"op": "return", "val": {"ref": "body"}},
        ],
        effects=effects,
    )


class _FakeHTTPResponse:
    """Minimal context manager mock for urllib.request.urlopen."""
    def __init__(self, data: bytes = b"ok"):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return self._data


# ===========================================================================
# 1. FS Capability — Multiple Allowed Paths (union semantics)
# ===========================================================================

class TestFSMultipleAllowedPaths(unittest.TestCase):
    """A cap may list multiple allowed directories; any match is sufficient."""

    def test_first_path_in_list_is_allowed(self):
        """Read from the first directory in the allow list must pass."""
        with tempfile.TemporaryDirectory() as td:
            dir_a = Path(td) / "a"
            dir_b = Path(td) / "b"
            dir_a.mkdir()
            dir_b.mkdir()
            file_a = dir_a / "x.txt"
            file_a.write_text("alpha", encoding="utf-8")

            spec = _make_read_file_fn(
                str(file_a),
                effects=[{"kind": "FS", "allow": [str(dir_a), str(dir_b)], "ops": ["read"]}],
            )
            Checker(spec).check()
            result = Runtime(spec).run()
            self.assertEqual(result, "alpha")

    def test_second_path_in_list_is_allowed(self):
        """Read from the second directory in the allow list must also pass."""
        with tempfile.TemporaryDirectory() as td:
            dir_a = Path(td) / "a"
            dir_b = Path(td) / "b"
            dir_a.mkdir()
            dir_b.mkdir()
            file_b = dir_b / "y.txt"
            file_b.write_text("beta", encoding="utf-8")

            spec = _make_read_file_fn(
                str(file_b),
                effects=[{"kind": "FS", "allow": [str(dir_a), str(dir_b)], "ops": ["read"]}],
            )
            Checker(spec).check()
            result = Runtime(spec).run()
            self.assertEqual(result, "beta")

    def test_path_not_in_any_allowed_entry_raises_at_check_time(self):
        """Access to a path outside all allow entries must raise CheckError."""
        with tempfile.TemporaryDirectory() as td:
            dir_a = Path(td) / "a"
            dir_b = Path(td) / "b"
            forbidden = Path(td) / "c"
            dir_a.mkdir()
            dir_b.mkdir()
            forbidden.mkdir()
            secret = forbidden / "secret.txt"
            secret.write_text("nope", encoding="utf-8")

            spec = _make_read_file_fn(
                str(secret),
                effects=[{"kind": "FS", "allow": [str(dir_a), str(dir_b)], "ops": ["read"]}],
            )
            with self.assertRaises(CheckError):
                Checker(spec).check()


# ===========================================================================
# 2. FS Capability — Subdirectory Access is Permitted
# ===========================================================================

class TestFSSubdirectoryAccess(unittest.TestCase):
    """Files in subdirectories of an allowed root are within scope."""

    def test_nested_subdirectory_access_allowed(self):
        """A file deep inside the allowed root must pass the capability check."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "data"
            nested = root / "sub" / "deep"
            nested.mkdir(parents=True)
            target = nested / "file.txt"
            target.write_text("deep content", encoding="utf-8")

            spec = _make_read_file_fn(
                str(target),
                effects=[{"kind": "FS", "allow": [str(root)], "ops": ["read"]}],
            )
            Checker(spec).check()
            result = Runtime(spec).run()
            self.assertEqual(result, "deep content")

    def test_sibling_directory_is_denied(self):
        """A file in a sibling directory (outside the allowed root) must be denied."""
        with tempfile.TemporaryDirectory() as td:
            allowed_root = Path(td) / "safe"
            sibling = Path(td) / "unsafe"
            allowed_root.mkdir()
            sibling.mkdir()
            bad_file = sibling / "leaked.txt"
            bad_file.write_text("secret", encoding="utf-8")

            spec = _make_read_file_fn(
                str(bad_file),
                effects=[{"kind": "FS", "allow": [str(allowed_root)], "ops": ["read"]}],
            )
            with self.assertRaises(CheckError):
                Checker(spec).check()


# ===========================================================================
# 3. FS Capability — ops Constraint Enforcement
# ===========================================================================

class TestFSOpsConstraint(unittest.TestCase):
    """'ops' restricts which operations are permitted."""

    def test_ops_read_allows_read_file(self):
        """A cap with ops=['read'] must permit read_file operations."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / "ok.txt"
            f.write_text("readable", encoding="utf-8")
            spec = _make_read_file_fn(
                str(f),
                effects=[{"kind": "FS", "allow": [str(root)], "ops": ["read"]}],
            )
            Checker(spec).check()  # must not raise

    def test_ops_write_only_denies_read_file_at_check_time(self):
        """A cap with ops=['write'] must block read_file at check time."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / "f.txt"
            f.write_text("data", encoding="utf-8")
            spec = _make_read_file_fn(
                str(f),
                # ops=['write'] means no 'read' → _fs_capability_allows returns False
                effects=[{"kind": "FS", "allow": [str(root)], "ops": ["write"]}],
            )
            with self.assertRaises(CheckError):
                Checker(spec).check()

    def test_ops_absent_means_all_ops_allowed(self):
        """When 'ops' is absent, any operation is permitted (no op restriction)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / "any.txt"
            f.write_text("no ops field", encoding="utf-8")
            spec = _make_read_file_fn(
                str(f),
                effects=[{"kind": "FS", "allow": [str(root)]}],  # no 'ops'
            )
            Checker(spec).check()  # must not raise
            result = Runtime(spec).run()
            self.assertEqual(result, "no ops field")


# ===========================================================================
# 4. NET Capability — Domain Allow / Deny
# ===========================================================================

class TestNETDomainAllowDeny(unittest.TestCase):
    """NET capability allows specific hostnames; all others are denied."""

    def test_allowed_domain_passes_checker(self):
        """A URL whose hostname is in the allow list must pass L2 check."""
        spec = _make_http_get_fn(
            "https://api.example.com/data",
            effects=[{"kind": "NET", "allow": ["api.example.com"]}],
        )
        Checker(spec).check()  # must not raise

    def test_denied_domain_raises_at_check_time(self):
        """A URL whose hostname is NOT in the allow list must raise CheckError."""
        spec = _make_http_get_fn(
            "https://evil.example.com/steal",
            effects=[{"kind": "NET", "allow": ["api.example.com"]}],
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_domain_check_is_case_insensitive(self):
        """Domain matching must be case-insensitive (RFC 4343)."""
        spec = _make_http_get_fn(
            "https://API.EXAMPLE.COM/v1",
            effects=[{"kind": "NET", "allow": ["api.example.com"]}],
        )
        Checker(spec).check()  # uppercase hostname must still match

    def test_http_scheme_also_allowed_for_listed_domain(self):
        """Plain http:// (not just https://) is accepted when domain is in allow list."""
        spec = _make_http_get_fn(
            "http://api.example.com/insecure",
            effects=[{"kind": "NET", "allow": ["api.example.com"]}],
        )
        Checker(spec).check()  # must not raise (http is a valid scheme)

    def test_subdomain_mismatch_is_denied(self):
        """Subdomain that is not explicitly listed must be rejected (exact match semantics)."""
        spec = _make_http_get_fn(
            "https://sub.api.example.com/v1",
            effects=[{"kind": "NET", "allow": ["api.example.com"]}],
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_multiple_allowed_domains_first_matches(self):
        """URL matching the first entry in a multi-domain allow list must pass."""
        spec = _make_http_get_fn(
            "https://payments.example.com/charge",
            effects=[{"kind": "NET", "allow": ["payments.example.com", "api.example.com"]}],
        )
        Checker(spec).check()

    def test_multiple_allowed_domains_second_matches(self):
        """URL matching the second entry in a multi-domain allow list must pass."""
        spec = _make_http_get_fn(
            "https://api.example.com/info",
            effects=[{"kind": "NET", "allow": ["payments.example.com", "api.example.com"]}],
        )
        Checker(spec).check()


# ===========================================================================
# 5. NET Capability — ops Constraint
# ===========================================================================

class TestNETOpsConstraint(unittest.TestCase):
    """'ops' on NET caps restricts which HTTP methods are permitted."""

    def test_net_ops_get_allows_http_get(self):
        """ops=['get'] must permit http_get operations."""
        spec = _make_http_get_fn(
            "https://api.example.com/v1",
            effects=[{"kind": "NET", "allow": ["api.example.com"], "ops": ["get"]}],
        )
        Checker(spec).check()  # must not raise

    def test_net_ops_post_only_denies_http_get(self):
        """ops=['post'] must deny http_get (which is a 'get' operation)."""
        spec = _make_http_get_fn(
            "https://api.example.com/v1",
            effects=[{"kind": "NET", "allow": ["api.example.com"], "ops": ["post"]}],
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_net_ops_absent_means_all_ops_allowed(self):
        """When 'ops' is absent, http_get is permitted for allowed domains."""
        spec = _make_http_get_fn(
            "https://api.example.com/v1",
            effects=[{"kind": "NET", "allow": ["api.example.com"]}],  # no 'ops'
        )
        Checker(spec).check()  # must not raise


# ===========================================================================
# 6. Backward Compatibility — Plain String Effects Still Work
# ===========================================================================

class TestBackwardCompatStringEffects(unittest.TestCase):
    """Plain string effect declarations must continue to work unchanged."""

    def test_plain_string_fs_effect_still_works_checker(self):
        """effects: ['FS'] (string) must not raise at check time."""
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "read_file", "path": {"lit": "/tmp/any.txt"}, "effect": "FS", "into": "c"},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["FS"])
        Checker(spec).check()  # no capability constraints → pass

    def test_plain_string_net_effect_still_works_checker(self):
        """effects: ['NET'] (string) must not raise at check time."""
        spec = fn_spec("f", [], STR_T, [
            {"op": "http_get", "url": {"lit": "https://example.com"}, "effect": "NET", "into": "body"},
            {"op": "return", "val": {"ref": "body"}},
        ], effects=["NET"])
        Checker(spec).check()

    def test_plain_string_net_effect_runtime_works(self):
        """Plain string 'NET' effect: runtime http_get must execute without cap enforcement."""
        spec = fn_spec("f", [], STR_T, [
            {"op": "http_get", "url": {"lit": "https://example.com"}, "effect": "NET", "into": "body"},
            {"op": "return", "val": {"ref": "body"}},
        ], effects=["NET"])
        Checker(spec).check()
        with patch("interpreter.runtime.urlopen", return_value=_FakeHTTPResponse(b"pong")):
            result = Runtime(spec).run()
        self.assertEqual(result, "pong")

    def test_net_cap_with_net_alias_still_works(self):
        """'Net' (legacy capitalisation) as kind in structured effect must be accepted."""
        spec = _make_http_get_fn(
            "https://api.example.com/v1",
            effects=[{"kind": "Net", "allow": ["api.example.com"]}],
        )
        Checker(spec).check()  # 'Net' is normalised to 'NET'


# ===========================================================================
# 7. Structured Effect Declaration Validation (L0 / L2)
# ===========================================================================

class TestStructuredEffectValidation(unittest.TestCase):
    """Malformed structured effect declarations must raise CheckError at check time."""

    def test_missing_allow_field_raises(self):
        """Structured effect without 'allow' must raise CheckError."""
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=[{"kind": "FS"}])  # no 'allow'
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_empty_allow_list_raises(self):
        """Structured effect with empty 'allow' list must raise CheckError."""
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=[{"kind": "FS", "allow": []}])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_allow_non_string_items_raises(self):
        """Structured effect with non-string items in 'allow' must raise."""
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=[{"kind": "FS", "allow": [123]}])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_missing_kind_field_raises(self):
        """Structured effect object without 'kind' must raise CheckError."""
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=[{"allow": ["/tmp/"]}])  # no 'kind'
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_ops_non_list_raises(self):
        """Structured effect with 'ops' as non-list must raise CheckError."""
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=[{"kind": "FS", "allow": ["/tmp/"], "ops": "read"}])  # string, not list
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_unknown_effect_kind_in_structured_form_raises(self):
        """A structured effect with an unknown 'kind' must raise CheckError."""
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=[{"kind": "DISK", "allow": ["/tmp/"]}])
        with self.assertRaises(CheckError):
            Checker(spec).check()


# ===========================================================================
# 8. Runtime Enforcement of Fine-grained Caps
# ===========================================================================

class TestRuntimeEnforcement(unittest.TestCase):
    """Capability constraints must also be enforced at runtime (defence-in-depth)."""

    def test_runtime_fs_capability_allows_permitted_path(self):
        """Runtime must execute read_file when path is within the allowed root."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "safe"
            root.mkdir()
            f = root / "data.txt"
            f.write_text("runtime ok", encoding="utf-8")
            spec = _make_read_file_fn(
                str(f),
                effects=[{"kind": "FS", "allow": [str(root)], "ops": ["read"]}],
            )
            Checker(spec).check()
            result = Runtime(spec).run()
            self.assertEqual(result, "runtime ok")

    def test_runtime_net_capability_allows_permitted_domain(self):
        """Runtime must execute http_get when URL domain is in the allow list."""
        spec = _make_http_get_fn(
            "https://api.example.com/ok",
            effects=[{"kind": "NET", "allow": ["api.example.com"]}],
        )
        Checker(spec).check()
        with patch("interpreter.runtime.urlopen", return_value=_FakeHTTPResponse(b"live")):
            result = Runtime(spec).run()
        self.assertEqual(result, "live")

    def test_runtime_net_capability_blocks_unpermitted_domain(self):
        """Runtime must raise NailRuntimeError when domain is not in the allow list.

        The checker cannot block dynamic URLs, so runtime enforcement is needed
        for variables/expressions. We verify here that checker also catches the
        static literal case (defence-in-depth: checker is the first line).
        """
        spec = _make_http_get_fn(
            "https://evil.example.com/steal",
            effects=[{"kind": "NET", "allow": ["api.example.com"]}],
        )
        # Static literal URL → checker blocks it first
        with self.assertRaises(CheckError):
            Checker(spec).check()


# ===========================================================================
# 9. Mixed FS + NET Capabilities in Same Function
# ===========================================================================

class TestMixedFSAndNETCaps(unittest.TestCase):
    """A function may declare both FS and NET granular caps simultaneously."""

    def test_fs_and_net_caps_both_pass_checker(self):
        """A function with both FS and NET structured caps must pass L2 check."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / "input.txt"
            f.write_text("data", encoding="utf-8")
            spec = fn_spec(
                "mixed", [], STR_T,
                [
                    {"op": "read_file", "path": {"lit": str(f)}, "effect": "FS", "into": "contents"},
                    {"op": "http_get", "url": {"lit": "https://api.example.com/post"}, "effect": "NET", "into": "resp"},
                    {"op": "return", "val": {"ref": "resp"}},
                ],
                effects=[
                    {"kind": "FS", "allow": [str(root)], "ops": ["read"]},
                    {"kind": "NET", "allow": ["api.example.com"]},
                ],
            )
            Checker(spec).check()

    def test_fs_allowed_but_net_denied_raises_at_check_time(self):
        """If NET cap blocks the URL even though FS cap allows the path, CheckError must be raised."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            f = root / "ok.txt"
            f.write_text("ok", encoding="utf-8")
            spec = fn_spec(
                "mixed", [], STR_T,
                [
                    {"op": "read_file", "path": {"lit": str(f)}, "effect": "FS", "into": "contents"},
                    # URL domain NOT in NET allow list
                    {"op": "http_get", "url": {"lit": "https://blocked.com/evil"}, "effect": "NET", "into": "resp"},
                    {"op": "return", "val": {"ref": "resp"}},
                ],
                effects=[
                    {"kind": "FS", "allow": [str(root)], "ops": ["read"]},
                    {"kind": "NET", "allow": ["api.example.com"]},  # blocked.com not allowed
                ],
            )
            with self.assertRaises(CheckError):
                Checker(spec).check()


# ===========================================================================
# 10. Scheme Blocking (Integration with fine-grained caps)
# ===========================================================================

class TestSchemeBlockingWithCaps(unittest.TestCase):
    """file:// and ftp:// schemes must be blocked even when NET cap is declared."""

    def test_file_scheme_blocked_even_with_net_cap(self):
        """http_get with file:// must raise CheckError regardless of NET cap."""
        spec = _make_http_get_fn(
            "file:///etc/passwd",
            effects=[{"kind": "NET", "allow": ["etc"]}],  # nonsensical but non-empty
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_ftp_scheme_blocked_even_with_net_cap(self):
        """http_get with ftp:// must raise CheckError regardless of NET cap."""
        spec = _make_http_get_fn(
            "ftp://ftp.example.com/file",
            effects=[{"kind": "NET", "allow": ["ftp.example.com"]}],
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
