# ISSUE-003: Hypothesis Property Testing Integration

## Summary
Integrate Hypothesis property-based testing to automatically generate thousands of test cases and find edge cases that manual tests miss.

## Motivation
Manual tests check specific examples, but property tests check properties across many inputs:

```python
# Manual: checks one case
def test_sort():
    assert sort([3, 1, 2]) == [1, 2, 3]

# Property: checks thousands of cases
@given(st.lists(st.integers()))
def test_sort_property(lst):
    result = sort(lst)
    assert len(result) == len(lst)
    assert all(result[i] <= result[i+1] for i in range(len(result)-1))
```

Property tests find edge cases like:
- Empty lists
- Single elements
- Duplicate values
- Integer overflow
- Unicode edge cases

## Detailed Description

### @property_test Decorator
Integrates with @spec for tracking:
```python
@spec("SORT-001", "Sort returns sorted list")
@property_test
@given(st.lists(st.integers()))
def test_sort_property(lst):
    ...
```

### Strategy Generation
Auto-generate strategies from type hints:
```python
def add(a: int, b: int) -> int:  # Generates st.integers() for both
```

### Contract Integration
Contracts are checked during property tests:
```python
@contract(requires=[lambda x: x > 0])
def sqrt(x):
    ...

# Hypothesis will find that negative inputs violate the contract
```

### Configuration
```toml
[tool.spec-test.hypothesis]
max_examples = 1000
deadline = 5000
```

## Options Considered

### Option A: Built-in property testing
**Pros**: No external dependency
**Cons**: Reinventing the wheel, Hypothesis is battle-tested

### Option B: Hypothesis integration (chosen)
**Pros**: Industry standard, powerful shrinking, database
**Cons**: Additional dependency

### Option C: QuickCheck-style custom
**Pros**: Full control
**Cons**: Significant implementation effort

## Decision
**Option B**: Hypothesis is the gold standard for property testing in Python. Integration is better than reimplementation.

## Related Specs
- [hypothesis-integration.md](../specs/hypothesis-integration.md)
  - HYP-001 to HYP-005: Property test decorator
  - HYP-010 to HYP-015: Strategy generation
  - HYP-020 to HYP-024: Contract integration
  - HYP-030 to HYP-034: Shrinking and reporting
  - HYP-040 to HYP-047: Configuration
  - HYP-050 to HYP-055: CLI integration

## Status
- [x] Issue written
- [x] Specs defined
- [ ] Implementation complete
- [ ] Tests passing
