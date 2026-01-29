# spec-workflow: Complete Specification-Driven Development

## Overview

This is the master workflow for specification-driven development. It guides you through the complete process from feature request to verified implementation.

## The Workflow

```
Feature Request
      |
      v
+------------------+
|  1. ISSUE        |  "Why are we doing this?"
|  spec-issue      |  Document intentions, options, decisions
+------------------+
      |
      v
+------------------+
|  2. SPEC         |  "What should it do?"
|  spec-feature    |  Define requirements with IDs
+------------------+
      |
      v
+------------------+
|  3. IMPLEMENT    |  "How does it work?"
|  spec-implement  |  Write code with @contract, @spec tests
+------------------+
      |
      v
+------------------+
|  4. VERIFY       |  "Does it work?"
|  spec-verify     |  Run spec-test verify
+------------------+
      |
      v
+------------------+
|  5. REVIEW       |  "Is it correct?"
|  spec-review     |  Review specs and implementation
+------------------+
```

## When to Use This Workflow

**Always** for non-trivial changes:
- New features
- Significant refactors
- Bug fixes that change behavior
- Performance optimizations

**Skip for** trivial changes:
- Typo fixes
- Comment updates
- Minor formatting

## Step-by-Step Guide

### Step 1: Write an Issue

**Skill**: `spec-issue`

Before any code, document:
- Why this change is needed
- What options were considered
- What decision was made and why

```bash
# Create issue file
design/issues/NNN-feature-name.md
```

**Deliverable**: Approved issue in `design/issues/`

### Step 2: Define Specs

**Skill**: `spec-feature`

Convert the issue into formal requirements:
- Each requirement gets a unique ID (PREFIX-NNN)
- Requirements must be testable
- Link back to the issue

```bash
# Create spec file
design/specs/feature-name.md

# Verify specs are found
spec-test list-specs
```

**Deliverable**: Spec file with requirements linked to issue

### Step 3: Implement with Contracts

**Skill**: `spec-implement`

Write code that satisfies the specs:

1. **Add contracts** for runtime verification:
```python
@contract(
    spec="FEAT-001",
    requires=[...],
    ensures=[...],
)
def feature_function():
    ...
```

2. **Write tests** linked to specs:
```python
@spec("FEAT-001", "Description")
def test_feature():
    ...
```

**Deliverable**: Implementation with contracts and tests

### Step 4: Verify

**Skill**: `spec-verify`

Run verification to ensure all specs pass:

```bash
spec-test verify
```

All specs must be:
- ✅ PASS - Test exists and passes
- Or marked with appropriate tags ([manual], [SKIP])

**Deliverable**: All specs verified

### Step 5: Review

**Skill**: `spec-review`

Final review checklist:
- [ ] Issue documents the "why"
- [ ] Specs are testable and complete
- [ ] Contracts enforce preconditions/postconditions
- [ ] Tests cover all specs
- [ ] `spec-test verify` passes

## Directory Structure

```
design/
  issues/           # Step 1: Why
    001-feature.md
  specs/            # Step 2: What
    feature.md
  prompts/          # AI instructions

src/                # Step 3: How
  feature.py

tests/              # Step 3: Verification
  test_feature.py
```

## Quick Reference

| Step | Skill | Output | Command |
|------|-------|--------|---------|
| 1. Issue | spec-issue | `design/issues/*.md` | - |
| 2. Spec | spec-feature | `design/specs/*.md` | `spec-test list-specs` |
| 3. Implement | spec-implement | `src/`, `tests/` | `pytest` |
| 4. Verify | spec-verify | All specs pass | `spec-test verify` |
| 5. Review | spec-review | Approval | - |

## Common Mistakes

### Skipping Issues
❌ Going straight to specs without documenting why
✅ Always write an issue first, even if brief

### Untestable Specs
❌ "System should be fast"
✅ "API response time < 200ms for 95th percentile"

### Missing Contracts
❌ Writing code without `@contract`
✅ Every public function should have contracts

### Orphan Specs
❌ Specs without tests
✅ Every spec ID has a `@spec` decorated test

## Example: Adding a Feature

```bash
# 1. Write issue
# design/issues/001-user-auth.md

# 2. Define specs
# design/specs/auth.md
# - AUTH-001: User can login
# - AUTH-002: Invalid password fails

# 3. Implement
# src/auth.py with @contract
# tests/test_auth.py with @spec

# 4. Verify
spec-test verify

# 5. Review and commit
git add . && git commit -m "feat: add user authentication"
```

## Integration with Git

Recommended commit flow:

```bash
# After Step 1
git add design/issues/
git commit -m "docs: add issue for [feature]"

# After Step 2
git add design/specs/
git commit -m "docs: add specs for [feature]"

# After Steps 3-4
git add src/ tests/
git commit -m "feat: implement [feature]

Implements:
- SPEC-001: description
- SPEC-002: description

Issue: #NNN"
```
