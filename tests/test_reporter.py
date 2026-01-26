"""Tests for the reporter."""

import tempfile
from io import StringIO
from pathlib import Path

import pytest

from spec_test import spec
from spec_test.reporter import Reporter
from spec_test.types import (
    SpecRequirement,
    SpecResult,
    SpecStatus,
    SpecTest,
    VerificationReport,
)


def make_spec(id: str, desc: str) -> SpecRequirement:
    """Helper to create a spec requirement."""
    return SpecRequirement(
        id=id,
        description=desc,
        source_file=Path("test.md"),
        source_line=1,
    )


def make_test(spec_id: str) -> SpecTest:
    """Helper to create a spec test."""
    return SpecTest(
        spec_id=spec_id,
        description="Test",
        test_path=f"tests::test_{spec_id.lower()}",
        test_file=Path("test.py"),
        test_line=1,
    )


@spec("REP-001", "Reporter prints colored terminal output")
def test_reporter_prints_terminal_output(capsys):
    """Test that reporter produces terminal output."""
    results = [
        SpecResult(
            spec=make_spec("TEST-001", "Passing"),
            status=SpecStatus.PASSING,
            test=make_test("TEST-001"),
        ),
        SpecResult(spec=make_spec("TEST-002", "Failing"), status=SpecStatus.FAILING),
    ]
    report = VerificationReport(results=results)

    reporter = Reporter()
    reporter.print_terminal(report)

    captured = capsys.readouterr()
    assert "TEST-001" in captured.out
    assert "TEST-002" in captured.out
    assert "PASS" in captured.out
    assert "FAIL" in captured.out


@spec("REP-002", "Reporter generates markdown file")
def test_reporter_generates_markdown():
    """Test that reporter can generate markdown output."""
    results = [
        SpecResult(
            spec=make_spec("TEST-001", "Test spec"),
            status=SpecStatus.PASSING,
            test=make_test("TEST-001"),
        ),
    ]
    report = VerificationReport(results=results)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        output_path = Path(f.name)

    try:
        reporter = Reporter()
        reporter.generate_markdown(report, output_path)

        content = output_path.read_text()
        assert "# Specification Status Report" in content
        assert "TEST-001" in content
        assert "PASS" in content
    finally:
        output_path.unlink()


@spec("REP-003", "Reporter shows coverage percentage")
def test_reporter_shows_coverage(capsys):
    """Test that reporter displays coverage percentage."""
    results = [
        SpecResult(
            spec=make_spec("TEST-001", "Pass"),
            status=SpecStatus.PASSING,
            test=make_test("TEST-001"),
        ),
        SpecResult(
            spec=make_spec("TEST-002", "Pass"),
            status=SpecStatus.PASSING,
            test=make_test("TEST-002"),
        ),
    ]
    report = VerificationReport(results=results)

    reporter = Reporter()
    reporter.print_terminal(report)

    captured = capsys.readouterr()
    assert "Coverage:" in captured.out
    assert "100.0%" in captured.out


@spec("REP-004", "Reporter lists failures with details")
def test_reporter_lists_failures(capsys):
    """Test that reporter shows failure details."""
    results = [
        SpecResult(
            spec=make_spec("FAIL-001", "Failing test"),
            status=SpecStatus.FAILING,
            error_message="AssertionError",
        ),
        SpecResult(spec=make_spec("MISS-001", "Missing test"), status=SpecStatus.PENDING),
    ]
    report = VerificationReport(results=results)

    reporter = Reporter()
    reporter.print_terminal(report)

    captured = capsys.readouterr()
    assert "Issues Found" in captured.out
    assert "FAIL-001" in captured.out
    assert "MISS-001" in captured.out
