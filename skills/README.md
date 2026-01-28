# spec-test AI Agent Skills

## Overview

These skills provide instructions for AI agents (like Claude) to effectively use spec-test for specification-driven development. When a user runs `spec-test init`, these skills are copied to the user's `.claude/skills/` directory.

## Available Skills

| Skill | File | Purpose |
|-------|------|---------|
| Create Feature | `spec-feature.md` | Define features and write formal specifications |
| Implement Specs | `spec-implement.md` | Write code that matches specifications |
| Verify Specs | `spec-verify.md` | Run verification and fix issues |
| Review Specs | `spec-review.md` | Review specifications for completeness |

## Installation

Skills are automatically installed when you run:

```bash
spec-test init
```

This copies skills to `.claude/skills/` in your project directory.

### Manual Installation

To manually install skills, copy the contents of this directory to your project:

```bash
mkdir -p .claude/skills
cp -r /path/to/spec-test/skills/*.md .claude/skills/
```

## Quick Start

1. **Starting a new feature**: Use `spec-feature` to define requirements first
2. **Writing code**: Use `spec-implement` to write tests and implementation
3. **Checking your work**: Use `spec-verify` to ensure all specs pass
4. **Code review**: Use `spec-review` to validate spec completeness

## Workflow Summary

```
Define Feature --> Write Specs --> Implement Code --> Verify --> Review
     |               |                 |               |          |
spec-feature   spec-feature    spec-implement    spec-verify  spec-review
```

## Key Concepts

### Specification IDs

Every requirement has a unique ID following the pattern `PREFIX-NNN`:

- `AUTH-001` - Authentication requirement 1
- `CART-003` - Shopping cart requirement 3
- `API-012` - API requirement 12

### The `@spec` Decorator

Tests are linked to specs using the `@spec` decorator:

```python
from spec_test import spec

@spec("AUTH-001", "User can log in with valid credentials")
def test_login_success():
    result = login("user@example.com", "password123")
    assert result.success
```

### Verification Types

Specs can have verification types in brackets:

- `**ID**: Description` - Automated test (default)
- `**ID** [manual]: Description` - Manual verification required
- `**ID** [contract]: Description` - Contract/property verification

## Commands Reference

```bash
spec-test verify          # Verify all specs have passing tests
spec-test list-specs      # List all specifications
spec-test check ID        # Check a single spec
spec-test init            # Initialize spec-test in a project
spec-test context         # Output CLAUDE.md for LLM context
```
