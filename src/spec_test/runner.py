"""Run tests and collect results."""

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .types import SpecTest


def discover_spec_tests(tests_dir: str | Path) -> dict[str, SpecTest]:
    """
    Discover all tests decorated with @spec.

    Returns:
        Dict mapping spec_id -> SpecTest
    """
    tests_path = Path(tests_dir)
    if not tests_path.exists():
        return {}

    return _discover_from_files(tests_path)


def _discover_from_files(tests_dir: Path) -> dict[str, SpecTest]:
    """Parse test files to find @spec decorators."""
    spec_tests: dict[str, SpecTest] = {}

    for py_file in tests_dir.glob("**/*.py"):
        if py_file.name.startswith("__"):
            continue

        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            spec_info = _extract_spec_decorator(node)
            if spec_info:
                spec_id, description = spec_info
                # Use file path format for pytest: /path/to/file.py::test_name
                test_path = f"{py_file}::{node.name}"

                spec_tests[spec_id] = SpecTest(
                    spec_id=spec_id,
                    description=description,
                    test_path=test_path,
                    test_file=py_file,
                    test_line=node.lineno,
                )

    return spec_tests


def _extract_spec_decorator(node: ast.FunctionDef) -> Optional[tuple[str, str]]:
    """Extract @spec decorator info from a function node."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Name) and func.id == "spec":
                args = decorator.args
                if len(args) >= 2:
                    spec_id = _get_string_value(args[0])
                    description = _get_string_value(args[1])
                    if spec_id and description:
                        return (spec_id, description)
    return None


def _get_string_value(node: ast.expr) -> Optional[str]:
    """Extract string value from AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _get_env_with_pythonpath() -> dict[str, str]:
    """Get environment with current Python path included."""
    env = os.environ.copy()
    # Ensure the current Python's site-packages are available
    python_path = os.pathsep.join(sys.path)
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = python_path + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = python_path
    return env


def run_test(test_path: str, tests_dir: Path) -> tuple[bool, Optional[str]]:
    """
    Run a specific test and return pass/fail status.

    Returns:
        Tuple of (passed: bool, error_message: Optional[str])
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            test_path,
            "-v",
            "--tb=short",
            "--no-header",
            "-p",
            "no:spec_test",  # Disable our plugin to avoid recursion
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env=_get_env_with_pythonpath(),
    )

    passed = result.returncode == 0
    error_message = None if passed else result.stdout + result.stderr

    return passed, error_message


def run_tests_by_spec_id(spec_id: str, tests_dir: Path) -> tuple[bool, Optional[str]]:
    """Run all tests for a given spec ID."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(tests_dir),
            "-v",
            "-m",
            f"spec_id({spec_id})",
            "--tb=short",
            "-p",
            "no:spec_test",  # Disable our plugin to avoid recursion
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env=_get_env_with_pythonpath(),
    )

    passed = result.returncode == 0
    error_message = None if passed else result.stdout + result.stderr

    return passed, error_message
