# spec-test AI Agent Skills

## Overview

These skills provide instructions for AI agents (like Claude) to effectively use spec-test for specification-driven development. When a user runs `spec-test init`, these skills are copied to the user's `.claude/skills/` directory.

## Available Skills

| Skill | File | Purpose |
|-------|------|---------|
| Workflow | `spec-workflow.md` | Complete spec-driven development workflow |
| Create Issue | `spec-issue.md` | Document intentions before writing specs |
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
Write Issue --> Define Specs --> Implement Code --> Verify --> Review
    |               |                 |               |          |
spec-issue    spec-feature     spec-implement   spec-verify  spec-review
   (why)          (what)            (how)        (check)     (approve)
```

See `spec-workflow.md` for the complete workflow guide.

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
- `**ID** [integration]: Description` - Integration test (real I/O)
- `**ID** [manual]: Description` - Manual verification required
- `**ID** [contract]: Description` - Contract/property verification
- `**ID** [provable]: Description` - Z3 formal proof

## Architecture Principles

All code should follow **Functional Core, Imperative Shell** with **Dependency Injection**:

```
┌─────────────────────────────────────────────────────────────┐
│                    Imperative Shell                         │
│           (thin layer, injected dependencies)               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 Functional Core                        │  │
│  │           (pure functions, all business logic)         │  │
│  │                                                        │  │
│  │   • Deterministic (same input → same output)          │  │
│  │   • No side effects                                    │  │
│  │   • Easy to test (unit tests)                         │  │
│  │   • Can be formally proven (Z3)                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│   • Database, Email, API calls via DI                      │
│   • Testable with mocks                                     │
│   • Integration tests verify real I/O                       │
└─────────────────────────────────────────────────────────────┘
```

### Testing Strategy

```
┌─────────────┬────────────────┬─────────────────────┬───────────┐
│  Test Type  │      What      │         How         │   Speed   │
├─────────────┼────────────────┼─────────────────────┼───────────┤
│ Unit        │ Pure functions │ Direct call         │ Fast (ms) │
├─────────────┼────────────────┼─────────────────────┼───────────┤
│ Mock        │ Service wiring │ Inject mocks via DI │ Fast (ms) │
├─────────────┼────────────────┼─────────────────────┼───────────┤
│ Integration │ Real I/O works │ Real DB/API         │ Slow (s)  │
└─────────────┴────────────────┴─────────────────────┴───────────┘
```

**Aim for ~90% unit/mock tests, ~10% integration tests.**

### Example

```python
# FUNCTIONAL CORE: Pure function, no dependencies
def calculate_total(items: list[Item]) -> Decimal:
    return sum(item.price * item.quantity for item in items)

# IMPERATIVE SHELL: Thin layer with injected dependencies
class OrderService:
    def __init__(self, db: Database, email: EmailSender):  # DI
        self.db = db
        self.email = email

    def place_order(self, items: list[Item]) -> Order:
        total = calculate_total(items)  # Call pure function
        order = Order(items=items, total=total)
        self.db.save(order)             # Injected dependency
        self.email.send_confirmation()  # Injected dependency
        return order

# TESTS
@spec("ORDER-001", "Total is sum of item prices")
def test_calculate_total():  # Unit test - pure function
    items = [Item(price=Decimal("10"), quantity=2)]
    assert calculate_total(items) == Decimal("20")

@spec("ORDER-002", "Order saved to database")
def test_order_saved():  # Mock test - inject mock
    mock_db = MockDatabase()
    service = OrderService(db=mock_db, email=MockEmail())
    service.place_order([Item(...)])
    assert len(mock_db.saved) == 1

@spec("ORDER-003", "Order persists to real database")
@pytest.mark.integration
def test_order_persists():  # Integration test - real I/O
    service = OrderService(db=real_db, email=mock_email)
    order = service.place_order([Item(...)])
    assert real_db.get(order.id) is not None
```

## Commands Reference

```bash
spec-test verify          # Verify all specs have passing tests
spec-test list-specs      # List all specifications
spec-test check ID        # Check a single spec
spec-test init            # Initialize spec-test in a project
spec-test context         # Output CLAUDE.md for LLM context
```
