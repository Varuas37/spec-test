"""spec-test: Specification-driven development with test verification."""

from .contracts import (
    ContractError,
    ContractInfo,
    contract,
    get_contract_for_spec,
    get_contract_registry,
)
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

__version__ = "0.2.0"

__all__ = [
    # Decorators
    "spec",
    "specs",
    "get_spec_registry",
    # Contracts
    "contract",
    "ContractError",
    "ContractInfo",
    "get_contract_registry",
    "get_contract_for_spec",
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
