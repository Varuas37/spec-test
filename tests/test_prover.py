"""Tests for Z3 formal proof verification."""

import pytest

from spec_test import spec, specs
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


@spec("Z3-003", "@provable stores info on function")
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


@spec("Z3-130", "verify_function skips without Z3")
def test_verify_function_skips_without_z3(monkeypatch):
    """Exercise the no-solver entry point in either test environment."""
    monkeypatch.setattr("spec_test.prover.Z3_AVAILABLE", False)

    @provable(spec="SKIP-001")
    @contract(ensures=[lambda r: r >= 0])
    def skip_func(x: int) -> int:
        return x

    outcome = verify_function(skip_func)
    assert outcome.result == ProofResult.SKIPPED
    assert "Z3 not installed" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
def test_verify_function_requires_provable():
    """Test that verify_function skips functions without @provable."""

    def plain_func(x: int) -> int:
        return x

    outcome = verify_function(plain_func)
    assert outcome.result == ProofResult.SKIPPED
    assert "not marked with @provable" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
def test_verify_function_requires_contract():
    """Test that verify_function skips functions without @contract."""

    @provable(spec="NO-CONTRACT")
    def no_contract_func(x: int) -> int:
        return x

    outcome = verify_function(no_contract_func)
    assert outcome.result == ProofResult.SKIPPED
    assert "no @contract" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-070", "verify_function proves simple postcondition")
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
@spec("Z3-071", "verify_function refutes invalid postcondition")
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
@spec("Z3-030", "verify_function handles arithmetic postconditions")
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
@spec("Z3-021", "verify_function handles comparison chains")
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


def test_proof_outcome_has_timing():
    """Test that ProofOutcome includes proof_time_ms."""
    outcome = ProofOutcome(
        result=ProofResult.PROVEN,
        function_name="test",
        proof_time_ms=42.5,
    )
    assert outcome.proof_time_ms == 42.5


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
@spec("Z3-022", "verify_function handles boolean operations")
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
@spec("Z3-073", "Unmodeled Python scalar types do not produce a proof")
def test_float_is_not_an_exact_z3_real():
    """IEEE float operations must not be silently modeled as mathematical reals."""

    @provable(spec="REAL-001")
    @contract(
        requires=[lambda x: x >= 0.0],
        ensures=[lambda result: result >= 0.0],
    )
    def square(x: float) -> float:
        return x * x

    outcome = verify_function(square)
    assert outcome.result == ProofResult.SKIPPED


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-080", "A real counterexample replays against the function")
def test_counterexample_replays_and_uses_both_same_line_preconditions():
    from spec_test.contracts import ContractError

    @provable(spec="REPLAY-001")
    @contract(
        requires=[lambda x, y: x >= 0, lambda x, y: y >= 0],
        ensures=[lambda result: result >= 0],
    )
    def subtract(x: int, y: int) -> int:
        return x - y

    outcome = verify_function(subtract)
    assert outcome.result == ProofResult.REFUTED
    witness = outcome.counter_example
    assert witness is not None
    assert witness["x"] >= 0 and witness["y"] > witness["x"]
    with pytest.raises(ContractError) as error:
        subtract(**witness)
    assert error.value.condition_type == "ensures"


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-024", "All same-line postconditions use the exact lambda")
def test_does_not_drop_the_second_postcondition_on_the_same_line():
    @provable(spec="POST-001")
    @contract(ensures=[lambda result: result >= 0, lambda result: result > 0])
    def zero() -> int:
        return 0

    outcome = verify_function(zero)
    assert outcome.result == ProofResult.REFUTED
    assert outcome.counter_example == {}


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-134", "Contradictory assumptions cannot produce a vacuous proof")
def test_contradictory_preconditions_are_not_proven():
    @provable(spec="EMPTY-001")
    @contract(requires=[lambda x: x >= 0, lambda x: x < 0], ensures=[lambda r: r >= 0])
    def identity(x: int) -> int:
        return x

    outcome = verify_function(identity)
    assert outcome.result == ProofResult.SKIPPED
    assert "unsatisfiable" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-132", "Any unsupported predicate makes the whole proof inconclusive")
def test_does_not_drop_unsupported_postcondition():
    @provable(spec="PARTIAL-001")
    @contract(ensures=[lambda r: r >= 0, lambda r: abs(r) > 1])
    def zero() -> int:
        return 0

    assert verify_function(zero).result == ProofResult.SKIPPED


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-023", "Ternary branches are modeled according to their Boolean predicate")
def test_ternary_with_boolean_input():
    @provable(spec="IF-001")
    @contract(ensures=[lambda r: 0 <= r <= 1])
    def bit(flag: bool) -> int:
        return 1 if flag else 0

    assert verify_function(bit).result == ProofResult.PROVEN


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@pytest.mark.parametrize("mode", ["prove", "refute", "unsupported", "empty", "duplicate"])
@specs("Z3-100", "Z3-103")
def test_cli_runs_proof_in_fresh_process(tmp_path, mode):
    import os
    import subprocess
    import sys
    from pathlib import Path

    expression = {"prove": "x + 1", "refute": "x - 1", "unsupported": "x // 1", "duplicate": "x + 1"}
    if mode != "empty":
        (tmp_path / "sample.py").write_text(
            "from spec_test import contract, provable\n"
            '@provable(spec="CLI-001")\n'
            "@contract(requires=[lambda x: x >= 0], ensures=[lambda r: r >= 0])\n"
            "def example(x: int) -> int:\n"
            f"    return {expression[mode]}\n"
        )
    exe = Path(sys.executable).with_name("spec-test.exe" if os.name == "nt" else "spec-test")
    if mode == "duplicate":
        (tmp_path / "another.py").write_text((tmp_path / "sample.py").read_text())
    command = [str(exe), "verify", "--proofs", "--fail-on-unknown"]
    if mode == "duplicate":
        command.extend(["--proof-module", "another"])
    if mode != "empty":
        command.extend(["--proof-module", "sample"])
    run = subprocess.run(
        command, cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(tmp_path)},
        text=True, capture_output=True, timeout=30,
    )
    expected = {
        "prove": (0, "PROVEN"),
        "refute": (4, "REFUTED"),
        "unsupported": (4, "SKIPPED"),
        "empty": (4, "No proofs registered"),
        "duplicate": (4, "Duplicate proof spec ID"),
    }
    code, marker = expected[mode]
    assert (run.returncode, marker in run.stdout) == (code, True), run.stdout + run.stderr
    if mode == "refute":
        assert "Counter-example: {'x': 0}" in run.stdout
