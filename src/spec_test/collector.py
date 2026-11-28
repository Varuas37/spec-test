"""Collect specifications from markdown files."""

import re
from pathlib import Path
from typing import Iterator, Optional

from .types import RelatedIssue, SpecRequirement, VerificationType

# Pattern: **SPEC-001**: Description
# Or: - **SPEC-001**: Description
# Or with tags: **SPEC-001** [SKIP]: Description
# Or with multiple tags: **SPEC-001** [manual] [SKIP]: Description
SPEC_PATTERN = re.compile(
    r"\*\*([A-Z][A-Z0-9]*-\d+)\*\*"  # **SPEC-001**
    r"((?:\s*\[\w+\])*)"  # Optional tags like [manual] [SKIP]
    r":\s*(.+?)$",  # : Description
    re.MULTILINE,
)

# Pattern to extract individual tags
TAG_PATTERN = re.compile(r"\[(\w+)\]")

# Pattern: - [ISSUE-001: Title](path/to/issue.md)
# Or: - [Title](path/to/issue.md)
ISSUE_LINK_PATTERN = re.compile(
    r"-\s*\[([^\]]+)\]\(([^)]+\.md)\)",  # - [Title](path.md)
    re.MULTILINE,
)


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
    for md_file in sorted(specs_path.glob("**/*.md")):
        # Skip files starting with underscore (like _index.md for internal use)
        if md_file.name.startswith("_"):
            continue
        specs.extend(_parse_spec_file(md_file))

    return specs


def _parse_spec_file(file_path: Path) -> Iterator[SpecRequirement]:
    """Parse a single markdown file for spec requirements."""
    content = file_path.read_text()
    lines = content.split("\n")

    # Extract related issues from file (applies to all specs in file)
    related_issues = _extract_related_issues(content, file_path)

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
        if {"skip", "future"} & set(tags_lower):
            verification_type = VerificationType.SKIP
        elif {"manual", "ai_review"} & set(tags_lower):
            verification_type = VerificationType.MANUAL
        elif "provable" in tags_lower:
            verification_type = VerificationType.PROOF
        elif "model" in tags_lower:
            verification_type = VerificationType.MODEL
        elif "property" in tags_lower:
            verification_type = VerificationType.PROPERTY
        else:
            verification_type = VerificationType.TEST

        yield SpecRequirement(
            id=spec_id,
            description=description,
            source_file=file_path,
            source_line=line_num,
            verification_type=verification_type,
            related_issues=related_issues,
            review_notes=_review_notes(lines, line_num) if "ai_review" in tags_lower else None,
        )


def _review_notes(lines: list[str], source_line: int) -> Optional[str]:
    # The first line following the declaration may carry the author's review hint.
    if source_line < len(lines):
        note = re.fullmatch(r"\s*<!--\s*ai:\s*(.*?)\s*-->\s*", lines[source_line])
        if note:
            return note.group(1)
    return None


def _extract_related_issues(content: str, file_path: Path) -> list[RelatedIssue]:
    """Extract related issue references from a spec file.

    Looks for a "Related Issue" or "Related Issues" section and extracts
    markdown links to issue files.
    """
    issues = []

    # Find the Related Issue(s) section
    # Match "## Related Issue" or "## Related Issues"
    section_pattern = re.compile(
        r"##\s*Related\s+Issues?\s*\n((?:.*\n)*?)(?=\n##|\Z)",
        re.IGNORECASE,
    )

    section_match = section_pattern.search(content)
    if not section_match:
        return issues

    section_content = section_match.group(1)

    # Extract all markdown links in the section
    for match in ISSUE_LINK_PATTERN.finditer(section_content):
        title = match.group(1)
        rel_path = match.group(2)

        # Resolve path relative to spec file
        abs_path = (file_path.parent / rel_path).resolve()

        issues.append(RelatedIssue(
            title=title,
            path=str(abs_path),
        ))

    return issues


def collect_spec_ids(specs_dir: str | Path) -> set[str]:
    """Collect just the spec IDs (for quick lookups)."""
    return {spec.id for spec in collect_specs(specs_dir)}
