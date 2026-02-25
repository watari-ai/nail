#!/usr/bin/env python3
"""
Test for Issue #82: `nail demo <name>` must propagate subprocess exit code.

Before the fix, `subprocess.run(...)` returncode was discarded so `nail demo`
always exited 0 even when the demo script itself failed.

After the fix:
    proc = subprocess.run([sys.executable, str(script)])
    sys.exit(proc.returncode)

Both success (0) and failure (non-zero) exit codes must be forwarded.

Run: python -m pytest tests/test_issue_82_demo_exit_code.py -v
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from nail_cli import main


def _make_proc(returncode: int) -> MagicMock:
    """Return a mock subprocess.CompletedProcess-like object."""
    m = MagicMock()
    m.returncode = returncode
    return m


class TestDemoExitCodePropagation(unittest.TestCase):
    """nail demo <name> must forward the demo subprocess's exit code."""

    def _run_demo(self, demo_name: str, returncode: int) -> int:
        """Run `nail demo <demo_name>` with subprocess.run mocked to return *returncode*.

        Returns the exit code that main() raised via SystemExit.
        """
        with patch('sys.argv', ['nail', 'demo', demo_name]):
            with patch('subprocess.run', return_value=_make_proc(returncode)):
                with self.assertRaises(SystemExit) as ctx:
                    main()
        return ctx.exception.code

    # ── Pass cases (demo subprocess exits 0) ───────────────────────────────

    def test_termination_demo_exit_zero(self):
        """`nail demo termination` exits 0 when demo subprocess exits 0."""
        code = self._run_demo('termination', 0)
        self.assertEqual(code, 0)

    def test_rogue_agent_demo_exit_zero(self):
        """`nail demo rogue-agent` exits 0 when demo subprocess exits 0."""
        code = self._run_demo('rogue-agent', 0)
        self.assertEqual(code, 0)

    def test_verifiability_demo_exit_zero(self):
        """`nail demo verifiability` exits 0 when demo subprocess exits 0."""
        code = self._run_demo('verifiability', 0)
        self.assertEqual(code, 0)

    # ── Fail cases (demo subprocess exits non-zero) ────────────────────────

    def test_demo_propagates_exit_code_1(self):
        """`nail demo` propagates exit code 1 (general failure) from demo subprocess."""
        code = self._run_demo('termination', 1)
        self.assertEqual(code, 1)

    def test_demo_propagates_exit_code_2(self):
        """`nail demo` propagates exit code 2 (another failure) from demo subprocess."""
        code = self._run_demo('rogue-agent', 2)
        self.assertEqual(code, 2)

    def test_demo_propagates_exit_code_42(self):
        """`nail demo` propagates arbitrary non-zero exit codes."""
        code = self._run_demo('verifiability', 42)
        self.assertEqual(code, 42)

    # ── subprocess.run is called with the correct arguments ───────────────

    def test_subprocess_called_with_python_and_script_path(self):
        """`subprocess.run` is invoked with [sys.executable, <script_path>]."""
        with patch('sys.argv', ['nail', 'demo', 'termination']):
            with patch('subprocess.run', return_value=_make_proc(0)) as mock_run:
                with self.assertRaises(SystemExit):
                    main()
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]  # first positional arg (the command list)
        self.assertEqual(call_args[0], sys.executable)
        self.assertTrue(str(call_args[1]).endswith('.py'),
                        f"Expected a .py script path, got: {call_args[1]}")
        self.assertIn('termination', str(call_args[1]))

    # ── Unknown demo names still exit 1 ───────────────────────────────────

    def test_unknown_demo_name_exits_one(self):
        """`nail demo nonexistent` still exits 1 (unknown demo)."""
        with patch('sys.argv', ['nail', 'demo', 'nonexistent-demo']):
            with self.assertRaises(SystemExit) as ctx:
                main()
        self.assertEqual(ctx.exception.code, 1)

    def test_demo_list_exits_zero(self):
        """`nail demo --list` exits 0 (just lists available demos)."""
        with patch('sys.argv', ['nail', 'demo', '--list']):
            with self.assertRaises(SystemExit) as ctx:
                main()
        self.assertEqual(ctx.exception.code, 0)

    def test_demo_no_args_exits_zero(self):
        """`nail demo` (no args) exits 0 (lists available demos)."""
        with patch('sys.argv', ['nail', 'demo']):
            with self.assertRaises(SystemExit) as ctx:
                main()
        self.assertEqual(ctx.exception.code, 0)


class TestDemoSubprocessNotCalled(unittest.TestCase):
    """subprocess.run should NOT be called for list/unknown cases."""

    def test_subprocess_not_called_for_list(self):
        with patch('sys.argv', ['nail', 'demo', '--list']):
            with patch('subprocess.run') as mock_run:
                with self.assertRaises(SystemExit):
                    main()
        mock_run.assert_not_called()

    def test_subprocess_not_called_for_unknown_demo(self):
        with patch('sys.argv', ['nail', 'demo', 'does-not-exist']):
            with patch('subprocess.run') as mock_run:
                with self.assertRaises(SystemExit):
                    main()
        mock_run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
