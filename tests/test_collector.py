"""Tests for the spec collector."""

import tempfile
from pathlib import Path

import pytest

from spec_test import spec
from spec_test.collector import _parse_spec_file, collect_specs
from spec_test.types import VerificationType


@spec("COL-001", "Collector finds specs in all .md files with **ID**: format")
def test_collector_finds_specs_in_markdown():
    """Test that collector parses **ID**: format from all .md files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_file = Path(tmpdir) / "feature.md"
        spec_file.write_text("""# Test Spec

## Requirements
- **TEST-001**: First requirement
- **TEST-002**: Second requirement
""")

        specs = collect_specs(tmpdir)

        assert len(specs) == 2
        assert specs[0].id == "TEST-001"
        assert specs[0].description == "First requirement"
        assert specs[1].id == "TEST-002"
        assert specs[1].description == "Second requirement"


@spec("COL-002", "Collector extracts verification type from [brackets]")
def test_collector_extracts_verification_type():
    """Test that collector parses [type] from spec lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_file = Path(tmpdir) / "spec-types.md"
        spec_file.write_text("""# Test Spec

- **TEST-001**: Normal spec
- **TEST-002** [manual]: Manual verification required
""")

        specs = collect_specs(tmpdir)

        assert len(specs) == 2
        assert specs[0].verification_type == VerificationType.TEST
        assert specs[1].verification_type == VerificationType.MANUAL


@spec("COL-003", "Collector searches nested directories recursively within specs/")
def test_collector_searches_nested_directories():
    """Test that collector recursively searches subdirectories within specs/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested structure
        nested = Path(tmpdir) / "subdir" / "deep"
        nested.mkdir(parents=True)

        (Path(tmpdir) / "root.md").write_text("- **ROOT-001**: Root spec")
        (nested / "nested.md").write_text("- **NEST-001**: Nested spec")

        specs = collect_specs(tmpdir)

        spec_ids = {s.id for s in specs}
        # All specs within specs/ should be collected (recursive)
        assert "ROOT-001" in spec_ids
        assert "NEST-001" in spec_ids


@spec("COL-004", "Collector skips files starting with underscore")
def test_collector_skips_underscore_files():
    """Test that collector ignores files starting with underscore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create regular files (should be collected)
        (Path(tmpdir) / "auth.md").write_text("- **AUTH-001**: Auth spec")
        (Path(tmpdir) / "feature.md").write_text("- **FEAT-001**: Feature spec")

        # Create underscore files (should be ignored)
        (Path(tmpdir) / "_index.md").write_text("- **INDEX-001**: Should be ignored")
        (Path(tmpdir) / "_internal.md").write_text("- **INT-001**: Should be ignored")

        specs = collect_specs(tmpdir)

        spec_ids = {s.id for s in specs}
        assert "AUTH-001" in spec_ids
        assert "FEAT-001" in spec_ids
        assert "INDEX-001" not in spec_ids
        assert "INT-001" not in spec_ids
        assert len(specs) == 2


@spec("COL-005", "Collector extracts related issue references from spec files")
def test_collector_extracts_related_issues():
    """Test that collector parses Related Issue section from spec files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create issues directory and issue file
        issues_dir = Path(tmpdir) / "issues"
        issues_dir.mkdir()
        (issues_dir / "001-feature.md").write_text("# ISSUE-001: Feature")

        # Create spec file with related issue
        specs_dir = Path(tmpdir) / "specs"
        specs_dir.mkdir()
        (specs_dir / "feature.md").write_text("""# Feature Spec

## Related Issue
- [ISSUE-001: Feature](../issues/001-feature.md)

## Requirements
- **FEAT-001**: First requirement
- **FEAT-002**: Second requirement
""")

        specs = collect_specs(specs_dir)

        assert len(specs) == 2
        # Both specs should have the same related issue
        for s in specs:
            assert s.has_issue
            assert len(s.related_issues) == 1
            assert "ISSUE-001" in s.related_issues[0].title


@spec("COL-006", "Collector reports specs missing related issues")
def test_collector_reports_missing_issues():
    """Test that specs without Related Issue section have empty related_issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create spec file without related issue
        spec_file = Path(tmpdir) / "no-issue.md"
        spec_file.write_text("""# Feature Spec

## Requirements
- **FEAT-001**: First requirement
""")

        specs = collect_specs(tmpdir)

        assert len(specs) == 1
        assert not specs[0].has_issue
        assert len(specs[0].related_issues) == 0
