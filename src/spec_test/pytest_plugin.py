"""pytest plugin for spec-test integration."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "spec: mark test as linked to a specification")
    config.addinivalue_line("markers", "spec_id(id): mark test with specific spec ID")
