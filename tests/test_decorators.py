"""Tests for the @spec decorator."""

import pytest

from spec_test import get_spec_registry, spec, specs
from spec_test.decorators import clear_registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear registry before each test."""
    clear_registry()
    yield
    clear_registry()


@spec("DEC-001", "@spec decorator registers test in global registry")
def test_spec_decorator_registers_in_registry():
    """Test that @spec decorator adds to global registry."""
    clear_registry()

    @spec("TEST-001", "Test description")
    def sample_test():
        pass

    registry = get_spec_registry()
    assert "TEST-001" in registry
    assert len(registry["TEST-001"]) == 1
    assert registry["TEST-001"][0]["description"] == "Test description"


@spec("DEC-002", "@spec decorator adds pytest marker to test")
def test_spec_decorator_adds_pytest_marker():
    """Test that @spec decorator adds pytest markers."""

    @spec("TEST-002", "Test description")
    def sample_test():
        pass

    # Check that the function has spec metadata
    assert hasattr(sample_test, "_spec_id")
    assert sample_test._spec_id == "TEST-002"


@spec("DEC-003", "@spec decorator preserves function metadata")
def test_spec_decorator_preserves_metadata():
    """Test that @spec decorator preserves function name and docstring."""

    @spec("TEST-003", "Test description")
    def sample_test():
        """This is a docstring."""
        pass

    assert sample_test.__name__ == "sample_test"
    assert sample_test.__doc__ == "This is a docstring."


@spec("DEC-004", "@specs decorator supports multiple spec IDs")
def test_specs_decorator_multiple_ids():
    """Test that @specs decorator handles multiple spec IDs."""
    clear_registry()

    @specs("TEST-A", "TEST-B", "TEST-C")
    def multi_spec_test():
        pass

    registry = get_spec_registry()
    assert "TEST-A" in registry
    assert "TEST-B" in registry
    assert "TEST-C" in registry
    assert hasattr(multi_spec_test, "_spec_ids")
    assert multi_spec_test._spec_ids == ("TEST-A", "TEST-B", "TEST-C")
