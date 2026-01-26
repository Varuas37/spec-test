"""Type definitions for spec-test."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path


class SpecStatus(Enum):
    """Status of a specification requirement."""
    PENDING = "pending"          # No test written yet
    PASSING = "passing"          # Test exists and passes
    FAILING = "failing"          # Test exists but fails
    SKIPPED = "skipped"          # Explicitly skipped


class VerificationType(Enum):
    """How a spec should be verified."""
    TEST = "test"                # Standard pytest test
    MANUAL = "manual"            # Requires human verification


@dataclass
class SpecRequirement:
    """A single specification requirement parsed from markdown."""
    id: str
    description: str
    source_file: Path
    source_line: int
    verification_type: VerificationType = VerificationType.TEST

    def __hash__(self):
        return hash(self.id)


@dataclass
class SpecTest:
    """A test linked to a specification."""
    spec_id: str
    description: str
    test_path: str          # module::function format
    test_file: Path
    test_line: int


@dataclass
class SpecResult:
    """Result of verifying a single spec."""
    spec: SpecRequirement
    status: SpecStatus
    test: Optional[SpecTest] = None
    error_message: Optional[str] = None


@dataclass
class VerificationReport:
    """Complete verification report."""
    results: list[SpecResult]
    total_specs: int = 0
    passing: int = 0
    failing: int = 0
    missing: int = 0

    def __post_init__(self):
        self.total_specs = len(self.results)
        self.passing = sum(1 for r in self.results if r.status == SpecStatus.PASSING)
        self.failing = sum(1 for r in self.results if r.status == SpecStatus.FAILING)
        self.missing = sum(1 for r in self.results if r.status == SpecStatus.PENDING)

    @property
    def coverage_percent(self) -> float:
        if self.total_specs == 0:
            return 100.0
        return (self.passing / self.total_specs) * 100

    @property
    def is_passing(self) -> bool:
        return self.failing == 0 and self.missing == 0
