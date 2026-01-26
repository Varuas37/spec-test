"""Tests for the spec verifier."""

import tempfile
from pathlib import Path

import pytest

from spec_test import spec
from spec_test.types import SpecStatus
from spec_test.verifier import SpecVerifier


@spec("VER-001", "Verifier matches specs to tests by ID")
def test_verifier_matches_specs_to_tests():
    """Test that verifier correctly matches spec IDs to test functions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create spec file
        specs_dir = tmpdir / "specs"
        specs_dir.mkdir()
        (specs_dir / "spec-match.md").write_text("- **MATCH-001**: Test matching")

        # Create test file with @spec decorator
        tests_dir = tmpdir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_match.py").write_text("""
from spec_test import spec

@spec("MATCH-001", "Test matching")
def test_matching():
    assert True
""")

        verifier = SpecVerifier(specs_dir=specs_dir, tests_dir=tests_dir)
        report = verifier.verify()

        # Should find the spec and match it to the test
        assert report.total_specs == 1
        assert report.results[0].spec.id == "MATCH-001"
        assert report.results[0].test is not None
        assert report.results[0].test.spec_id == "MATCH-001"


@spec("VER-002", "Verifier runs tests and captures pass/fail")
def test_verifier_runs_tests_and_captures_results():
    """Test that verifier actually runs tests and captures results."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        specs_dir = tmpdir / "specs"
        specs_dir.mkdir()
        (specs_dir / "spec-run.md").write_text("- **RUN-001**: Passing test")

        tests_dir = tmpdir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_run.py").write_text("""
from spec_test import spec

@spec("RUN-001", "Passing test")
def test_passes():
    assert True
""")

        verifier = SpecVerifier(specs_dir=specs_dir, tests_dir=tests_dir)
        report = verifier.verify()

        assert report.total_specs == 1
        # Test should pass
        assert report.results[0].status == SpecStatus.PASSING


@spec("VER-003", "Verifier reports missing tests as PENDING")
def test_verifier_reports_missing_tests():
    """Test that verifier marks specs without tests as PENDING."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        specs_dir = tmpdir / "specs"
        specs_dir.mkdir()
        (specs_dir / "spec-miss.md").write_text("- **MISS-001**: Missing test")

        tests_dir = tmpdir / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")  # Empty tests dir

        verifier = SpecVerifier(specs_dir=specs_dir, tests_dir=tests_dir)
        report = verifier.verify()

        assert report.total_specs == 1
        assert report.results[0].status == SpecStatus.PENDING
        assert report.missing == 1
