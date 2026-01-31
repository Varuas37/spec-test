---
name: spec-review
description: Review Specifications for Completeness
---

## Overview

This skill guides human reviewers through evaluating specifications for completeness, clarity, and testability. Good specs are the foundation of reliable software.

## When to Use

- Reviewing a pull request that adds or modifies specs
- Before signing off on a feature design
- During sprint planning to validate requirements
- When specs and implementation seem misaligned
- User asks to "review specs" or "validate requirements"

## Review Workflow

### Step 1: Get an Overview

List all specs to understand scope:

```bash
spec-test list-specs
```

### Step 2: Check Verification Status

Run verification to see current state:

```bash
spec-test verify
```

### Step 3: Review Each Spec

For each specification, evaluate against the criteria below.

### Step 4: Document Findings

Create review comments using the feedback template at the end of this document.

## Spec Quality Criteria

### 1. Uniqueness

Each spec ID must be unique across the entire project.

**Check**:
```bash
spec-test list-specs | sort | uniq -d
```

**Bad**:
```markdown
- **AUTH-001**: User can log in
- **AUTH-001**: User can log out  # Duplicate ID!
```

**Good**:
```markdown
- **AUTH-001**: User can log in
- **AUTH-002**: User can log out
```

### 2. Testability

A spec must have clear pass/fail criteria that can be verified programmatically.

**Bad** (vague, subjective):
```markdown
- **UI-001**: The interface should be user-friendly
- **PERF-001**: The system should be fast
```

**Good** (specific, measurable):
```markdown
- **UI-001**: Login form displays email and password fields
- **PERF-001**: API response time is under 200ms for 95th percentile
```

### 3. Atomicity

Each spec should describe one requirement, not multiple bundled together.

**Bad** (multiple requirements):
```markdown
- **AUTH-001**: User can log in, log out, and reset password
```

**Good** (atomic):
```markdown
- **AUTH-001**: User can log in with valid credentials
- **AUTH-002**: User can log out and end session
- **AUTH-003**: User can request password reset email
```

### 4. Completeness

Requirements should cover:
- Happy path (normal operation)
- Error cases (what happens when things go wrong)
- Edge cases (boundary conditions)
- Security considerations

**Incomplete**:
```markdown
- **AUTH-001**: User can log in with valid credentials
```

**Complete**:
```markdown
- **AUTH-001**: User can log in with valid credentials
- **AUTH-002**: Login fails with invalid email
- **AUTH-003**: Login fails with invalid password
- **AUTH-004**: Account locks after 5 failed attempts
- **AUTH-005**: Locked account unlocks after 30 minutes
```

### 5. Traceability

Specs should map to business requirements or user stories.

**Good practice**: Include references in the spec file:
```markdown
## Authentication (User Story: US-42)

### Requirements
- **AUTH-001**: User can log in with valid credentials
```

### 6. Appropriate Verification Type

Use verification types correctly:

| Type | Use For |
|------|---------|
| (none) | Automatable logic and behavior |
| `[manual]` | UI/UX, timing, human judgment |
| `[contract]` | Invariants, type constraints |

**Examples**:
```markdown
- **AUTH-001**: User can log in with valid credentials        # Automated
- **AUTH-002** [manual]: Login page matches design mockup     # Human review
- **AUTH-003** [contract]: Password is never stored in plain text  # Invariant
```

## Common Issues

### Issue: Spec Describes Implementation

**Bad** (implementation details):
```markdown
- **DB-001**: User table has columns: id, email, password_hash
```

**Good** (behavior):
```markdown
- **USER-001**: System stores user email and secure password
```

### Issue: Circular or Self-Referential

**Bad**:
```markdown
- **AUTH-001**: The login feature works correctly
```

**Good**:
```markdown
- **AUTH-001**: User with valid credentials receives access token
```

### Issue: Missing Error Cases

**Incomplete**:
```markdown
## Cart
- **CART-001**: User can add item to cart
```

**Better**:
```markdown
## Cart
- **CART-001**: User can add item to cart
- **CART-002**: Adding out-of-stock item shows error message
- **CART-003**: Adding more than available quantity caps at maximum
- **CART-004**: Cart total cannot exceed $10,000
```

### Issue: Untestable Timing Requirements

**Bad**:
```markdown
- **PERF-001**: System responds quickly
```

**Good**:
```markdown
- **PERF-001** [manual]: P95 response time under 200ms under load
```

## Review Checklist

Use this checklist for each spec file:

### Spec IDs
- [ ] All IDs follow PREFIX-NNN format
- [ ] All IDs are unique
- [ ] PREFIX is consistent within a domain

### Content Quality
- [ ] Each spec is testable (clear pass/fail)
- [ ] Each spec is atomic (one requirement)
- [ ] Language is precise and unambiguous
- [ ] No implementation details in specs

### Coverage
- [ ] Happy paths are covered
- [ ] Error cases are covered
- [ ] Edge cases are identified
- [ ] Security considerations included

### Verification Types
- [ ] Automated specs are actually automatable
- [ ] Manual specs truly require human judgment
- [ ] Contract specs define invariants

### Organization
- [ ] Specs are grouped logically
- [ ] File naming follows {domain}.md pattern in specs/
- [ ] Specs are traceable to user stories/epics

## Feedback Template

Use this template for review comments:

```markdown
## Spec Review: [file name]

### Summary
[Overall assessment: Approved / Changes Requested / Needs Discussion]

### Issues Found

#### [SPEC-ID]: [Brief issue description]
**Problem**: [What is wrong]
**Suggestion**: [How to fix]

### Missing Coverage
- [Scenario not covered]
- [Edge case not handled]

### Questions
- [Clarification needed]

### Positive Notes
- [What was done well]
```

## Commands

```bash
# List all specs for overview
spec-test list-specs

# Check current verification status
spec-test verify

# Check specific spec
spec-test check AUTH-001

# Generate report for review
spec-test verify --output review-report.md
```
