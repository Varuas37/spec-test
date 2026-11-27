"""Type definitions for spec-test."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path

from .evidence import Evidence


class SpecStatus(Enum):
    """Status of a specification requirement."""
    PENDING = "pending"          # No test written yet
    PASSING = "passing"          # Test exists and passes
    FAILING = "failing"          # Test exists but fails
    UNKNOWN = "unknown"          # Inconclusive or required evidence did not run
    SKIPPED = "skipped"          # Explicitly skipped


class VerificationType(Enum):
    """How a spec should be verified."""
    TEST = "test"                # Standard pytest test
    PROPERTY = "property"       # Generated cases against the implementation
    PROOF = "implementation-proof"
    MODEL = "model-proof"
    MANUAL = "manual"            # Requires human verification
    SKIP = "skip"                # Skipped - not implemented yet


@dataclass
class RelatedIssue:
    """A reference to a related issue from a spec file."""
    title: str
    path: str  # Relative path to issue file

    @property
    def exists(self) -> bool:
        """Check if the issue file exists (relative to spec file)."""
        return Path(self.path).is_file()


@dataclass
class SpecRequirement:
    """A single specification requirement parsed from markdown."""
    id: str
    description: str
    source_file: Path
    source_line: int
    verification_type: VerificationType = VerificationType.TEST
    related_issues: list[RelatedIssue] = field(default_factory=list)
    review_notes: Optional[str] = None

    def __hash__(self):
        return hash(self.id)

    @property
    def has_issue(self) -> bool:
        """Check if this spec has at least one related issue."""
        return len(self.related_issues) > 0


@dataclass
class SpecTest:
    """A test linked to a specification."""
    spec_id: str
    description: str
    test_path: str          # module::function format
    test_file: Path
    test_line: int
    evidence_kind: str = "test"


@dataclass
class SpecResult:
    """Result of verifying a single spec."""
    spec: SpecRequirement
    status: SpecStatus
    test: Optional[SpecTest] = None
    error_message: Optional[str] = None
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class VerificationReport:
    """Complete verification report."""
    results: list[SpecResult]
    total_specs: int = 0
    passing: int = 0
    failing: int = 0
    missing: int = 0
    skipped: int = 0
    unknown: int = 0
    evidence: list[Evidence] = field(default_factory=list)

    def __post_init__(self):
        self.total_specs = len(self.results)
        self.passing = sum(1 for r in self.results if r.status == SpecStatus.PASSING)
        self.failing = sum(1 for r in self.results if r.status == SpecStatus.FAILING)
        self.missing = sum(1 for r in self.results if r.status == SpecStatus.PENDING)
        self.unknown = sum(1 for r in self.results if r.status == SpecStatus.UNKNOWN)
        self.skipped = sum(1 for r in self.results if r.status == SpecStatus.SKIPPED)

    @property
    def coverage_percent(self) -> float:
        if self.total_specs == 0:
            return 0.0
        return (self.passing / self.total_specs) * 100

    @property
    def is_passing(self) -> bool:
        return self.failing == 0 and self.missing == 0 and self.unknown == 0
