# ISSUE-004: Z3 Formal Proof Verification

## Summary
Integrate Z3 SMT solver to provide mathematical proofs that code satisfies its contracts, eliminating entire classes of bugs with certainty.

## Motivation
Tests and property tests check examples, but proofs verify ALL possible inputs:

| Approach | Coverage | Certainty |
|----------|----------|-----------|
| Unit tests | Specific examples | Low |
| Property tests | Thousands of random examples | Medium |
| Formal proofs | ALL possible inputs | 100% |

For critical code (financial, security, safety), "probably correct" isn't enough. We need mathematical certainty.

Example:
```python
@provable
@contract(
    requires=[lambda x: x >= 0],
    ensures=[lambda result: result >= 0],
)
def sqrt(x: float) -> float:
    ...

# Z3 proves: for ALL x >= 0, result >= 0
# No test can check infinite inputs, but Z3 can prove it
```

## Detailed Description

### @provable Decorator
Marks functions for formal verification:
```python
@provable(timeout=30)
@contract(requires=[...], ensures=[...])
def critical_function():
    ...
```

### Contract Translation
Translates Python contracts to Z3 constraints:
- `lambda x: x > 0` → `x > 0` (Z3 expression)
- `lambda result: result >= 0` → `result >= 0`

### Supported Patterns
- Numeric bounds checking
- Array index bounds
- None/null safety
- Arithmetic overflow

### Counter-examples
When proofs fail, Z3 provides concrete counter-examples:
```
REFUTED: sqrt postcondition
Counter-example: x = -1
```

### Proof Caching
Cache proofs to avoid re-verification:
- Hash function + contracts
- Invalidate on changes

## Options Considered

### Option A: Custom symbolic execution
**Pros**: Full control
**Cons**: Extremely complex, years of work

### Option B: Z3 integration (chosen)
**Pros**: Industry-leading solver, well-maintained
**Cons**: Learning curve, limited Python subset

### Option C: Dafny/F* transpilation
**Pros**: Purpose-built for verification
**Cons**: Different language, complex toolchain

## Decision
**Option B**: Z3 is the most practical path. It's used by Microsoft, Amazon, and others for real verification. We'll support a useful Python subset rather than trying to verify arbitrary code.

## Limitations (Important!)
Z3 cannot verify:
- Dynamic typing
- I/O operations
- Complex object mutations
- Arbitrary recursion
- External API calls

We'll focus on pure functions with numeric/boolean operations.

## Related Specs
- [z3-proofs.md](../specs/z3-proofs.md)
  - Z3-001 to Z3-005: Provable decorator
  - Z3-010 to Z3-025: Contract translation
  - Z3-030 to Z3-064: Verification patterns
  - Z3-070 to Z3-094: Proof results and caching
  - Z3-100 to Z3-107: CLI integration

## Status
- [x] Issue written
- [x] Specs defined
- [ ] Implementation complete
- [ ] Tests passing
