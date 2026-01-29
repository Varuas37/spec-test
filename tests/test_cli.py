"""Tests for the CLI."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from spec_test import spec
from spec_test.cli import app

runner = CliRunner()


@spec("CLI-001", "`verify` command runs full verification")
def test_verify_command_runs():
    """Test that verify command executes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create minimal spec and test
        specs_dir = tmpdir / "docs" / "specs"
        specs_dir.mkdir(parents=True)
        (specs_dir / "spec-cli.md").write_text("- **CLI-TEST-001**: Test spec")

        tests_dir = tmpdir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_cli.py").write_text("""
from spec_test import spec

@spec("CLI-TEST-001", "Test spec")
def test_something():
    assert True
""")

        # Change to temp directory for test
        import os

        orig_dir = os.getcwd()
        try:
            os.chdir(tmpdir)
            result = runner.invoke(app, ["verify", "-s", str(specs_dir), "-t", str(tests_dir)])
            assert "Specification Verification Report" in result.output
        finally:
            os.chdir(orig_dir)


@spec("CLI-002", "`list-specs` command shows all specs")
def test_list_specs_command():
    """Test that list-specs command shows specs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        specs_dir = Path(tmpdir)
        (specs_dir / "spec-list.md").write_text("""
- **LIST-001**: First spec
- **LIST-002**: Second spec
""")

        result = runner.invoke(app, ["list-specs", "-s", str(specs_dir)])

        assert result.exit_code == 0
        assert "LIST-001" in result.output
        assert "LIST-002" in result.output
        assert "Found 2 specifications" in result.output


@spec("CLI-003", "`check` command verifies single spec")
def test_check_command():
    """Test that check command verifies a single spec."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        specs_dir = tmpdir / "specs"
        specs_dir.mkdir()
        (specs_dir / "spec-check.md").write_text("- **CHECK-001**: Single spec to check")

        tests_dir = tmpdir / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")

        result = runner.invoke(
            app, ["check", "CHECK-001", "-s", str(specs_dir), "-t", str(tests_dir)]
        )

        assert "CHECK-001" in result.output


@spec("CLI-004", "`init` command scaffolds project")
def test_init_command():
    """Test that init command creates design directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = runner.invoke(app, ["init", tmpdir])

        assert result.exit_code == 0
        assert "Created" in result.output
        assert "design" in result.output
        assert "CLAUDE.md" in result.output

        # Check design directories were created
        design_dir = Path(tmpdir) / "design"
        assert design_dir.exists()
        assert (design_dir / "specs").exists()
        assert (design_dir / "issues").exists()
        assert (design_dir / "prompts").exists()

        # Check example files were created
        example_spec = design_dir / "specs" / "example.md"
        assert example_spec.exists()

        example_issue = design_dir / "issues" / "001-example.md"
        assert example_issue.exists()

        # Check CLAUDE.md was created
        claude_file = Path(tmpdir) / "CLAUDE.md"
        assert claude_file.exists()


@spec("CLI-005", "Exit code 1 on test failures")
def test_exit_code_on_failures():
    """Test that CLI exits with code 1 when tests fail."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        specs_dir = tmpdir / "specs"
        specs_dir.mkdir()
        (specs_dir / "spec-fail.md").write_text("- **FAIL-001**: Failing test")

        tests_dir = tmpdir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_fail.py").write_text("""
from spec_test import spec

@spec("FAIL-001", "Failing test")
def test_fails():
    assert False, "This test fails"
""")

        import os

        orig_dir = os.getcwd()
        try:
            os.chdir(tmpdir)
            result = runner.invoke(app, ["verify", "-s", str(specs_dir), "-t", str(tests_dir)])
            assert result.exit_code == 1
        finally:
            os.chdir(orig_dir)


@spec("CLI-006", "Exit code 2 on missing tests (when --fail-on-missing)")
def test_exit_code_on_missing():
    """Test that CLI exits with code 2 when specs have no tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        specs_dir = tmpdir / "specs"
        specs_dir.mkdir()
        (specs_dir / "spec-miss.md").write_text("- **MISS-001**: Missing test")

        tests_dir = tmpdir / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")

        import os

        orig_dir = os.getcwd()
        try:
            os.chdir(tmpdir)
            result = runner.invoke(
                app, ["verify", "-s", str(specs_dir), "-t", str(tests_dir), "--fail-on-missing"]
            )
            assert result.exit_code == 2
        finally:
            os.chdir(orig_dir)
