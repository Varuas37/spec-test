# AI Agent Workflow for spec-test

This document describes how AI agents should work on issues in this repository.

## Trigger

Issues labeled `ai-agent` are candidates for automated AI agent work.

## Workflow Steps

### 1. Fetch the Issue

```bash
gh issue view <issue-number>
```

Or list available issues:

```bash
gh issue list --label ai-agent
```

### 2. Understand the Problem

- Read the issue description carefully
- Identify what behavior is broken or missing
- Check if there's a related spec in `docs/specs/*.md`

### 3. Reproduce the Issue (if applicable)

Before fixing, confirm the issue exists:

```bash
# Build and install the package
uv build
uv venv --seed
.venv/bin/pip install dist/*.whl

# Run tests to see current state
.venv/bin/pytest

# Run spec verification
.venv/bin/spec-test verify
```

### 4. Add or Update Specs

If the fix requires new behavior:

1. Add a spec to the appropriate file in `docs/specs/*.md`:
   ```markdown
   - **PREFIX-NNN**: Description of the requirement
   ```

2. Use meaningful prefixes:
   - `DEC-` for decorator functionality
   - `CLI-` for CLI commands
   - `RUN-` for runner/discovery logic
   - `PARSE-` for spec parsing

### 5. Write Tests First

Create or update tests in `tests/`:

```python
from spec_test import spec

@spec("PREFIX-NNN", "Description matching the spec")
def test_the_new_behavior():
    # Implement the test
    assert actual == expected
```

For async tests:

```python
import pytest
from spec_test import spec

@spec("PREFIX-NNN", "Async behavior description")
@pytest.mark.asyncio
async def test_async_behavior():
    result = await some_async_function()
    assert result == expected
```

For class-based tests:

```python
from spec_test import spec

class TestFeature:
    @spec("PREFIX-NNN", "Class method test description")
    def test_feature_behavior(self):
        assert True
```

### 6. Implement the Fix

- Make minimal changes to fix the issue
- Follow existing code patterns
- Don't over-engineer or add unnecessary features

Key source files:
- `src/spec_test/decorators.py` - @spec and @specs decorators
- `src/spec_test/runner.py` - Test discovery and execution
- `src/spec_test/parser.py` - Spec file parsing
- `src/spec_test/cli.py` - CLI commands

### 7. Verify the Fix

```bash
# Rebuild
uv build

# Reinstall
.venv/bin/pip install dist/*.whl --force-reinstall

# Run all tests
.venv/bin/pytest

# Verify all specs have passing tests
.venv/bin/spec-test verify
```

All specs must show 100% coverage before committing.

### 8. Commit the Changes

Write a clear commit message:

```bash
git add -A
git commit -m "fix: brief description of the fix

- What was broken
- How it was fixed
- Related specs added/updated

Fixes #<issue-number>"
```

### 9. Comment on the Issue

Add a comment explaining:
- Root cause of the issue
- What changes were made
- Which files were modified
- New specs/tests added

```bash
gh issue comment <issue-number> --body "..."
```

### 10. Close the Issue

```bash
gh issue close <issue-number>
```

## Important Rules

1. **Never skip testing** - Always run tests before committing
2. **Don't bump version unnecessarily** - Only bump for releases
3. **Spec-first development** - Add specs before or with your fix
4. **100% spec coverage required** - `spec-test verify` must pass
5. **Minimal changes** - Fix the issue, don't refactor unrelated code

## Python Version Notes

This project requires Python 3.11+ due to type syntax (`str | Path`).

Use `uv` to manage Python versions:

```bash
uv venv --python 3.13 --seed
```

## Common Issues

### Module not found after install

Reinstall from wheel:
```bash
.venv/bin/pip install dist/*.whl --force-reinstall
```

### Tests pass but spec-test verify fails

Check that:
- Your test has `@spec("ID", "description")` decorator
- The spec ID exists in `docs/specs/*.md`
- The test function name starts with `test_`

### Async tests not discovered

Ensure both:
- `@pytest.mark.asyncio` decorator is present
- `@spec()` decorator is present
- Function is defined with `async def`
