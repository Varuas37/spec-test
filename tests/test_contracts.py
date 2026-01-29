"""Tests for the contract decorator."""

import pytest

from spec_test import spec, contract, ContractError, get_contract_registry, Old
from spec_test.contracts import clear_contract_registry


@spec("CONTRACT-001", "@contract decorator validates preconditions")
def test_contract_validates_preconditions():
    """Test that @contract checks requires conditions before function runs."""
    clear_contract_registry()

    @contract(
        requires=[lambda x: x > 0],
    )
    def positive_only(x: int) -> int:
        return x * 2

    # Should work with positive
    assert positive_only(5) == 10

    # Should fail with negative
    with pytest.raises(ContractError) as exc_info:
        positive_only(-1)

    assert "Precondition 0 failed" in str(exc_info.value)


@spec("CONTRACT-002", "@contract decorator validates postconditions")
def test_contract_validates_postconditions():
    """Test that @contract checks ensures conditions after function runs."""
    clear_contract_registry()

    @contract(
        ensures=[lambda result: result > 0],
    )
    def must_return_positive(x: int) -> int:
        return x  # Just returns input

    # Should work when returning positive
    assert must_return_positive(5) == 5

    # Should fail when returning negative
    with pytest.raises(ContractError) as exc_info:
        must_return_positive(-1)

    assert "Postcondition 0 failed" in str(exc_info.value)


@spec("CONTRACT-003", "@contract links to spec ID")
def test_contract_links_to_spec_id():
    """Test that @contract with spec= registers in registry."""
    clear_contract_registry()

    @contract(
        spec="TEST-LINK-001",
        requires=[lambda x: x > 0],
    )
    def linked_function(x: int) -> int:
        return x

    registry = get_contract_registry()
    assert "TEST-LINK-001" in registry
    assert registry["TEST-LINK-001"].func_name == "linked_function"


@spec("CONTRACT-004", "@contract preserves function behavior")
def test_contract_preserves_function_behavior():
    """Test that decorated function behaves normally when contracts pass."""
    clear_contract_registry()

    @contract(
        requires=[lambda a, b: a >= 0 and b >= 0],
        ensures=[lambda result: result >= 0],
    )
    def add(a: int, b: int) -> int:
        return a + b

    # Normal behavior preserved
    assert add(2, 3) == 5
    assert add(0, 0) == 0
    assert add(100, 200) == 300


@spec("CONTRACT-005", "@contract works with async functions")
@pytest.mark.asyncio
async def test_contract_works_with_async():
    """Test that @contract supports async functions."""
    clear_contract_registry()

    @contract(
        requires=[lambda x: x > 0],
        ensures=[lambda result: result > 0],
    )
    async def async_double(x: int) -> int:
        return x * 2

    # Should work
    result = await async_double(5)
    assert result == 10

    # Should fail precondition
    with pytest.raises(ContractError):
        await async_double(-1)


@spec("CONTRACT-010", "Callable preconditions receive function arguments")
def test_preconditions_receive_args():
    """Test that precondition lambdas receive all function arguments."""
    clear_contract_registry()
    received_args = []

    def capture_args(a, b, c):
        received_args.append((a, b, c))
        return True

    @contract(requires=[capture_args])
    def func_with_args(a: int, b: str, c: bool) -> str:
        return f"{a}-{b}-{c}"

    func_with_args(1, "hello", True)

    assert len(received_args) == 1
    assert received_args[0] == (1, "hello", True)


@spec("CONTRACT-011", "Callable postconditions receive result")
def test_postconditions_receive_result():
    """Test that postcondition lambdas receive the function result."""
    clear_contract_registry()
    received_results = []

    def capture_result(result):
        received_results.append(result)
        return True

    @contract(ensures=[capture_result])
    def return_value() -> dict:
        return {"key": "value"}

    return_value()

    assert len(received_results) == 1
    assert received_results[0] == {"key": "value"}


def test_contract_multiple_preconditions():
    """Test multiple preconditions are all checked."""
    clear_contract_registry()

    @contract(
        requires=[
            lambda x, y: x > 0,
            lambda x, y: y > 0,
            lambda x, y: x != y,
        ],
    )
    def both_positive_different(x: int, y: int) -> int:
        return x + y

    # All pass
    assert both_positive_different(1, 2) == 3

    # First fails
    with pytest.raises(ContractError) as exc_info:
        both_positive_different(-1, 2)
    assert "Precondition 0 failed" in str(exc_info.value)

    # Second fails
    with pytest.raises(ContractError) as exc_info:
        both_positive_different(1, -2)
    assert "Precondition 1 failed" in str(exc_info.value)

    # Third fails (same values)
    with pytest.raises(ContractError) as exc_info:
        both_positive_different(2, 2)
    assert "Precondition 2 failed" in str(exc_info.value)


def test_contract_preserves_metadata():
    """Test that contract decorator preserves function metadata."""
    clear_contract_registry()

    @contract()
    def documented_func(x: int) -> int:
        """This is the docstring."""
        return x

    assert documented_func.__name__ == "documented_func"
    assert documented_func.__doc__ == "This is the docstring."


@spec("CONTRACT-020", "Discover contracts by spec ID")
def test_discover_contracts_by_spec_id():
    """Test that contracts are discoverable by their linked spec ID."""
    from spec_test import get_contract_for_spec

    clear_contract_registry()

    @contract(
        spec="DISCOVER-001",
        requires=[lambda x: x > 0],
    )
    def discoverable_func(x: int) -> int:
        return x

    # Should be discoverable by spec ID
    contract_info = get_contract_for_spec("DISCOVER-001")
    assert contract_info is not None
    assert contract_info.spec_id == "DISCOVER-001"
    assert contract_info.func_name == "discoverable_func"
    assert len(contract_info.requires) == 1

    # Non-existent spec should return None
    assert get_contract_for_spec("NONEXISTENT-001") is None


@spec("CONTRACT-021", "Report contract coverage in verify")
def test_report_contract_coverage():
    """Test that verifier reports contract information for specs."""
    import tempfile
    from pathlib import Path

    from spec_test import SpecVerifier

    clear_contract_registry()

    # Create a contract linked to a spec
    @contract(
        spec="HASCON-001",
        requires=[lambda x: x > 0],
    )
    def contracted_func(x: int) -> int:
        return x

    # Create a temporary spec file
    with tempfile.TemporaryDirectory() as tmpdir:
        spec_file = Path(tmpdir) / "test.md"
        spec_file.write_text(
            "# Test Spec\n"
            "- **HASCON-001**: Spec with contract\n"
            "- **NOCON-001**: Spec without contract\n"
        )

        verifier = SpecVerifier(specs_dir=tmpdir, tests_dir="tests")
        report = verifier.verify()

        # Find the results for our specs
        has_contract = next(
            (r for r in report.results if r.spec.id == "HASCON-001"), None
        )
        no_contract = next(
            (r for r in report.results if r.spec.id == "NOCON-001"), None
        )

        assert has_contract is not None
        assert no_contract is not None

        # Verify contract info is available via registry
        from spec_test import get_contract_for_spec

        assert get_contract_for_spec("HASCON-001") is not None
        assert get_contract_for_spec("NOCON-001") is None


@spec("CONTRACT-006", "@contract validates invariants before and after execution")
def test_contract_validates_invariants():
    """Test that @contract checks invariants before AND after function runs."""
    clear_contract_registry()
    invariant_calls = []

    def track_invariant(items, item):
        invariant_calls.append(len(items))
        return len(items) <= 10  # Max 10 items

    @contract(
        invariants=[track_invariant],
    )
    def add_item(items: list, item) -> list:
        items.append(item)
        return items

    # Should work when invariant holds before and after
    result = add_item([1, 2, 3], 4)
    assert result == [1, 2, 3, 4]
    assert len(invariant_calls) == 2  # Called before and after

    # Should fail when invariant fails AFTER (list becomes too long)
    invariant_calls.clear()
    with pytest.raises(ContractError) as exc_info:
        add_item(list(range(10)), 11)  # Would make 11 items

    assert "Invariant 0 failed after execution" in str(exc_info.value)


@spec("CONTRACT-007", "@contract supports old() for capturing pre-state")
def test_contract_captures_old_values():
    """Test that capture_old=True provides old values in postconditions."""
    clear_contract_registry()

    @contract(
        capture_old=True,
        ensures=[lambda result, old: len(result) == len(old.items) + 1],
    )
    def append_item(items: list, item) -> list:
        return items + [item]

    # Should work - length increased by 1
    result = append_item([1, 2, 3], 4)
    assert result == [1, 2, 3, 4]

    # Test that old captures the ORIGINAL value (not mutated)
    @contract(
        capture_old=True,
        ensures=[lambda result, old: result == old.x + 10],
    )
    def add_ten(x: int) -> int:
        return x + 10

    assert add_ten(5) == 15


@spec("CONTRACT-013", "Callable invariants receive function arguments")
def test_invariants_receive_args():
    """Test that invariant lambdas receive all function arguments."""
    clear_contract_registry()
    received_args = []

    def capture_args(a, b):
        received_args.append((a, b))
        return True

    @contract(invariants=[capture_args])
    def func_with_args(a: int, b: str) -> str:
        return f"{a}-{b}"

    func_with_args(42, "hello")

    # Called twice (before and after)
    assert len(received_args) == 2
    assert received_args[0] == (42, "hello")
    assert received_args[1] == (42, "hello")


@spec("CONTRACT-014", "Old object provides access to captured argument values")
def test_old_object_access():
    """Test that Old object provides attribute access to captured values."""
    clear_contract_registry()

    @contract(
        capture_old=True,
        ensures=[
            lambda result, old: old.a == 1,
            lambda result, old: old.b == "test",
            lambda result, old: old.c == [1, 2, 3],
        ],
    )
    def multi_arg_func(a: int, b: str, c: list) -> str:
        return f"{a}-{b}-{len(c)}"

    result = multi_arg_func(1, "test", [1, 2, 3])
    assert result == "1-test-3"


def test_old_object_deep_copies():
    """Test that Old captures deep copies to detect mutations."""
    clear_contract_registry()

    @contract(
        capture_old=True,
        ensures=[lambda result, old: old.items == [1, 2, 3]],  # Original value
    )
    def mutate_list(items: list) -> list:
        items.append(999)  # Mutates the list
        return items

    # old.items should still be [1, 2, 3] even though we mutated it
    result = mutate_list([1, 2, 3])
    assert result == [1, 2, 3, 999]


@pytest.mark.asyncio
async def test_invariants_work_with_async():
    """Test that invariants work with async functions."""
    clear_contract_registry()

    @contract(
        invariants=[lambda x: x > 0],
        ensures=[lambda result: result > 0],
    )
    async def async_with_invariant(x: int) -> int:
        return x * 2

    result = await async_with_invariant(5)
    assert result == 10

    with pytest.raises(ContractError) as exc_info:
        await async_with_invariant(-1)
    assert "Invariant 0 failed before execution" in str(exc_info.value)


@pytest.mark.asyncio
async def test_old_works_with_async():
    """Test that capture_old works with async functions."""
    clear_contract_registry()

    @contract(
        capture_old=True,
        ensures=[lambda result, old: result == old.x * 2],
    )
    async def async_double(x: int) -> int:
        return x * 2

    result = await async_double(7)
    assert result == 14
