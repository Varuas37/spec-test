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

        # Process top-level functions
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                spec_info = _extract_spec_decorator(node)
                if spec_info:
                    spec_id, description = spec_info
                    test_path = f"{py_file}::{node.name}"
                    spec_tests[spec_id] = SpecTest(
                        spec_id=spec_id,
                        description=description,
                        test_path=test_path,
                        test_file=py_file,
                        test_line=node.lineno,
                    )

            # Process methods inside classes
            elif isinstance(node, ast.ClassDef):
                class_name = node.name
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        spec_info = _extract_spec_decorator(item)
                        if spec_info:
                            spec_id, description = spec_info
                            # pytest format: file.py::ClassName::method_name
                            test_path = f"{py_file}::{class_name}::{item.name}"
                            spec_tests[spec_id] = SpecTest(
                                spec_id=spec_id,
                                description=description,
                                test_path=test_path,
                                test_file=py_file,
                                test_line=item.lineno,
                            )

    return spec_tests


def _extract_spec_decorator(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Optional[tuple[str, str]]:
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


def run_tests_batch(test_paths: list[str], tests_dir: Path) -> dict[str, tuple[bool, Optional[str]]]:
    """
    Run multiple tests in a single pytest invocation for performance.

    Returns:
        Dict mapping test_path -> (passed, error_message)
    """
    if not test_paths:
        return {}

    # Run all tests in a single pytest invocation
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *test_paths,
            "-v",
            "--tb=line",  # Shorter output for batch runs
            "--no-header",
            "-p",
            "no:spec_test",  # Disable our plugin to avoid recursion
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
        env=_get_env_with_pythonpath(),
    )

    # Parse pytest output to extract per-test results
    results: dict[str, tuple[bool, Optional[str]]] = {}

    # Parse the output - look for test result lines
    output = result.stdout + result.stderr
    lines = output.split('\n')

    for line in lines:
        # Match pytest verbose output: "test_file.py::test_name PASSED" or "FAILED"
        # Example: "tests/test_contracts.py::test_contract_validates_preconditions PASSED    [ 50%]"
        if '::' in line:
            # Check for status keywords
            status_found = None
            for status_keyword in ['PASSED', 'FAILED', 'ERROR', 'SKIPPED']:
                if status_keyword in line:
                    status_found = status_keyword
                    break

            if status_found:
                # Extract test identifier (everything before the status)
                # Split on whitespace and get the first part
                parts = line.split()
                if len(parts) >= 2:
                    test_identifier = parts[0]

                    # Match against our test paths
                    # pytest outputs can be relative (with ../ prefix) or absolute
                    # Our test_paths are typically absolute
                    for test_path in test_paths:
                        # Normalize both paths by resolving them and comparing
                        # Split into file path and test node (::test_name)
                        test_path_parts = test_path.split('::')
                        test_id_parts = test_identifier.split('::')

                        # Match if the test nodes (after ::) match
                        # and the file paths resolve to the same file
                        matches = False

                        if test_path == test_identifier:
                            # Exact match
                            matches = True
                        elif len(test_path_parts) == len(test_id_parts) and test_path_parts[1:] == test_id_parts[1:]:
                            # Test nodes match, now check if file paths point to same file
                            try:
                                # Normalize the pytest output path (might have ../ prefix)
                                # by resolving it from current working directory
                                test_id_file = Path(test_id_parts[0]).resolve()
                                test_path_file = Path(test_path_parts[0]).resolve()

                                if test_id_file == test_path_file:
                                    matches = True
                            except (ValueError, OSError):
                                # If path resolution fails, fall back to string matching
                                if test_path_parts[0].endswith(test_id_parts[0]) or test_id_parts[0].endswith(test_path_parts[0]):
                                    matches = True

                        if matches:
                            if status_found in ['PASSED']:
                                results[test_path] = (True, None)
                            elif status_found in ['FAILED']:
                                # Extract error from subsequent lines (simplified)
                                error_msg = f"Test failed: {test_identifier}"
                                results[test_path] = (False, error_msg)
                            elif status_found in ['ERROR']:
                                error_msg = f"Test error: {test_identifier}"
                                results[test_path] = (False, error_msg)
                            elif status_found in ['SKIPPED']:
                                results[test_path] = (True, None)  # Treat skipped as passing for spec purposes
                            break

    # Mark any tests that didn't appear in output as failed
    for test_path in test_paths:
        if test_path not in results:
            results[test_path] = (False, "Test did not run or was not found")

    return results


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
