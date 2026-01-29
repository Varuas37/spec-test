"""spec-test: Specification-driven development with test verification."""

from .contracts import (
    ContractError,
    ContractInfo,
    Old,
    contract,
    get_contract_for_spec,
    get_contract_registry,
)
from .decorators import get_spec_registry, spec, specs
from .prover import (
    ProofOutcome,
    ProofResult,
    ProvableInfo,
    clear_provable_registry,
    get_provable_for_spec,
    get_provable_registry,
    provable,
    verify_function,
)
from .reporter import Reporter
from .types import (
    RelatedIssue,
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
    "Old",
    "get_contract_registry",
    "get_contract_for_spec",
    # Types
    "RelatedIssue",
    "SpecStatus",
    "SpecRequirement",
    "SpecTest",
    "SpecResult",
    "VerificationReport",
    "VerificationType",
    # Classes
    "SpecVerifier",
    "Reporter",
    # Prover (Z3)
    "provable",
    "ProofResult",
    "ProofOutcome",
    "ProvableInfo",
    "verify_function",
    "get_provable_registry",
    "get_provable_for_spec",
    "clear_provable_registry",
]
