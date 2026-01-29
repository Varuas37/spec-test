# ISSUE-001: Core Spec-Test Functionality

## Summary
Implement the core spec-test framework that links specifications to tests, enabling specification-driven development.

## Motivation
AI writes code faster than humans can review it. Traditional code review is now the bottleneck. By shifting review from code to specs, we can:
- Review 50 lines of specs instead of 500 lines of code
- Have mathematical certainty that code meets requirements
- Enable AI to generate trustworthy code

Without this:
- AI-generated code remains unverifiable
- Human reviewers become the bottleneck
- No formal link between requirements and implementation

## Detailed Description

### @spec Decorator
Links test functions to specification IDs:
```python
@spec("AUTH-001", "User can login")
def test_user_login():
    ...
```

### Spec Collection
Parses markdown files for spec definitions:
```markdown
- **AUTH-001**: User can login with email/password
```

### Verification
Runs tests and reports which specs pass/fail/missing.

### CLI Commands
- `spec-test verify` - Full verification
- `spec-test list-specs` - List all specs
- `spec-test check ID` - Check single spec

## Options Considered

### Option A: Docstring-based specs
**Pros**: No decorator needed
**Cons**: Harder to parse, less explicit

### Option B: Decorator-based specs (chosen)
**Pros**: Explicit, type-safe, IDE support
**Cons**: Requires importing decorator

### Option C: External mapping file
**Pros**: Separation of concerns
**Cons**: Easy to get out of sync

## Decision
**Option B**: Decorator-based approach. Explicit is better than implicit, and decorators are idiomatic Python.

## Related Specs
- [spec-spec-test.md](../specs/spec-spec-test.md)
  - DEC-*: Decorator requirements
  - COL-*: Collector requirements
  - RUN-*: Runner requirements
  - VER-*: Verifier requirements
  - CLI-*: CLI requirements
  - REP-*: Reporter requirements

## Status
- [x] Issue written
- [x] Specs defined
- [x] Implementation complete
- [x] Tests passing
