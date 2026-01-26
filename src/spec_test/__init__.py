"""spec-test: Specification-driven development with test verification."""

from .decorators import get_spec_registry, spec, specs
from .reporter import Reporter
from .types import (
    SpecRequirement,
    SpecResult,
    SpecStatus,
    SpecTest,
    VerificationReport,
    VerificationType,
)
from .verifier import SpecVerifier

__version__ = "0.1.0"

__all__ = [
    # Decorators
    "spec",
    "specs",
    "get_spec_registry",
    # Types
    "SpecStatus",
    "SpecRequirement",
    "SpecTest",
    "SpecResult",
    "VerificationReport",
    "VerificationType",
    # Classes
    "SpecVerifier",
    "Reporter",
]
