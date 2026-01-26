"""Tests for the test runner/discovery."""

import tempfile
from pathlib import Path

import pytest

from spec_test import spec
from spec_test.runner import discover_spec_tests


@spec("RUN-001", "Runner discovers @spec decorated methods inside test classes")
def test_runner_discovers_class_methods():
    """Test that runner finds @spec decorators on methods inside test classes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test file with class-based tests
        (tmpdir / "test_class.py").write_text("""
from spec_test import spec

class TestSomething:
    @spec("CLASS-001", "Test inside a class")
    def test_in_class(self):
        assert True

    @spec("CLASS-002", "Another test inside class")
    def test_another(self):
        assert True
""")

        spec_tests = discover_spec_tests(tmpdir)

        assert "CLASS-001" in spec_tests
        assert "CLASS-002" in spec_tests
        assert spec_tests["CLASS-001"].spec_id == "CLASS-001"
        assert spec_tests["CLASS-002"].spec_id == "CLASS-002"


@spec("RUN-002", "Runner generates correct pytest node ID for class-based tests")
def test_runner_generates_correct_node_id_for_class_tests():
    """Test that runner creates pytest-compatible node IDs for class methods."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        (tmpdir / "test_nodes.py").write_text("""
from spec_test import spec

class TestMyClass:
    @spec("NODE-001", "Class method test")
    def test_method(self):
        pass

@spec("NODE-002", "Top-level function test")
def test_function():
    pass
""")

        spec_tests = discover_spec_tests(tmpdir)

        # Class method should have ClassName in the path
        assert "NODE-001" in spec_tests
        class_test_path = spec_tests["NODE-001"].test_path
        assert "::TestMyClass::" in class_test_path
        assert "::test_method" in class_test_path

        # Top-level function should NOT have a class name
        assert "NODE-002" in spec_tests
        func_test_path = spec_tests["NODE-002"].test_path
        assert "::test_function" in func_test_path
        # Should not have double colons for class
        assert func_test_path.count("::") == 1
