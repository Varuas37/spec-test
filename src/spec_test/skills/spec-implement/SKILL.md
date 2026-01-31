---
name: spec-implement
description: Implement Code Matching Specs
---

## Overview

This skill guides you through implementing features that satisfy specifications. The approach emphasizes writing tests first, then implementation, following test-driven development principles.

## When to Use

- Specs exist but tests are missing (shown as PENDING in verification)
- User asks to "implement" or "build" a specified feature
- User asks to write tests for existing specs
- Verification shows missing test coverage

## Workflow

### Step 1: Identify Specs to Implement

Run verification to see what needs implementation:

```bash
spec-test verify
```

Look for specs marked as `PENDING` (no test) or `FAIL` (test exists but fails).

### Step 2: Write the Test First

Create a test file in `tests/` directory. Use the `@spec` decorator to link to the specification.

```python
from spec_test import spec

@spec("AUTH-001", "User can log in with valid credentials")
def test_login_with_valid_credentials():
    # Arrange
    user = create_test_user(email="test@example.com", password="secure123")

    # Act
    result = login(email="test@example.com", password="secure123")

    # Assert
    assert result.success is True
    assert result.user.email == "test@example.com"
```

### Step 3: Run the Test (Expect Failure)

```bash
pytest tests/test_auth.py -v
```

The test should fail because the implementation does not exist yet.

### Step 4: Implement the Feature

Write the minimal code to make the test pass:

```python
def login(email: str, password: str) -> LoginResult:
    user = find_user_by_email(email)
    if user and verify_password(password, user.password_hash):
        return LoginResult(success=True, user=user)
    return LoginResult(success=False, user=None)
```

### Step 5: Verify

Run spec-test to confirm the spec is now satisfied:

```bash
spec-test verify
```

## Test Patterns

### Basic Test with @spec

```python
from spec_test import spec

@spec("CART-001", "User can add item to cart")
def test_add_item_to_cart():
    cart = Cart()
    item = Item(id="SKU-123", price=29.99)

    cart.add(item, quantity=2)

    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2
```

### Multiple Specs with @specs

When one test verifies multiple specifications:

```python
from spec_test import specs

@specs("CART-010", "CART-011")
def test_cart_total_with_discount():
    cart = Cart()
    cart.add(Item(price=100.00), quantity=1)
    cart.apply_discount(Discount(percent=10))

    # CART-010: total is sum of (price * quantity)
    # CART-011: percentage discounts applied correctly
    assert cart.total == 90.00
```

### Async Tests

```python
import pytest
from spec_test import spec

@spec("API-001", "API returns user data")
@pytest.mark.asyncio
async def test_get_user_endpoint():
    response = await client.get("/api/users/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1
```

### Class-Based Tests

```python
from spec_test import spec

class TestUserAuthentication:
    @spec("AUTH-001", "User can log in")
    def test_login_success(self):
        result = login("user@test.com", "password")
        assert result.success

    @spec("AUTH-002", "Invalid password fails")
    def test_login_invalid_password(self):
        result = login("user@test.com", "wrong")
        assert not result.success
```

## Architecture: Functional Core, Imperative Shell

**This is the guiding principle for all code.** Structure code so that:

- **Functional Core**: Pure functions containing all business logic (no side effects)
- **Imperative Shell**: Thin layer at the edges handling I/O, state, and side effects

```
┌─────────────────────────────────────┐
│       Imperative Shell              │  ← I/O, DB, network, state
│  ┌───────────────────────────────┐  │
│  │      Functional Core          │  │  ← Pure functions
│  │   (all business logic here)   │  │     No side effects
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Why This Matters

| Benefit | Pure Functions | Side Effects |
|---------|---------------|--------------|
| Testability | Trivial (input → output) | Requires mocks/integration |
| Provability | Z3 can verify | Cannot formally verify |
| Debugging | Predictable, reproducible | Hidden state issues |
| Composability | Functions compose cleanly | Order dependencies |

### Pure Function Rules

A function is **pure** if:
1. Same inputs always produce same outputs (deterministic)
2. No side effects (no I/O, no state mutation, no globals)

```python
# ✅ PURE - deterministic, no side effects
def calculate_discount(price: Decimal, percent: int) -> Decimal:
    return price * (percent / 100)

# ❌ IMPURE - reads external state
def calculate_discount(item_id: str) -> Decimal:
    item = database.get(item_id)  # Side effect!
    return item.price * 0.1

# ❌ IMPURE - mutates state
def apply_discount(cart: Cart) -> None:
    cart.total -= cart.total * 0.1  # Mutation!
```

### Refactoring to Functional Core

Transform impure code by extracting pure business logic:

```python
# ❌ BEFORE: Mixed concerns, hard to test
class OrderService:
    def place_order(self, user_id: str, items: list[str]):
        user = self.db.get_user(user_id)
        cart_items = [self.db.get_item(i) for i in items]

        if user.balance < sum(i.price for i in cart_items):
            raise InsufficientFunds()

        order = Order(user=user, items=cart_items)
        order.total = sum(i.price for i in cart_items)
        order.tax = order.total * Decimal("0.08")

        self.db.save(order)
        self.email.send_confirmation(user.email, order)
        return order

# ✅ AFTER: Functional Core + Imperative Shell

# CORE: Pure functions (easy to test, can be proven)
def calculate_order_total(items: list[Item]) -> Decimal:
    return sum(item.price for item in items)

def calculate_tax(subtotal: Decimal, rate: Decimal = Decimal("0.08")) -> Decimal:
    return subtotal * rate

def validate_balance(balance: Decimal, required: Decimal) -> Result[None, InsufficientFunds]:
    if balance < required:
        return Err(InsufficientFunds())
    return Ok(None)

def create_order(user: User, items: list[Item]) -> Order:
    subtotal = calculate_order_total(items)
    return Order(
        user_id=user.id,
        items=items,
        total=subtotal,
        tax=calculate_tax(subtotal),
    )

# SHELL: Side effects at the edges
class OrderService:
    def place_order(self, user_id: str, item_ids: list[str]) -> Order:
        # Fetch data (side effect)
        user = self.db.get_user(user_id)
        items = [self.db.get_item(i) for i in item_ids]

        # Pure business logic
        total = calculate_order_total(items)
        validate_balance(user.balance, total).unwrap()
        order = create_order(user, items)

        # Persist and notify (side effects)
        self.db.save(order)
        self.email.send_confirmation(user.email, order)
        return order
```

## Dependency Injection

Use **constructor injection** to make dependencies explicit and testable. No framework needed.

### Define Interfaces with Protocol

```python
from typing import Protocol

class Database(Protocol):
    def get(self, id: str) -> Any: ...
    def save(self, obj: Any) -> None: ...

class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...
```

### Inject Dependencies via Constructor

```python
class OrderService:
    def __init__(self, db: Database, email: EmailSender):
        self.db = db
        self.email = email

    def place_order(self, order: Order) -> None:
        total = calculate_total(order.items)  # Pure function
        order.total = total
        self.db.save(order)                   # Injected dependency
        self.email.send(...)                  # Injected dependency
```

### Create Test Mocks

```python
class MockDatabase:
    def __init__(self):
        self.saved = []

    def get(self, id: str) -> Any:
        return self._data.get(id)

    def save(self, obj: Any) -> None:
        self.saved.append(obj)

class MockEmailSender:
    def __init__(self):
        self.sent = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})
```

### Test with Injected Mocks

```python
@spec("ORDER-010", "Order saved to database")
def test_order_saved():
    mock_db = MockDatabase()
    mock_email = MockEmailSender()
    service = OrderService(db=mock_db, email=mock_email)

    service.place_order(Order(items=[...]))

    assert len(mock_db.saved) == 1

@spec("ORDER-011", "Confirmation email sent after order")
def test_confirmation_email_sent():
    mock_db = MockDatabase()
    mock_email = MockEmailSender()
    service = OrderService(db=mock_db, email=mock_email)

    service.place_order(Order(user=User(email="test@example.com"), items=[...]))

    assert len(mock_email.sent) == 1
    assert mock_email.sent[0]["to"] == "test@example.com"
```

### Default Dependencies Pattern

For convenience, provide defaults that can be overridden:

```python
class OrderService:
    def __init__(
        self,
        db: Database | None = None,
        email: EmailSender | None = None,
    ):
        self.db = db or PostgresDatabase()
        self.email = email or SmtpEmailSender()
```

### DI Benefits

| Without DI | With DI |
|------------|---------|
| Hidden dependencies | Explicit dependencies |
| Hard to test | Easy to mock |
| Tightly coupled | Loosely coupled |
| Can't swap implementations | Easy to swap (test/prod) |

## Testing Strategy

### Unit Tests for Pure Functions (Most Tests)

Fast, deterministic, no mocks needed:

```python
@spec("ORDER-001", "Order total is sum of item prices")
def test_calculate_order_total():
    items = [Item(price=Decimal("10.00")), Item(price=Decimal("5.00"))]
    assert calculate_order_total(items) == Decimal("15.00")

@spec("ORDER-002", "Tax calculated at 8% rate")
def test_calculate_tax():
    assert calculate_tax(Decimal("100.00")) == Decimal("8.00")

@spec("ORDER-003", "Insufficient balance returns error")
def test_validate_balance_insufficient():
    result = validate_balance(Decimal("50"), Decimal("100"))
    assert result.is_err()
```

### Mocks for Shell Testing (When Needed)

Use mocks to test the shell wiring without real I/O:

```python
from unittest.mock import Mock, patch

@spec("ORDER-010", "Order service saves to database")
def test_order_service_saves():
    # Arrange
    mock_db = Mock()
    mock_db.get_user.return_value = User(id="1", balance=Decimal("1000"))
    mock_db.get_item.return_value = Item(price=Decimal("10"))

    service = OrderService(db=mock_db, email=Mock())

    # Act
    service.place_order("1", ["item-1"])

    # Assert
    mock_db.save.assert_called_once()
```

### Integration Tests for Side Effects (Few Tests)

Mark integration specs clearly - these verify real I/O works:

```markdown
## Specs (in spec file)
- **ORDER-001**: Order total is sum of item prices
- **ORDER-002**: Tax calculated at 8% rate
- **ORDER-020** [integration]: Order persists to database
- **ORDER-021** [integration]: Confirmation email sent after order
```

```python
import pytest

@spec("ORDER-020", "Order persists to database")
@pytest.mark.integration
def test_order_persists_to_database():
    """Integration test - requires real database."""
    service = OrderService(db=real_db, email=mock_email)

    order = service.place_order("user-1", ["item-1"])

    # Verify in real database
    saved = real_db.query(Order).get(order.id)
    assert saved is not None
    assert saved.total == order.total
```

### Testing Pyramid

```
        /\
       /  \     Integration tests [integration]
      /    \    Real DB, network, file I/O
     /──────\   Use sparingly, slow
    /        \
   /   Unit   \ Unit tests (default)
  /   Tests    \ Pure functions, mocks
 /──────────────\ Fast, many of them
```

**Ratio**: Aim for ~90% unit tests, ~10% integration tests

### When to Use Mocks vs Integration Tests

| Scenario | Approach | Why |
|----------|----------|-----|
| Pure business logic | Unit test, no mocks | Deterministic, fast |
| Service orchestration | Mock dependencies (DI) | Test wiring without I/O |
| Verify DB queries work | Integration test | Need real DB behavior |
| External API contract | Integration test | Need real API |
| Email actually sends | Integration test | Verify real delivery |
| Complex DB transactions | Integration test | Test rollback, locks |

**Rule of thumb:**
- If testing **logic** → pure function unit test
- If testing **wiring** → mocks via DI
- If testing **I/O actually works** → integration test

## Pure Function Examples

### Good: Pure function, easy to test
```python
def calculate_cart_total(items: list[CartItem], discounts: list[Discount]) -> Decimal:
    subtotal = sum(item.price * item.quantity for item in items)
    discount_amount = sum(d.apply(subtotal) for d in discounts)
    return max(subtotal - discount_amount, Decimal("0"))

@spec("CART-010", "Cart total is sum of (price * quantity)")
def test_calculate_cart_total():
    items = [CartItem(price=Decimal("10.00"), quantity=2)]
    result = calculate_cart_total(items, discounts=[])
    assert result == Decimal("20.00")
```

### Avoid: Hidden dependencies
```python
# ❌ Avoid: Function with hidden dependencies
def get_cart_total():
    items = database.get_cart_items(current_user.id)  # Hidden state
    return sum(i.price * i.quantity for i in items)

# ✅ Better: Explicit dependencies
def get_cart_total(items: list[CartItem]) -> Decimal:
    return sum(i.price * i.quantity for i in items)
```

## Formal Verification with @provable

Pure functions can be formally verified with Z3:

```python
from spec_test import spec, provable, contract

@provable(spec="MATH-001")
@contract(
    requires=[lambda x, y: x >= 0, lambda x, y: y >= 0],
    ensures=[lambda result: result >= 0],
)
def add_positive(x: int, y: int) -> int:
    return x + y

# Z3 will PROVE this postcondition holds for ALL valid inputs
# Not just the test cases you write!
```

This is only possible with pure functions - side effects cannot be formally verified.

## File Organization

```
tests/
    test_auth.py        # Tests for AUTH-* specs
    test_cart.py        # Tests for CART-* specs
    test_api.py         # Tests for API-* specs
    conftest.py         # Shared fixtures
```

## Commands

```bash
# See which specs need tests
spec-test verify

# Check a single spec
spec-test check AUTH-001

# Run specific test file
pytest tests/test_auth.py -v

# Run tests for a specific spec marker
pytest -m "spec_id_AUTH_001" -v

# Run all spec-linked tests
pytest -m spec -v
```

## Checklist

For each spec being implemented:

- [ ] Test file exists in `tests/` directory
- [ ] Test uses `@spec("ID", "description")` decorator
- [ ] Test follows Arrange-Act-Assert pattern
- [ ] Test name is descriptive (`test_<what_is_being_tested>`)
- [ ] Implementation makes the test pass
- [ ] `spec-test verify` shows spec as PASS
- [ ] No unrelated tests were broken
