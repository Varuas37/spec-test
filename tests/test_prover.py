"""Tests for Z3 formal proof verification."""

import pytest

from spec_test import spec
from spec_test.contracts import contract
from spec_test.prover import (
    ProofOutcome,
    ProofResult,
    ProvableInfo,
    Z3_AVAILABLE,
    clear_provable_registry,
    get_provable_for_spec,
    get_provable_registry,
    provable,
    verify_function,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear provable registry before each test."""
    clear_provable_registry()
    yield
    clear_provable_registry()


@spec("Z3-001", "@provable decorator registers functions")
def test_provable_decorator_registers():
    """Test that @provable decorator registers functions in registry."""

    @provable(spec="TEST-001")
    @contract(
        requires=[lambda x: x >= 0],
        ensures=[lambda result: result >= 0],
    )
    def test_func(x: int) -> int:
        return x

    registry = get_provable_registry()
    assert "TEST-001" in registry
    assert registry["TEST-001"].func_name == "test_func"


@spec("Z3-002", "@provable stores info on function")
def test_provable_stores_info_on_function():
    """Test that @provable stores ProvableInfo on the function."""

    @provable(spec="TEST-002", timeout=60)
    @contract(ensures=[lambda r: r > 0])
    def my_func(x: int) -> int:
        return x + 1

    assert hasattr(my_func, "_provable_info")
    info = my_func._provable_info
    assert isinstance(info, ProvableInfo)
    assert info.spec_id == "TEST-002"
    assert info.timeout == 60


@spec("Z3-003", "get_provable_for_spec retrieves by ID")
def test_get_provable_for_spec():
    """Test retrieving provable info by spec ID."""

    @provable(spec="LOOKUP-001")
    @contract(ensures=[lambda r: True])
    def lookup_func(x: int) -> int:
        return x

    result = get_provable_for_spec("LOOKUP-001")
    assert result is not None
    assert result.func_name == "lookup_func"

    # Non-existent spec
    assert get_provable_for_spec("NONEXISTENT") is None


@spec("Z3-004", "verify_function skips without Z3")
def test_verify_function_skips_without_z3():
    """Test that verify_function gracefully handles missing Z3."""
    if Z3_AVAILABLE:
        pytest.skip("Z3 is available, skipping no-Z3 test")

    @provable(spec="SKIP-001")
    @contract(ensures=[lambda r: r >= 0])
    def skip_func(x: int) -> int:
        return x

    outcome = verify_function(skip_func)
    assert outcome.result == ProofResult.SKIPPED
    assert "Z3 not installed" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-005", "verify_function requires @provable")
def test_verify_function_requires_provable():
    """Test that verify_function skips functions without @provable."""

    def plain_func(x: int) -> int:
        return x

    outcome = verify_function(plain_func)
    assert outcome.result == ProofResult.SKIPPED
    assert "not marked with @provable" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-006", "verify_function requires @contract")
def test_verify_function_requires_contract():
    """Test that verify_function skips functions without @contract."""

    @provable(spec="NO-CONTRACT")
    def no_contract_func(x: int) -> int:
        return x

    outcome = verify_function(no_contract_func)
    assert outcome.result == ProofResult.SKIPPED
    assert "no @contract" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-007", "verify_function proves simple postcondition")
def test_verify_function_proves_simple():
    """Test that verify_function can prove simple postconditions."""

    @provable(spec="PROVE-001")
    @contract(
        requires=[lambda x: x >= 0],
        ensures=[lambda result: result >= 0],
    )
    def identity(x: int) -> int:
        return x

    outcome = verify_function(identity)
    assert outcome.result == ProofResult.PROVEN
    assert outcome.spec_id == "PROVE-001"


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-008", "verify_function refutes invalid postcondition")
def test_verify_function_refutes_invalid():
    """Test that verify_function finds counter-examples."""

    @provable(spec="REFUTE-001")
    @contract(
        requires=[lambda x: x >= 0],
        ensures=[lambda result: result > 10],  # Invalid for x <= 10
    )
    def identity(x: int) -> int:
        return x

    outcome = verify_function(identity)
    assert outcome.result == ProofResult.REFUTED
    assert outcome.counter_example is not None


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-009", "verify_function handles arithmetic postconditions")
def test_verify_function_arithmetic():
    """Test Z3 verification with arithmetic postconditions."""

    @provable(spec="ARITH-001")
    @contract(
        requires=[lambda x, y: x >= 0, lambda x, y: y >= 0],
        ensures=[lambda result: result >= 0],
    )
    def add(x: int, y: int) -> int:
        return x + y

    outcome = verify_function(add)
    assert outcome.result == ProofResult.PROVEN


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-010", "verify_function handles comparison chains")
def test_verify_function_comparisons():
    """Test Z3 verification with comparison chains."""

    @provable(spec="CMP-001")
    @contract(
        requires=[lambda x: 0 <= x <= 100],
        ensures=[lambda result: 0 <= result <= 100],
    )
    def clamp(x: int) -> int:
        return x

    outcome = verify_function(clamp)
    assert outcome.result == ProofResult.PROVEN


@spec("Z3-011", "ProofOutcome contains timing info")
def test_proof_outcome_has_timing():
    """Test that ProofOutcome includes proof_time_ms."""
    outcome = ProofOutcome(
        result=ProofResult.PROVEN,
        function_name="test",
        proof_time_ms=42.5,
    )
    assert outcome.proof_time_ms == 42.5


@spec("Z3-012", "ProvableInfo.full_name combines module and func")
def test_provable_info_full_name():
    """Test that ProvableInfo.full_name works correctly."""
    info = ProvableInfo(
        spec_id="TEST",
        func_name="my_func",
        func_module="my_module",
        timeout=30,
        skip_runtime_if_proven=False,
    )
    assert info.full_name == "my_module.my_func"


@spec("Z3-013", "clear_provable_registry clears all entries")
def test_clear_registry():
    """Test that clear_provable_registry removes all entries."""

    @provable(spec="CLEAR-001")
    @contract(ensures=[lambda r: True])
    def func1(x: int) -> int:
        return x

    @provable(spec="CLEAR-002")
    @contract(ensures=[lambda r: True])
    def func2(x: int) -> int:
        return x

    assert len(get_provable_registry()) == 2

    clear_provable_registry()

    assert len(get_provable_registry()) == 0


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-014", "verify_function handles boolean operations")
def test_verify_function_boolean():
    """Test Z3 verification with boolean operations in conditions."""

    @provable(spec="BOOL-001")
    @contract(
        requires=[lambda x, y: x >= 0 and y >= 0],
        ensures=[lambda result: result >= 0],
    )
    def multiply(x: int, y: int) -> int:
        return x * y

    outcome = verify_function(multiply)
    assert outcome.result == ProofResult.PROVEN


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-015", "verify_function handles real numbers")
def test_verify_function_reals():
    """Test Z3 verification with float types."""

    @provable(spec="REAL-001")
    @contract(
        requires=[lambda x: x >= 0.0],
        ensures=[lambda result: result >= 0.0],
    )
    def square(x: float) -> float:
        return x * x

    outcome = verify_function(square)
    assert outcome.result == ProofResult.PROVEN
