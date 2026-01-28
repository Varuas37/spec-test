# spec-implement: Implement Code That Matches Specifications

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

## Pure Function Pattern

For better testability, prefer pure functions with explicit inputs and outputs:

### Pure Function Example

```python
# Good: Pure function, easy to test
def calculate_cart_total(items: list[CartItem], discounts: list[Discount]) -> Decimal:
    subtotal = sum(item.price * item.quantity for item in items)
    discount_amount = sum(d.apply(subtotal) for d in discounts)
    return max(subtotal - discount_amount, Decimal("0"))

# Test is simple and deterministic
@spec("CART-010", "Cart total is sum of (price * quantity)")
def test_calculate_cart_total():
    items = [CartItem(price=Decimal("10.00"), quantity=2)]
    result = calculate_cart_total(items, discounts=[])
    assert result == Decimal("20.00")
```

### Avoid Side Effects

```python
# Avoid: Function with hidden dependencies
def get_cart_total():
    items = database.get_cart_items(current_user.id)  # Hidden state
    return sum(i.price * i.quantity for i in items)

# Better: Explicit dependencies
def get_cart_total(items: list[CartItem]) -> Decimal:
    return sum(i.price * i.quantity for i in items)
```

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
