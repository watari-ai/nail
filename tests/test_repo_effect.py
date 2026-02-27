#!/usr/bin/env python3
"""
NAIL REPO Effect Type + exec_cmd Operation — Test Suite

Tests: REPO effect declaration validation, exec_cmd checker (L2),
exec_cmd runtime execution, and REPO capability enforcement.

Run: pytest tests/test_repo_effect.py
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, Runtime, CheckError, NailRuntimeError
from interpreter.types import NailEffectError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STR_T = {"type": "string"}
UNIT_T = {"type": "unit"}
INT64 = {"type": "int", "bits": 64, "overflow": "panic"}


def fn_spec(fn_id, params, returns, body, effects=None):
    return {
        "nail": "0.9",
        "kind": "fn",
        "id": fn_id,
        "meta": {"spec_version": "0.9.0"},
        "effects": effects or [],
        "params": params,
        "returns": returns,
        "body": body,
    }


def module_spec(mod_id, defs):
    return {
        "nail": "0.9",
        "kind": "module",
        "id": mod_id,
        "meta": {"spec_version": "0.9.0"},
        "defs": defs,
    }


def check(spec):
    c = Checker(spec)
    c.check()
    return c


def run_fn_spec(spec, args=None):
    r = Runtime(spec)
    return r.run(args or {})


# ---------------------------------------------------------------------------
# TestRepoEffectDeclaration
# ---------------------------------------------------------------------------

class TestRepoEffectDeclaration(unittest.TestCase):
    """Tests for REPO effect declaration parsing and validation."""

    def test_repo_string_effect_valid(self):
        """Coarse-grained REPO as a plain string is valid."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [{"op": "return_void"}],
            effects=["REPO"],
        )
        c = check(spec)
        self.assertIn("REPO", c.declared_effects)

    def test_repo_structured_effect_valid(self):
        """Fine-grained REPO with proper owner/repo allow list is valid."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [{"op": "return_void"}],
            effects=[{"kind": "REPO", "allow": ["watari-ai/nail", "zyom45/moldium"]}],
        )
        c = check(spec)
        self.assertIn("REPO", c.declared_effects)
        self.assertIn("REPO", c.declared_effect_caps)

    def test_repo_invalid_allow_format_no_slash(self):
        """owner/repo format required — plain string without slash is rejected."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [{"op": "return_void"}],
            effects=[{"kind": "REPO", "allow": ["not-a-repo"]}],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("owner/repo", str(ctx.exception))

    def test_repo_invalid_allow_format_too_many_slashes(self):
        """owner/repo format required — multiple slashes are rejected."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [{"op": "return_void"}],
            effects=[{"kind": "REPO", "allow": ["owner/repo/extra"]}],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("owner/repo", str(ctx.exception))

    def test_repo_invalid_allow_format_path_traversal(self):
        """Path traversal like ../evil is rejected."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [{"op": "return_void"}],
            effects=[{"kind": "REPO", "allow": ["../evil"]}],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("owner/repo", str(ctx.exception))

    def test_repo_invalid_chars_in_allow(self):
        """Special characters in owner/repo parts are rejected."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [{"op": "return_void"}],
            effects=[{"kind": "REPO", "allow": ["owner!bad/repo"]}],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("invalid characters", str(ctx.exception))

    def test_unknown_effect_still_rejected(self):
        """Unknown effect kinds (other than REPO/IO/FS/etc.) are still rejected."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [{"op": "return_void"}],
            effects=["GIT"],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("Unknown effect kind", str(ctx.exception))


# ---------------------------------------------------------------------------
# TestExecCmdOperation
# ---------------------------------------------------------------------------

class TestExecCmdOperation(unittest.TestCase):
    """Checker (L2) tests for exec_cmd operation."""

    def _echo_body(self, effect="IO", repo=None, cmd="echo hello"):
        stmt = {
            "op": "exec_cmd",
            "cmd": {"lit": cmd},
            "effect": effect,
        }
        if repo is not None:
            stmt["repo"] = {"lit": repo}
        return [stmt, {"op": "return_void"}]

    def test_exec_cmd_io_effect_valid(self):
        """exec_cmd with effect=IO and IO declared is valid."""
        spec = fn_spec(
            "f", [], UNIT_T,
            self._echo_body(effect="IO"),
            effects=["IO"],
        )
        # Should not raise
        check(spec)

    def test_exec_cmd_repo_effect_valid(self):
        """exec_cmd with effect=REPO and REPO declared is valid."""
        spec = fn_spec(
            "f", [], UNIT_T,
            self._echo_body(effect="REPO", repo="watari-ai/nail"),
            effects=["REPO"],
        )
        # Should not raise
        check(spec)

    def test_exec_cmd_repo_missing_repo_field(self):
        """exec_cmd with effect=REPO but missing repo field raises CheckError."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [
                {"op": "exec_cmd", "cmd": {"lit": "git push"}, "effect": "REPO"},
                {"op": "return_void"},
            ],
            effects=["REPO"],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("requires 'repo' field", str(ctx.exception))

    def test_exec_cmd_repo_not_in_allow_list(self):
        """exec_cmd with fine-grained REPO caps but repo not in allow list raises CheckError."""
        spec = fn_spec(
            "f", [], UNIT_T,
            self._echo_body(effect="REPO", repo="evil/repo"),
            effects=[{"kind": "REPO", "allow": ["watari-ai/nail"]}],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("not in declared REPO allow list", str(ctx.exception))

    def test_exec_cmd_io_without_io_effect(self):
        """exec_cmd with effect=IO but IO not declared raises CheckError."""
        spec = fn_spec(
            "f", [], UNIT_T,
            self._echo_body(effect="IO"),
            effects=[],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("does not declare it", str(ctx.exception))

    def test_exec_cmd_repo_without_repo_effect(self):
        """exec_cmd with effect=REPO but REPO not declared raises CheckError."""
        spec = fn_spec(
            "f", [], UNIT_T,
            self._echo_body(effect="REPO", repo="watari-ai/nail"),
            effects=[],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("does not declare it", str(ctx.exception))

    def test_exec_cmd_invalid_effect_value(self):
        """exec_cmd with an effect other than IO or REPO raises CheckError."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [
                {"op": "exec_cmd", "cmd": {"lit": "ls"}, "effect": "FS"},
                {"op": "return_void"},
            ],
            effects=["FS"],
        )
        with self.assertRaises(CheckError) as ctx:
            check(spec)
        self.assertIn("must be 'IO' or 'REPO'", str(ctx.exception))

    def test_exec_cmd_into_binding(self):
        """exec_cmd with 'into' does not cause a type error at check time."""
        spec = fn_spec(
            "f", [], UNIT_T,
            [
                {
                    "op": "exec_cmd",
                    "cmd": {"lit": "echo hello"},
                    "effect": "IO",
                    "into": "result",
                },
                {"op": "return_void"},
            ],
            effects=["IO"],
        )
        # Should not raise
        check(spec)

    def test_exec_cmd_coarse_repo_any_literal_ok(self):
        """With coarse REPO (no allow list), any literal repo is accepted."""
        spec = fn_spec(
            "f", [], UNIT_T,
            self._echo_body(effect="REPO", repo="any/repo"),
            effects=["REPO"],
        )
        # Should not raise
        check(spec)


# ---------------------------------------------------------------------------
# TestExecCmdRuntime
# ---------------------------------------------------------------------------

class TestExecCmdRuntime(unittest.TestCase):
    """Runtime execution tests for exec_cmd operation."""

    def _build_spec(self, effect, repo=None, cmd="echo hello", effects=None):
        stmt = {
            "op": "exec_cmd",
            "cmd": {"lit": cmd},
            "effect": effect,
            "into": "result",
        }
        if repo is not None:
            stmt["repo"] = {"lit": repo}
        body = [stmt, {"op": "return_void"}]
        return fn_spec("f", [], UNIT_T, body, effects=effects or [effect])

    @patch("subprocess.run")
    def test_exec_cmd_io_runs_command(self, mock_run):
        """exec_cmd with IO effect actually calls subprocess.run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="hello\n", stderr="")
        spec = self._build_spec("IO")
        r = Runtime(spec)
        r.run()
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        self.assertEqual(call_kwargs[0][0], "echo hello")

    @patch("subprocess.run")
    def test_exec_cmd_repo_allowed_passes(self, mock_run):
        """exec_cmd with REPO effect and repo in allow list passes."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        spec = self._build_spec(
            "REPO",
            repo="watari-ai/nail",
            cmd="git push origin main",
            effects=[{"kind": "REPO", "allow": ["watari-ai/nail"]}],
        )
        r = Runtime(spec)
        r.run()  # Should not raise
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_exec_cmd_repo_blocked_raises_runtime_error(self, mock_run):
        """exec_cmd with REPO effect but repo not in allow list raises NailRuntimeError."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        spec = self._build_spec(
            "REPO",
            repo="evil/repo",
            cmd="git push",
            effects=[{"kind": "REPO", "allow": ["watari-ai/nail"]}],
        )
        r = Runtime(spec)
        with self.assertRaises(NailRuntimeError) as ctx:
            r.run()
        self.assertIn("REPO_VIOLATION", str(ctx.exception.code))

    @patch("subprocess.run")
    def test_exec_cmd_captures_stdout_stderr(self, mock_run):
        """exec_cmd result map contains stdout and stderr."""
        mock_run.return_value = MagicMock(returncode=0, stdout="output text\n", stderr="err text\n")
        body = [
            {
                "op": "exec_cmd",
                "cmd": {"lit": "some-cmd"},
                "effect": "IO",
                "into": "result",
            },
            {"op": "return", "val": {"ref": "result"}},
        ]
        spec = fn_spec("f", [], {"type": "map", "key": {"type": "string"}, "value": {"type": "string"}}, body, effects=["IO"])
        r = Runtime(spec)
        result = r.run()
        self.assertEqual(result["stdout"], "output text\n")
        self.assertEqual(result["stderr"], "err text\n")
        self.assertEqual(result["exit_code"], 0)

    @patch("subprocess.run")
    def test_exec_cmd_exit_code_nonzero(self, mock_run):
        """exec_cmd correctly captures nonzero exit codes."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error occurred\n")
        body = [
            {
                "op": "exec_cmd",
                "cmd": {"lit": "false"},
                "effect": "IO",
                "into": "result",
            },
            {"op": "return", "val": {"ref": "result"}},
        ]
        spec = fn_spec("f", [], {"type": "map", "key": {"type": "string"}, "value": {"type": "string"}}, body, effects=["IO"])
        r = Runtime(spec)
        result = r.run()
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["stderr"], "error occurred\n")

    def test_exec_cmd_io_without_effect_raises_runtime_error(self):
        """exec_cmd at runtime raises if IO effect not declared in function."""
        # Build a spec where effect field is IO but function declares no effects.
        # We bypass the checker by constructing Runtime directly.
        body = [
            {"op": "exec_cmd", "cmd": {"lit": "echo hi"}, "effect": "IO"},
            {"op": "return_void"},
        ]
        raw_spec = {
            "nail": "0.9",
            "kind": "fn",
            "id": "f",
            "meta": {"spec_version": "0.9.0"},
            "effects": [],
            "params": [],
            "returns": UNIT_T,
            "body": body,
        }
        r = Runtime(raw_spec)
        with self.assertRaises(NailRuntimeError) as ctx:
            r.run()
        self.assertIn("EFFECT_VIOLATION", str(ctx.exception.code))


# ---------------------------------------------------------------------------
# TestRepoCapabilityEnforcement
# ---------------------------------------------------------------------------

class TestRepoCapabilityEnforcement(unittest.TestCase):
    """Tests for fine-grained vs coarse-grained REPO capability enforcement."""

    @patch("subprocess.run")
    def test_coarse_repo_effect_no_restriction(self, mock_run):
        """Coarse REPO (no allow list) imposes no restriction on which repos can be used."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        spec = fn_spec(
            "f", [], UNIT_T,
            [
                {
                    "op": "exec_cmd",
                    "cmd": {"lit": "git push"},
                    "effect": "REPO",
                    "repo": {"lit": "any/repo"},
                },
                {"op": "return_void"},
            ],
            effects=["REPO"],
        )
        r = Runtime(spec)
        r.run()  # Should not raise
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_fine_grained_repo_allows_declared(self, mock_run):
        """Fine-grained REPO with allow list allows accessing a declared repo."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        spec = fn_spec(
            "f", [], UNIT_T,
            [
                {
                    "op": "exec_cmd",
                    "cmd": {"lit": "git push"},
                    "effect": "REPO",
                    "repo": {"lit": "watari-ai/nail"},
                },
                {"op": "return_void"},
            ],
            effects=[{"kind": "REPO", "allow": ["watari-ai/nail"]}],
        )
        r = Runtime(spec)
        r.run()  # Should not raise
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_fine_grained_repo_blocks_undeclared(self, mock_run):
        """Fine-grained REPO with allow list blocks accessing an undeclared repo."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        spec = fn_spec(
            "f", [], UNIT_T,
            [
                {
                    "op": "exec_cmd",
                    "cmd": {"lit": "git push"},
                    "effect": "REPO",
                    "repo": {"lit": "evil/repo"},
                },
                {"op": "return_void"},
            ],
            effects=[{"kind": "REPO", "allow": ["watari-ai/nail"]}],
        )
        r = Runtime(spec)
        with self.assertRaises(NailRuntimeError) as ctx:
            r.run()
        self.assertEqual(ctx.exception.code, "REPO_VIOLATION")
        # subprocess.run should not have been called (error thrown before execution)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_multiple_repos_in_allow_list(self, mock_run):
        """Fine-grained REPO with multiple repos in allow list allows any declared repo."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        effects = [{"kind": "REPO", "allow": ["watari-ai/nail", "zyom45/moldium"]}]

        for repo in ["watari-ai/nail", "zyom45/moldium"]:
            mock_run.reset_mock()
            spec = fn_spec(
                "f", [], UNIT_T,
                [
                    {
                        "op": "exec_cmd",
                        "cmd": {"lit": "git pull"},
                        "effect": "REPO",
                        "repo": {"lit": repo},
                    },
                    {"op": "return_void"},
                ],
                effects=effects,
            )
            r = Runtime(spec)
            r.run()  # Should not raise
            mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_exec_cmd_cwd_is_passed_to_subprocess(self, mock_run):
        """exec_cmd with cwd field passes cwd to subprocess.run."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        spec = fn_spec(
            "f", [], UNIT_T,
            [
                {
                    "op": "exec_cmd",
                    "cmd": {"lit": "git status"},
                    "effect": "REPO",
                    "repo": {"lit": "watari-ai/nail"},
                    "cwd": {"lit": "/Users/w/nail"},
                },
                {"op": "return_void"},
            ],
            effects=["REPO"],
        )
        r = Runtime(spec)
        r.run()
        call_kwargs = mock_run.call_args[1]
        self.assertEqual(call_kwargs.get("cwd"), "/Users/w/nail")


if __name__ == "__main__":
    unittest.main()
