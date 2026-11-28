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

    expression = {"prove": "x + 1", "refute": "x - 1", "unsupported": "x ** 2", "duplicate": "x + 1"}
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


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-052", "Every supported control path returns its declared non-optional type")
def test_nested_conditional_returns_and_trailing_continuation():
    @provable()
    @contract(ensures=[lambda result: result >= 0])
    def magnitude(x: int, reflect: bool) -> int:
        if x < 0:
            if reflect:
                return -x
        elif x > 0:
            return x
        return 0

    assert verify_function(magnitude).result is ProofResult.PROVEN


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
def test_early_return_takes_priority_and_mutation_replays():
    @provable()
    @contract(ensures=[lambda result: result >= 0])
    def broken(x: int) -> int:
        if x < 0:
            return x
        if x < 1:
            return 0
        return x + 1

    outcome = verify_function(broken)
    assert outcome.result is ProofResult.REFUTED
    witness = outcome.counter_example
    assert witness is not None and witness["x"] < 0
    assert broken.__wrapped__.__wrapped__(**witness) < 0


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
def test_total_boolean_branches_work_without_a_trailing_return():
    @provable()
    @contract(ensures=[lambda result: result])
    def valid(flag: bool) -> bool:
        if flag:
            return flag
        else:
            return not flag

    assert verify_function(valid).result is ProofResult.PROVEN


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
def test_fallthrough_and_partial_translation_never_pass():
    @provable()
    @contract(ensures=[lambda result: result >= 0])
    def missing(x: int) -> int:
        if x < 0:
            return -x

    @provable()
    @contract(ensures=[lambda result: result >= 0])
    def unsupported(x: int) -> int:
        if x < 0:
            return abs(x)
        return x

    @provable()
    @contract(ensures=[lambda result: result >= 0])
    def mixed(x: int) -> int:
        if x < 0:
            return True
        return x

    @provable()
    @contract(ensures=[lambda result: result >= 0])
    def truthy(x: int) -> int:
        if x:
            return 1
        return 0

    for fn, reason in (
        (missing, "falls through"),
        (unsupported, "return expression"),
        (mixed, "declared type"),
        (truthy, "boolean branch"),
    ):
        outcome = verify_function(fn)
        assert outcome.result is ProofResult.SKIPPED
        assert reason in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-002", "Proof never disables runtime preconditions")
def test_successful_proof_does_not_disable_runtime_precondition():
    from spec_test.contracts import ContractError

    @provable(skip_runtime_if_proven=True)
    @contract(requires=[lambda x: x >= 0], ensures=[lambda result: result > 0])
    def increment(x: int) -> int:
        return x + 1

    assert verify_function(increment).result is ProofResult.PROVEN
    assert increment(0) == 1
    with pytest.raises(ContractError) as raised:
        increment(-1)
    assert raised.value.condition_type == "requires"


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@specs("Z3-010", "Z3-033")
def test_unbounded_integer_types_and_range_postcondition():
    @provable()
    @contract(ensures=[lambda result: -1 <= result <= 0])
    def integer_sign(x: int) -> int:
        return -1 if x < 0 else 0

    assert verify_function(integer_sign).result is ProofResult.PROVEN
    assert integer_sign(-(1 << 256)) == -1
    assert integer_sign(1 << 256) == 0


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-012", "Boolean parameters translate to Bool sorts")
def test_boolean_type_and_contract():
    @provable()
    @contract(ensures=[lambda result: result])
    def excluded_middle(flag: bool) -> bool:
        return flag or not flag

    assert verify_function(excluded_middle).result is ProofResult.PROVEN
    assert excluded_middle(False) is True
    assert excluded_middle(True) is True


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-026", "Signed integer quotient and remainder match Python")
def test_signed_floor_division_and_modulo_match_python():
    @provable()
    @contract(
        requires=[lambda x, y: y != 0, lambda x, y: -3 <= x <= 3,
                  lambda x, y: -3 <= y <= 3],
        ensures=[lambda result: result == 0],
    )
    def quotient_remainder_identity(x: int, y: int) -> int:
        return x - (x // y) * y - x % y

    @provable()
    @contract(ensures=[lambda result: -2 <= result <= 0])
    def negative_modulus(x: int) -> int:
        return x % -3

    @provable()
    @contract(requires=[lambda x: 1 <= x <= 3], ensures=[lambda result: result == -1])
    def negative_quotient(x: int) -> int:
        return x // -3

    @provable()
    @contract(requires=[lambda x: -3 <= x <= -1], ensures=[lambda result: result == -1])
    def negative_dividend(x: int) -> int:
        return x // 3

    for function in (
        quotient_remainder_identity, negative_modulus, negative_quotient, negative_dividend
    ):
        assert verify_function(function).result is ProofResult.PROVEN

    for x in range(-3, 4):
        assert negative_modulus(x) == x % -3
        for y in (-3, -2, -1, 1, 2, 3):
            assert quotient_remainder_identity(x, y) == 0
    for x in (1, 2, 3):
        assert negative_quotient(x) == -1
        assert negative_dividend(-x) == -1


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-032", "Zero-divisor safety follows the actual evaluated path")
def test_safe_paths_prove_and_refutation_replays_zero_division():
    @provable()
    @contract(
        requires=[lambda y: y != 0 or 2 > 3 > 5 // y],
        ensures=[lambda result: result == result],
    )
    def short_circuit_and_unreachable_return(y: int) -> int:
        if y == 0 and 3 == 3:
            return 1 % 0
        return (1 % y) if 1 < 0 < 5 // y else 2 // y

    @provable()
    @contract(ensures=[lambda result: result])
    def boolean_and_short_circuit(y: int) -> bool:
        return not (y != 0 and 1 % y < 0 and y > 0)

    @provable()
    @contract(ensures=[lambda result: result == result])
    def missing_guard(y: int) -> int:
        return 1 // y

    assert verify_function(short_circuit_and_unreachable_return).result is ProofResult.PROVEN
    assert short_circuit_and_unreachable_return(-3) == -1
    assert verify_function(boolean_and_short_circuit).result is ProofResult.PROVEN
    assert boolean_and_short_circuit(0) is True
    outcome = verify_function(missing_guard)
    assert outcome.result is ProofResult.REFUTED
    assert outcome.message == "Function body can divide by zero"
    assert outcome.counter_example == {"y": 0}
    with pytest.raises(ZeroDivisionError):
        missing_guard(**outcome.counter_example)


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-082", "Concrete counterexamples name their earliest failing contract clause")
def test_ordered_preconditions_and_postconditions_report_exact_clause():
    from spec_test.contracts import ContractError

    @provable()
    @contract(
        requires=[lambda y: 1 // y == 1, lambda y: y != 0],
        ensures=[lambda result: result == 1],
    )
    def invalid_requires(y: int) -> int:
        return y

    @provable()
    @contract(ensures=[lambda result: result == 0, lambda result: 1 % result == 1])
    def invalid_ensures(y: int) -> int:
        return y

    @provable()
    @contract(ensures=[lambda result: result == 0, lambda result: result > 0])
    def false_postcondition(y: int) -> int:
        return y - y

    for function, location in (
        (invalid_requires, "Precondition 1 can divide by zero"),
        (invalid_ensures, "Postcondition 2 can divide by zero"),
    ):
        outcome = verify_function(function)
        assert outcome.result is ProofResult.REFUTED
        assert outcome.message == location
        assert outcome.counter_example == {"y": 0}
        with pytest.raises(ZeroDivisionError):
            function(**outcome.counter_example)

    outcome = verify_function(false_postcondition)
    assert outcome.result is ProofResult.REFUTED
    assert outcome.message == "Postcondition 2 fails"
    with pytest.raises(ContractError) as raised:
        false_postcondition(**outcome.counter_example)
    assert raised.value.condition_index == 1


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
def test_precondition_zero_guard_cannot_make_no_inputs_proven():
    @provable()
    @contract(
        requires=[lambda y: y != 0, lambda y: y % y == 1],
        ensures=[lambda result: True],
    )
    def no_valid_inputs(y: int) -> int:
        return 1 // y

    outcome = verify_function(no_valid_inputs)
    assert outcome.result is ProofResult.SKIPPED
    assert "unsatisfiable" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@pytest.mark.parametrize("op", ["true division", "power"])
def test_float_division_and_power_remain_unsupported(op):
    @provable()
    @contract(ensures=[lambda result: result >= 0])
    def true_division(x: int) -> int:
        return x / 2

    @provable()
    @contract(ensures=[lambda result: result >= 0])
    def power(x: int) -> int:
        return x ** 2

    outcome = verify_function({"true division": true_division, "power": power}[op])
    assert outcome.result is ProofResult.SKIPPED


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-072", "Native solver UNKNOWN is not misreported as proof")
def test_native_solver_unknown_is_not_proven(monkeypatch):
    import z3

    make_solver = z3.Solver

    def resource_limited_solver():
        solver = make_solver()
        solver.set(rlimit=1)
        return solver

    monkeypatch.setattr(z3, "Solver", resource_limited_solver)

    @provable()
    @contract(ensures=[lambda result: result >= 0])
    def square(x: int) -> int:
        return x * x

    outcome = verify_function(square)
    assert outcome.result is ProofResult.UNKNOWN
    assert outcome.counter_example is None
    assert "could not determine" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-131", "Exhausting the shared deadline yields UNKNOWN with a reason")
def test_shared_deadline_exhausted_before_domain_check(monkeypatch):
    from types import SimpleNamespace

    from spec_test import prover

    ticks = iter([0.0, 0.0, 1.1, 1.1])
    monkeypatch.setattr(prover, "time", SimpleNamespace(monotonic=lambda: next(ticks)))

    @provable(timeout=1)
    @contract(ensures=[lambda result: result == 0])
    def zero(x: int) -> int:
        return x - x

    outcome = verify_function(zero)
    assert outcome.result is ProofResult.UNKNOWN
    assert outcome.counter_example is None
    assert "timeout" in outcome.message


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 not installed")
@spec("Z3-135", "Changed source cannot certify an already loaded function or predicate")
@pytest.mark.parametrize("stale", ["body", "predicate"])
def test_refuses_stale_live_code(tmp_path, stale):
    import importlib.util
    import linecache

    from spec_test import ContractError

    source = tmp_path / "loaded.py"
    body = (
        "from spec_test import contract, provable\n"
        "@provable()\n"
        "@contract(ensures=[lambda result: result == 1])\n"
        "def choose(x: int) -> int:\n"
        "    return x - x + 0\n"
    )
    source.write_text(body)
    location = importlib.util.spec_from_file_location("source_match_fixture", source)
    module = importlib.util.module_from_spec(location)
    location.loader.exec_module(module)
    assert verify_function(module.choose).result is ProofResult.REFUTED
    if stale == "body":
        body = body.replace("x - x + 0", "x - x + 1")
    else:
        body = body.replace("result == 1", "result == 0")
    source.write_text(body)
    linecache.clearcache()
    outcome = verify_function(module.choose)
    assert outcome.result is ProofResult.SKIPPED
    assert "does not uniquely match the loaded Python code" in outcome.message
    with pytest.raises(ContractError):
        module.choose(0)
