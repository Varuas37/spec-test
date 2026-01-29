# ISSUE-002: Runtime Contract Enforcement

## Summary
Add runtime contract checking with preconditions, postconditions, and invariants to catch violations during execution.

## Motivation
Tests verify behavior at test time, but contracts verify behavior at runtime. This catches:
- Invalid inputs that tests didn't cover
- Postcondition violations from implementation bugs
- Invariant violations during function execution

Contracts complement tests by providing continuous verification.

## Detailed Description

### @contract Decorator
```python
@contract(
    spec="AUTH-001",
    requires=[lambda email, pw: "@" in email],
    ensures=[lambda result: result is not None],
    invariants=[lambda email, pw: len(pw) >= 8],
)
def login(email, password):
    ...
```

### Preconditions (requires)
- Checked before function execution
- Receive function arguments
- Raise ContractError on failure

### Postconditions (ensures)
- Checked after function execution
- Receive function result
- Can access `old` values for comparison

### Invariants
- Checked before AND after execution
- Must hold throughout function lifetime

### Old State Capture
```python
@contract(
    capture_old=True,
    ensures=[lambda result, old: len(result) == len(old.items) + 1],
)
def append(items, item):
    return items + [item]
```

## Options Considered

### Option A: String-based contracts
```python
requires=["email.contains('@')"]
```
**Pros**: More readable
**Cons**: Requires expression parser, not type-safe

### Option B: Lambda-based contracts (chosen)
```python
requires=[lambda email: "@" in email]
```
**Pros**: Real Python, type-safe, IDE support
**Cons**: Less readable for complex conditions

### Option C: Annotation-based
```python
def login(email: Requires["@" in email], ...):
```
**Pros**: Inline with parameters
**Cons**: Non-standard, hard to parse

## Decision
**Option B**: Lambda-based. Real Python code is better than a DSL - it's debuggable, type-checkable, and doesn't require a parser.

## Related Specs
- [contracts.md](../specs/contracts.md)
  - CONTRACT-001 to CONTRACT-007: Contract decorator
  - CONTRACT-010 to CONTRACT-014: Contract validation
  - CONTRACT-020 to CONTRACT-021: Contract discovery

## Status
- [x] Issue written
- [x] Specs defined
- [x] Implementation complete
- [x] Tests passing
