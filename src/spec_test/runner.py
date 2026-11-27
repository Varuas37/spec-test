"""Run tests and collect results."""

import ast
import json
import os
import subprocess
import sys
import tempfile
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

    return {key: group[0] for key, group in discover_spec_test_groups(tests_path).items()}


def discover_spec_test_groups(tests_dir: str | Path) -> dict[str, list[SpecTest]]:
    """Discover every linked test, preserving repeated spec IDs."""
    groups: dict[str, list[SpecTest]] = {}
    for file in sorted(Path(tests_dir).glob("**/*.py")):
        if file.name.startswith("__"):
            continue
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            scope = node.body if isinstance(node, ast.ClassDef) else [node]
            for item in scope:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                prefix = f"{node.name}::" if isinstance(node, ast.ClassDef) else ""
                for spec_id, description, evidence_kind in _spec_decorators(item):
                    test = SpecTest(
                        spec_id, description, f"{file}::{prefix}{item.name}", file,
                        item.lineno, evidence_kind,
                    )
                    groups.setdefault(spec_id, []).append(test)
    return groups


def _spec_decorators(node):
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Name):
            continue
        name = decorator.func.id
        if name == "specs":
            for value in decorator.args:
                if spec_id := _get_string_value(value):
                    yield spec_id, node.name, "test"
            continue
        if name not in {"spec", "property_test"}:
            continue
        args = decorator.args
        kw = {arg.arg: arg.value for arg in decorator.keywords}
        spec_id = _get_string_value(args[0] if args else kw.get("spec_id"))
        description = _get_string_value(args[1] if len(args) > 1 else kw.get("description"))
        if spec_id and (description or name == "property_test"):
            yield spec_id, description or node.name, "property" if name == "property_test" else "test"


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
    """Compatibility wrapper for callers that need a pass/fail result."""
    return run_tests_batch([test_path], tests_dir)[test_path]


def run_tests_batch(test_paths: list[str], tests_dir: Path) -> dict[str, tuple[bool, Optional[str]]]:
    return {
        path: (status == "passed", detail)
        for path, (status, detail) in run_test_receipts(test_paths).items()
    }


def _node_key(node_id: str, root: Path) -> tuple[Path, str]:
    file, _, nodes = node_id.partition("::")
    return (root / file).resolve(), nodes


def run_test_receipts(test_paths: list[str]) -> dict[str, tuple[str, Optional[str]]]:
    paths = list(dict.fromkeys(test_paths))
    if not paths:
        return {}
    with tempfile.TemporaryDirectory() as directory:
        receipt = Path(directory) / "pytest.json"
        proc = subprocess.run(
            [
                sys.executable, "-m", "pytest", *paths, "-q", "--tb=line",
                "-p", "no:spec_test", "-p", "spec_test.pytest_receipt",
                "--spec-test-receipt", str(receipt),
            ],
            capture_output=True, text=True, env=_get_env_with_pythonpath(),
        )
        if not receipt.is_file() or proc.returncode not in (0, 1):
            reason = (proc.stderr or proc.stdout).strip()[-1000:]
            return {path: ("unknown", reason or "pytest did not finish") for path in paths}
        data = json.loads(receipt.read_text(encoding="utf-8"))

    exact: dict[tuple[Path, str], str] = {}
    groups: dict[tuple[Path, str], list[str]] = {}
    deselected = set(data["deselected"]) - set(data["selected"])
    all_cases = set(data["selected"]) | deselected | data["tests"].keys()
    for node_id in all_cases:
        key = _node_key(node_id, Path(data["root"]))
        stages = data["tests"].get(node_id, [])
        if node_id in deselected:
            state = "unknown"
        elif any(outcome == "failed" for _, outcome, _ in stages):
            state = "failed"
        elif any(outcome == "skipped" or xfail for _, outcome, xfail in stages):
            state = "skipped"
        elif {phase for phase, outcome, _ in stages if outcome == "passed"} == {
            "setup", "call", "teardown"
        }:
            state = "passed"
        else:
            state = "unknown"
        exact[key] = state
        file, nodes = key
        groups.setdefault((file, nodes.split("[", 1)[0]), []).append(state)

    results = {}
    for path in paths:
        key = _node_key(path, Path.cwd())
        observed = [exact.get(key, "unknown")] if "[" in key[1] else groups.get(key, [])
        state = next(
            (s for s in ("failed", "unknown", "skipped", "passed") if s in observed), "unknown"
        )
        results[path] = (state, None if state == "passed" else f"pytest evidence {state}: {path}")
    return results
