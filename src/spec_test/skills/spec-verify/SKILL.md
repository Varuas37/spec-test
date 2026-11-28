---
name: spec-verify
description: Run Verification and Fix Issues
---

## Overview

This skill guides you through running spec-test verification, interpreting results, and fixing common issues. Verification ensures all specifications have passing tests.

## When to Use

- Before committing code changes
- After implementing new features
- When CI/CD pipeline fails on spec verification
- User asks to "verify specs" or "check coverage"
- Debugging why specs are failing

## Choose the evidence you need

1. Use `spec-test plan` to inspect the native commands. Run
   `spec-test run-checks --trust-repo` only for an authorized checkout.
   A command passing does not satisfy a spec ID by itself.
2. For navigation, generate source indexes with the Rust and TypeScript
   adapters. Use `spec-test trace --specs design/specs --index rust.json
   --index typescript.json --require QUEUE-001` (adjust the ID and inputs).
   Each represented language must provide both roles. This validates links,
   not the results of any runner.
3. Use `spec-test verify --evidence rust-results.json
   --evidence typescript-results.json` with fresh, trusted receipts when
   the project uses native checks. Keep test, property, model proof, and
   implementation proof evidence distinct. Do not turn a skipped, missing
   or stale proof into a pass. A selected optional proof engine emits its
   own receipt; normal Rust builds and trace do not require Kani.

## Workflow

### Step 1: Run Full Verification

```bash
spec-test verify
```

This command:
1. Scans `design/specs/*.md` for specifications
2. Discovers tests with `@spec` decorators in `tests/`
3. Runs matched tests
4. Reports results

### Step 2: Interpret the Output

The output shows each spec with a status:

```
Specification Verification Report
=================================

AUTH-001  PASS   User can log in with valid credentials
AUTH-002  FAIL   Invalid password returns error
AUTH-003  PENDING  Account locks after failed attempts
AUTH-004  SKIP   [manual] Password reset email timing

Coverage: 50% (2/4 automated specs passing)
```

### Status Meanings

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| `PASS` | Test exists and passes | None |
| `FAIL` | Test exists but fails | Fix test or implementation |
| `PENDING` | No test found for spec | Write a test |
| `SKIP` | Manual or explicitly deferred | Check the item's reason |

For manual or AI-assisted requirements, export an offline packet with
`spec-test review-packet --output review.json`. Record the exact revision,
requirement ID, item digest, and the human reviewer's observation and decision
in the PR or review log. Never submit that record as a runner receipt.

### Step 3: Fix Issues

Based on the status, take appropriate action:

#### Fixing FAIL Status

1. Find the failing test:
   ```bash
   spec-test check AUTH-002
   ```

2. Run the test with verbose output:
   ```bash
   pytest tests/test_auth.py::test_invalid_password -v
   ```

3. Debug the failure:
   - Is the test correct but implementation wrong? Fix implementation.
   - Is the implementation correct but test wrong? Fix test.
   - Has the spec changed? Update both test and implementation.

#### Fixing PENDING Status

1. Identify which spec needs a test:
   ```bash
   spec-test list-specs
   ```

2. Write a test with the `@spec` decorator:
   ```python
   @spec("AUTH-003", "Account locks after failed attempts")
   def test_account_lockout():
       # Implementation
       pass
   ```

3. Verify the spec is now tracked:
   ```bash
   spec-test check AUTH-003
   ```

## Common Issues and Solutions

### Issue: Spec Not Found

**Symptom**: `spec-test check ID` returns "Spec not found"

**Causes**:
- Spec file not in `design/specs/` directory
- Spec format incorrect (missing `**ID**:`)

**Solution**:
```bash
# Check file naming
ls design/specs/

# Verify spec format in file
grep -n "**AUTH-001**" design/specs/auth.md
```

### Issue: Test Not Discovered

**Symptom**: Spec shows PENDING but test exists

**Causes**:
- Missing `@spec` decorator
- Wrong spec ID in decorator
- Test file not in `tests/` directory
- Test function does not start with `test_`

**Solution**:
```python
# Ensure decorator is present and ID matches
@spec("AUTH-001", "Description")  # ID must match exactly
def test_something():  # Must start with test_
    pass
```

### Issue: Wrong Test Directory

**Symptom**: Tests pass with pytest but spec-test shows PENDING

**Solution**:
```bash
# Specify correct directories
spec-test verify --specs docs/specs --tests tests
```

### Issue: Exit Code Non-Zero

**Exit code 1**: Tests are failing
```bash
# Find and fix failing tests
spec-test verify
pytest tests/ -v --tb=short
```

**Exit code 2**: Missing tests (when `--fail-on-missing` is enabled)
```bash
# Either write missing tests or allow missing
spec-test verify --no-fail-on-missing
```

## Verification Options

### Verbose Output

See detailed test output:
```bash
spec-test verify --verbose
```

### Custom Directories

Specify non-default locations:
```bash
spec-test verify --specs path/to/specs --tests path/to/tests
```

### Generate Report

Save report to markdown file:
```bash
spec-test verify --output verification-report.md
```

### Allow Missing Tests

Do not fail on PENDING specs:
```bash
spec-test verify --no-fail-on-missing
```

## Single Spec Verification

Check one spec at a time:
```bash
spec-test check AUTH-001
```

Output:
```
PASS AUTH-001: User can log in with valid credentials
  Test: tests/test_auth.py::test_login_success
```

## Commands Reference

```bash
# Full verification
spec-test verify

# Verbose verification
spec-test verify -v

# Check single spec
spec-test check AUTH-001

# List all specs
spec-test list-specs

# Generate markdown report
spec-test verify -o report.md

# Custom directories
spec-test verify -s specs -t tests

# Allow missing tests
spec-test verify --no-fail-on-missing
```

## CI/CD Integration

Add to your CI pipeline:

```yaml
# GitHub Actions example
- name: Verify Specifications
  run: |
    pip install spec-test
    spec-test verify
```

```yaml
# GitLab CI example
verify-specs:
  script:
    - pip install spec-test
    - spec-test verify --output verification-report.md
  artifacts:
    paths:
      - verification-report.md
```

## Checklist

Before committing:

- [ ] `spec-test verify` exits with code 0
- [ ] No FAIL status specs
- [ ] No unexpected PENDING specs
- [ ] Coverage percentage is acceptable
- [ ] All new specs have corresponding tests
