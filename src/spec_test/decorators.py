"""Decorators for linking tests to specifications."""

import functools
from typing import Callable, Optional

import pytest

# Global registry: spec_id -> list of test paths
_spec_registry: dict[str, list[dict]] = {}


def spec(
    spec_id: str,
    description: str,
    verification_notes: Optional[str] = None,
):
    """
    Decorator that links a test function to a specification requirement.

    Args:
        spec_id: Unique identifier matching the spec doc (e.g., "AUTH-001")
        description: Brief description of what this test verifies
        verification_notes: Optional notes about how this test verifies the spec

    Usage:
        @spec("AUTH-001", "User can create API token")
        def test_create_token_returns_valid_jwt():
            ...
    """

    def decorator(func: Callable) -> Callable:
        # Register this test
        if spec_id not in _spec_registry:
            _spec_registry[spec_id] = []

        _spec_registry[spec_id].append(
            {
                "test_path": f"{func.__module__}::{func.__qualname__}",
                "description": description,
                "notes": verification_notes,
            }
        )

        # Attach metadata to function
        func._spec_id = spec_id
        func._spec_description = description
        func._spec_notes = verification_notes

        # Add pytest marker for filtering: pytest -m "spec"
        marked = pytest.mark.spec(func)
        marked = pytest.mark.spec_id(spec_id)(marked)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Preserve spec metadata on wrapper
        wrapper._spec_id = spec_id
        wrapper._spec_description = description
        wrapper._spec_notes = verification_notes

        return wrapper

    return decorator


def get_spec_registry() -> dict[str, list[dict]]:
    """Get all registered spec -> test mappings."""
    return _spec_registry.copy()


def clear_registry():
    """Clear the registry (useful for testing)."""
    _spec_registry.clear()


def specs(*spec_ids: str):
    """
    Decorator for tests that verify multiple specs.

    Usage:
        @specs("AUTH-001", "AUTH-002")
        def test_token_creation_and_validation():
            ...
    """

    def decorator(func: Callable) -> Callable:
        for spec_id in spec_ids:
            if spec_id not in _spec_registry:
                _spec_registry[spec_id] = []
            _spec_registry[spec_id].append(
                {
                    "test_path": f"{func.__module__}::{func.__qualname__}",
                    "description": f"Multi-spec test covering {', '.join(spec_ids)}",
                    "notes": None,
                }
            )

        func._spec_ids = spec_ids

        # Add markers
        marked = pytest.mark.spec(func)
        for sid in spec_ids:
            marked = pytest.mark.spec_id(sid)(marked)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._spec_ids = spec_ids
        return wrapper

    return decorator
