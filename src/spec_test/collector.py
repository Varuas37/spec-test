"""Collect specifications from markdown files."""

import re
from pathlib import Path
from typing import Iterator

from .types import SpecRequirement, VerificationType

# Pattern: **SPEC-001**: Description
# Or: - **SPEC-001**: Description
# Or with verification type: **SPEC-001** [manual]: Description
SPEC_PATTERN = re.compile(
    r"\*\*([A-Z]+-\d+)\*\*"  # **SPEC-001**
    r"(?:\s*\[(\w+)\])?"  # Optional [verification_type]
    r":\s*(.+?)$",  # : Description
    re.MULTILINE,
)


def collect_specs(specs_dir: str | Path) -> list[SpecRequirement]:
    """
    Collect all specification requirements from spec-*.md files.

    Args:
        specs_dir: Directory to search for spec-*.md files (searches recursively)

    Returns:
        List of SpecRequirement objects
    """
    specs_path = Path(specs_dir)
    if not specs_path.exists():
        return []

    specs = []
    # Only collect from files matching spec-*.md pattern
    for md_file in specs_path.glob("**/spec-*.md"):
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
        verification_type_str = match.group(2)
        description = match.group(3).strip()

        # Determine verification type
        if verification_type_str:
            try:
                verification_type = VerificationType(verification_type_str.lower())
            except ValueError:
                verification_type = VerificationType.TEST
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
