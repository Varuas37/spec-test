---
name: spec-workflow
description: Complete Specification-Driven Development
---

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

Write code that satisfies the specs using **Functional Core, Imperative Shell**:

1. **Structure code as pure functions** (functional core):
```python
# Pure function - no side effects, easy to test and prove
def calculate_total(items: list[Item]) -> Decimal:
    return sum(item.price * item.quantity for item in items)
```

2. **Add contracts** for runtime verification:
```python
@contract(
    spec="FEAT-001",
    requires=[lambda items: len(items) > 0],
    ensures=[lambda result: result >= 0],
)
def calculate_total(items: list[Item]) -> Decimal:
    return sum(item.price * item.quantity for item in items)
```

3. **Push side effects to the edges** (imperative shell) with **Dependency Injection**:
```python
class OrderService:
    def __init__(self, db: Database, email: EmailSender):  # DI
        self.db = db
        self.email = email

    def create_order(self, item_ids: list[str]) -> Order:
        items = self.db.get_items(item_ids)  # Injected dependency
        total = calculate_total(items)        # Pure function
        order = Order(items=items, total=total)
        self.db.save(order)                   # Injected dependency
        return order
```

4. **Write tests** linked to specs:
```python
# Unit test for pure function (no mocks needed)
@spec("FEAT-001", "Total is sum of item prices")
def test_calculate_total():
    items = [Item(price=Decimal("10"), quantity=2)]
    assert calculate_total(items) == Decimal("20")

# Mock test for service wiring (inject mocks via DI)
@spec("FEAT-002", "Order calls database save")
def test_order_saves():
    mock_db = MockDatabase()
    service = OrderService(db=mock_db, email=MockEmailSender())
    service.create_order(["item-1"])
    assert len(mock_db.saved) == 1

# Integration test for real I/O (fewer of these)
@spec("FEAT-003", "Order persists to database")
@pytest.mark.integration
def test_order_persists():
    service = OrderService(db=real_db, email=real_email)
    order = service.create_order(["item-1"])
    assert real_db.get(order.id) is not None
```

**Deliverable**: Implementation with pure core, thin shell, contracts, and tests

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

### Mixing Pure Logic with Side Effects
❌ Business logic interleaved with database calls
```python
def process_order(order_id):
    order = db.get(order_id)       # I/O
    order.total = sum(...)          # Logic
    db.save(order)                  # I/O
    email.send(order.user)          # I/O
```
✅ Pure functions for logic, side effects at edges
```python
def calculate_total(items) -> Decimal:      # Pure
    return sum(i.price * i.qty for i in items)

class OrderService:                          # Shell
    def process_order(self, order_id):
        order = self.db.get(order_id)
        order.total = calculate_total(order.items)
        self.db.save(order)
        self.email.send(order.user)
```

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
