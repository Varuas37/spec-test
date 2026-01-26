# CLAUDE.md - Agent Instructions

## Specification-Driven Development

This project uses `spec-test` for specification-driven development. Every behavior must be backed by a passing test.

## Workflow

1. **Specs live in** `docs/specs/*.md`
2. **Tests use** `@spec("ID", "description")` decorator to link to specs
3. **Run** `spec-test verify` to check all specs have passing tests

## Spec Format

In markdown files, specs are defined as:
```
- **PREFIX-001**: Description of requirement
```

## Test Format

```python
from spec_test import spec

@spec("PREFIX-001", "Description")
def test_something():
    # Test implementation
    assert result == expected
```

## Commands

```bash
spec-test verify          # Check all specs have passing tests
spec-test list-specs      # List all specs
spec-test check PREFIX-001  # Check single spec
```

## Rules

1. Never claim a feature works without a test
2. Every spec ID in docs/specs must have a corresponding `@spec` test
3. Run `spec-test verify` before committing - it must pass
4. If a spec has no test, write the test first
