# Feature: Hypothesis Property Testing Integration

Property-based testing using Hypothesis to automatically generate test cases and verify behavior across a wide range of inputs.

## Related Issue
- [ISSUE-003: Hypothesis Property Testing Integration](../issues/003-hypothesis-integration.md)

---

## Property Test Decorator

- **HYP-001**: @property_test decorator integrates with @spec

  **Contracts:**
  - Requires: spec_id is valid spec ID string
  - Ensures: test registered with spec_id for verification

- **HYP-002**: @property_test accepts Hypothesis settings

  **Contracts:**
  - Requires: settings is dict or hypothesis.settings object
  - Ensures: property test runs with specified settings (max_examples, deadline, etc.)

- **HYP-003**: @property_test preserves function metadata

  **Contracts:**
  - Requires: function has __name__, __doc__, __module__
  - Ensures: decorated function preserves all metadata attributes

- **HYP-004**: @property_test works with pytest

  **Contracts:**
  - Requires: pytest is installed
  - Ensures: test discoverable and runnable via pytest

- **HYP-005**: @property_test supports async functions

  **Contracts:**
  - Requires: function is async
  - Ensures: awaitable behavior preserved, hypothesis.given works correctly

---

## Strategy Generation

- **HYP-010**: Auto-generate strategies from type hints

  **Contracts:**
  - Requires: function has type annotations
  - Ensures: hypothesis strategies generated for each annotated parameter

- **HYP-011**: Support standard library types

  **Contracts:**
  - Requires: type hint is int, str, float, bool, bytes, list, dict, set, tuple, Optional, Union
  - Ensures: appropriate hypothesis strategy generated

- **HYP-012**: Support constrained types via Annotated

  **Contracts:**
  - Requires: type hint uses typing.Annotated with constraints
  - Ensures: strategy respects constraints (e.g., Annotated[int, Gt(0)])

- **HYP-013**: Allow explicit strategy override

  **Contracts:**
  - Requires: strategies parameter is dict mapping param names to strategies
  - Ensures: explicit strategies used instead of auto-generated ones

- **HYP-014**: Support custom types via strategy registry

  **Contracts:**
  - Requires: custom type registered with register_strategy()
  - Ensures: registered strategy used for custom type

- **HYP-015**: Fail clearly on unsupported types

  **Contracts:**
  - Requires: type hint has no registered strategy
  - Ensures: raises StrategyGenerationError with helpful message

---

## Contract Integration

- **HYP-020**: Contracts checked during property tests

  **Contracts:**
  - Requires: function has @contract decorator
  - Ensures: preconditions checked before execution, postconditions checked after

- **HYP-021**: Contract failures recorded as property test failures

  **Contracts:**
  - Requires: ContractError raised during property test
  - Ensures: hypothesis records as falsifying example

- **HYP-022**: Contract violations trigger shrinking

  **Contracts:**
  - Requires: contract fails on generated input
  - Ensures: hypothesis shrinks to minimal failing example

- **HYP-023**: Combined @property_test and @contract decorator order

  **Contracts:**
  - Requires: both decorators applied to function
  - Ensures: works correctly regardless of decorator order

- **HYP-024**: Preconditions can filter invalid inputs via assume()

  **Contracts:**
  - Requires: precondition marked as assumption
  - Ensures: failing precondition calls hypothesis.assume(False)

---

## Shrinking and Reporting

- **HYP-030**: Shrink failing cases to minimal examples

  **Contracts:**
  - Requires: property test finds falsifying example
  - Ensures: hypothesis shrinks to smallest reproducible failure

- **HYP-031**: Report failing inputs clearly

  **Contracts:**
  - Requires: property test fails
  - Ensures: output shows exact inputs that caused failure

- **HYP-032**: Store failing examples in database

  **Contracts:**
  - Requires: property test finds falsifying example
  - Ensures: example saved to hypothesis database for replay

- **HYP-033**: Replay stored failing examples first

  **Contracts:**
  - Requires: hypothesis database contains previous failures
  - Ensures: stored examples run before generating new ones

- **HYP-034**: Report number of examples tested

  **Contracts:**
  - Requires: property test completes (pass or fail)
  - Ensures: output shows how many examples were tested

---

## Configuration

- **HYP-040**: Configure via pyproject.toml

  **Contracts:**
  - Requires: [tool.spec-test.hypothesis] section exists
  - Ensures: settings applied to all property tests

- **HYP-041**: Support max_examples setting

  **Contracts:**
  - Requires: max_examples specified in config
  - Ensures: property tests run at most max_examples times

- **HYP-042**: Support deadline setting

  **Contracts:**
  - Requires: deadline specified in config (ms or None)
  - Ensures: individual examples timeout after deadline

- **HYP-043**: Support suppress_health_check setting

  **Contracts:**
  - Requires: suppress_health_check specified in config
  - Ensures: specified health checks suppressed

- **HYP-044**: Support database path setting

  **Contracts:**
  - Requires: database_path specified in config
  - Ensures: hypothesis database stored at specified path

- **HYP-045**: Per-test settings override global config

  **Contracts:**
  - Requires: @property_test has settings parameter
  - Ensures: test-level settings take precedence over global config

- **HYP-046**: Support verbosity setting

  **Contracts:**
  - Requires: verbosity specified in config
  - Ensures: hypothesis output verbosity matches setting

- **HYP-047**: Support derandomize setting for CI

  **Contracts:**
  - Requires: derandomize=true in config
  - Ensures: tests run deterministically with fixed seed

---

## CLI Integration

- **HYP-050**: `spec-test verify` includes property tests

  **Contracts:**
  - Requires: property tests exist with @property_test
  - Ensures: property tests run as part of verification

- **HYP-051**: `spec-test verify --properties` runs only property tests

  **Contracts:**
  - Requires: --properties flag provided
  - Ensures: only @property_test decorated tests run

- **HYP-052**: `spec-test verify --no-properties` skips property tests

  **Contracts:**
  - Requires: --no-properties flag provided
  - Ensures: @property_test tests excluded from run

- **HYP-053**: `spec-test verify --max-examples N` overrides config

  **Contracts:**
  - Requires: --max-examples flag with integer value
  - Ensures: all property tests use specified max_examples

- **HYP-054**: Exit code reflects property test results

  **Contracts:**
  - Requires: property tests complete
  - Ensures: exit code 1 if any property test fails

- **HYP-055**: `spec-test list-specs` shows property test indicators

  **Contracts:**
  - Requires: spec has associated property test
  - Ensures: spec listing shows [property] indicator

---

## Reporting and Coverage

- **HYP-060**: Report property test statistics per spec

  **Contracts:**
  - Requires: property test completes
  - Ensures: report shows examples_run, pass/fail, shrink_count

- **HYP-061**: Include property coverage in overall coverage

  **Contracts:**
  - Requires: spec has property test
  - Ensures: coverage calculation includes property test status

- **HYP-062**: Report contract violations found by property tests

  **Contracts:**
  - Requires: property test finds contract violation
  - Ensures: report distinguishes contract failure from assertion failure

- **HYP-063**: Generate property test summary in markdown report

  **Contracts:**
  - Requires: markdown report requested
  - Ensures: report includes property test section with statistics

- **HYP-064**: Report unique failure modes discovered

  **Contracts:**
  - Requires: multiple failing examples found
  - Ensures: report groups failures by exception type/message

---

## Error Handling

- **HYP-070**: Handle hypothesis not installed gracefully

  **Contracts:**
  - Requires: hypothesis package not installed
  - Ensures: clear error message suggesting `pip install hypothesis`

- **HYP-071**: Handle invalid strategy configuration

  **Contracts:**
  - Requires: strategy configuration is invalid
  - Ensures: raises ConfigurationError with details

- **HYP-072**: Handle timeout during shrinking

  **Contracts:**
  - Requires: shrinking exceeds reasonable time
  - Ensures: returns best shrunk example found so far

- **HYP-073**: Handle flaky tests detection

  **Contracts:**
  - Requires: test passes/fails inconsistently on same input
  - Ensures: warns about flaky behavior, suggests fixes

---

## Example Usage

```python
from spec_test import spec, property_test, contract
from typing import Annotated
from hypothesis import assume

# Basic property test linked to spec
@property_test("HYP-001")
def test_string_concat_length(a: str, b: str):
    result = a + b
    assert len(result) == len(a) + len(b)

# With explicit strategies
@property_test("HYP-013", strategies={
    "x": st.integers(min_value=0, max_value=100)
})
def test_bounded_integer(x: int):
    assert 0 <= x <= 100

# Combined with contract
@contract(
    spec="MATH-001",
    requires=[lambda x: x >= 0],
    ensures=[lambda result: result >= 0]
)
def sqrt(x: float) -> float:
    return x ** 0.5

@property_test("MATH-001")
def test_sqrt_contract(x: Annotated[float, Ge(0)]):
    result = sqrt(x)
    assert result * result == pytest.approx(x)

# Using assume for filtering
@property_test("DIV-001")
def test_division(a: int, b: int):
    assume(b != 0)  # Filter out division by zero
    result = a / b
    assert result * b == pytest.approx(a)
```

## Configuration Example

```toml
[tool.spec-test.hypothesis]
max_examples = 100
deadline = 500  # ms
database_path = ".hypothesis"
derandomize = false
verbosity = "normal"  # quiet, normal, verbose, debug
suppress_health_check = ["too_slow"]
```
