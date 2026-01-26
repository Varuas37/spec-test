# spec-test

Specification-driven development tool that verifies your specs have passing tests.

## Philosophy

**Every claim about system behavior must be backed by a passing test.**

- If there's no test, the behavior is unverified
- Specs are written first, then implementation, then tests
- `spec-test verify` is the source of truth for project health

## Installation

```bash
pip install spec-test
# or with uv
uv add spec-test
```

## Quick Start

1. Create a spec file anywhere in your project (must be `spec-*.md`):

```markdown
# docs/specs/spec-auth.md

## Requirements
- **AUTH-001**: User can login with email and password
- **AUTH-002**: Invalid credentials return 401 error
```

2. Write tests with the `@spec` decorator:

```python
from spec_test import spec

@spec("AUTH-001", "User can login with email and password")
def test_user_login():
    response = client.post("/login", json={"email": "test@example.com", "password": "secret"})
    assert response.status_code == 200

@spec("AUTH-002", "Invalid credentials return 401 error")
def test_invalid_login():
    response = client.post("/login", json={"email": "test@example.com", "password": "wrong"})
    assert response.status_code == 401
```

3. Verify all specs have passing tests:

```bash
spec-test verify
```

## Commands

```bash
spec-test verify          # Verify all specs have passing tests
spec-test list-specs      # List all specs found
spec-test check AUTH-001  # Check a single spec
spec-test init            # Initialize spec-test in a project
```

## Spec File Format

Spec files must:
- Be named `spec-*.md` (e.g., `spec-auth.md`, `spec-api.md`)
- Can be anywhere in the project (nested directories supported)
- Use `**ID**: description` format for requirements

```markdown
- **AUTH-001**: User can login with email and password
- **AUTH-002** [manual]: Requires manual verification
```

## License

MIT
