"""Collect specifications from markdown files."""

import re
from pathlib import Path
from typing import Iterator

from .types import SpecRequirement, VerificationType

# Pattern: **SPEC-001**: Description
# Or: - **SPEC-001**: Description
# Or with tags: **SPEC-001** [SKIP]: Description
# Or with multiple tags: **SPEC-001** [manual] [SKIP]: Description
SPEC_PATTERN = re.compile(
    r"\*\*([A-Z]+-\d+)\*\*"  # **SPEC-001**
    r"((?:\s*\[\w+\])*)"  # Optional tags like [manual] [SKIP]
    r":\s*(.+?)$",  # : Description
    re.MULTILINE,
)

# Pattern to extract individual tags
TAG_PATTERN = re.compile(r"\[(\w+)\]")


def collect_specs(specs_dir: str | Path) -> list[SpecRequirement]:
    """
    Collect all specification requirements from markdown files.

    Args:
        specs_dir: Directory to search for .md files (recursive within specs/)

    Returns:
        List of SpecRequirement objects
    """
    specs_path = Path(specs_dir)
    if not specs_path.exists():
        return []

    specs = []
    # Collect from all .md files in specs directory (recursive)
    for md_file in specs_path.glob("**/*.md"):
        # Skip files starting with underscore (like _index.md for internal use)
        if md_file.name.startswith("_"):
            continue
        specs.extend(_parse_spec_file(md_file))

    return specs


def _parse_spec_file(file_path: Path) -> Iterator[SpecRequirement]:
    """Parse a single markdown file for spec requirements."""
    content = file_path.read_text()
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        match = SPEC_PATTERN.search(line)
        if not match:
            continue

        spec_id = match.group(1)
        tags_str = match.group(2)
        description = match.group(3).strip()

        # Parse tags
        tags = TAG_PATTERN.findall(tags_str) if tags_str else []
        tags_lower = [t.lower() for t in tags]

        # Determine verification type (priority: skip > manual > test)
        if "skip" in tags_lower:
            verification_type = VerificationType.SKIP
        elif "manual" in tags_lower:
            verification_type = VerificationType.MANUAL
        else:
            verification_type = VerificationType.TEST

        yield SpecRequirement(
            id=spec_id,
            description=description,
            source_file=file_path,
            source_line=line_num,
            verification_type=verification_type,
        )


def collect_spec_ids(specs_dir: str | Path) -> set[str]:
    """Collect just the spec IDs (for quick lookups)."""
    return {spec.id for spec in collect_specs(specs_dir)}
