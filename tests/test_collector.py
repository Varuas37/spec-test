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


@spec("COL-003", "Collector handles nested directories")
def test_collector_handles_nested_directories():
    """Test that collector finds spec-*.md files in nested directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested structure
        nested = Path(tmpdir) / "subdir" / "deep"
        nested.mkdir(parents=True)

        (Path(tmpdir) / "spec-root.md").write_text("- **ROOT-001**: Root spec")
        (nested / "spec-nested.md").write_text("- **NEST-001**: Nested spec")

        specs = collect_specs(tmpdir)

        spec_ids = {s.id for s in specs}
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
