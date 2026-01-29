# CLAUDE.md - Agent Instructions

## Specification-Driven Development

This project uses `spec-test` for specification-driven development. Every behavior must be backed by a passing test.

## Workflow

1. **Issues** document intentions in `design/issues/`
2. **Specs** define requirements in `design/specs/`
3. **Tests** use `@spec("ID", "description")` decorator
4. **Run** `spec-test verify` to check all specs have passing tests

## Directory Structure

```
design/
  issues/    # Why - intentions, pros/cons, context
  specs/     # What - formal requirements
  prompts/   # How - AI agent instructions
```

## Spec Format

```markdown
- **PREFIX-001**: Description of requirement
```

## Test Format

```python
from spec_test import spec

@spec("PREFIX-001", "Description")
def test_something():
    assert result == expected
```

## Commands

```bash
spec-test verify          # Check all specs have passing tests
spec-test list-specs      # List all specs
spec-test check PREFIX-001  # Check single spec
```

## Architecture

Follow **Functional Core, Imperative Shell** with **Dependency Injection**:

- **Pure functions** for all business logic (testable, provable with Z3)
- **Dependency Injection** for I/O dependencies (testable with mocks)
- **Integration tests** only for verifying real I/O works

```
┌─────────────────────────────────────────┐
│          Imperative Shell               │  ← I/O via DI
│  ┌───────────────────────────────────┐  │
│  │       Functional Core             │  │  ← Pure functions
│  │    (all business logic here)      │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Rules

1. Write an issue before writing specs
2. Every spec must link to an issue
3. Every spec ID must have a corresponding `@spec` test
4. Run `spec-test verify` before committing
5. Prefer pure functions; push side effects to the edges
