# spec-test

**Make AI-generated code trustworthy through mathematical verification.**

Stop reviewing code. Start verifying specs.

---

## The Problem

AI writes code 100x faster than humans can review it. Traditional code review is now the bottleneck:

```
Human writes code     -->  Human reviews code     -->  Ship
      (slow)                    (slow)

AI writes code        -->  Human reviews code     -->  Ship
      (fast)                    (slow)
                                  ^
                            BOTTLENECK
```

You cannot keep up. And the code AI generates is often correct, but *how do you know?*

## The Solution

**Shift review from CODE to SPECS.**

Specs are 10x smaller than implementations. If your specs are correct and verification passes, the code is correct by definition.

```
                         +------------------+
                         |    YOU REVIEW    |
                         |      SPECS       |
                         |   (10 minutes)   |
                         +--------+---------+
                                  |
                                  v
+----------------+     +-------------------+     +-----------------+
|  AI Generates  | --> |   spec-test v2    | --> |  Verified Code  |
|     Code       |     |    VERIFIES       |     |   Ready to Ship |
+----------------+     +-------------------+     +-----------------+
```

## How It Works

```
FEATURES (what users want)
    |
    v
SPECS (formal requirements)
    |
    +--> Runtime Contracts     [catches violations immediately]
    |
    +--> Property Testing      [finds edge cases with Hypothesis]
    |
    +--> Formal Proofs         [mathematical certainty with Z3]
    |
    v
VERIFIED CODE
```

### The Verification Stack

```
+------------------------------------------------------------------+
|                        VERIFICATION LAYERS                        |
+------------------------------------------------------------------+
|                                                                   |
|  Layer 3: FORMAL PROOFS (Z3)                                     |
|  "This function CANNOT return negative values"                    |
|  Mathematical proof. 100% certainty.                             |
|                                                                   |
+------------------------------------------------------------------+
|                                                                   |
|  Layer 2: PROPERTY TESTING (Hypothesis)                          |
|  "For ALL inputs, output > 0"                                    |
|  Generates 1000s of test cases. Finds edge cases.                |
|                                                                   |
+------------------------------------------------------------------+
|                                                                   |
|  Layer 1: RUNTIME CONTRACTS                                      |
|  "Input must be positive, output must be non-empty"              |
|  Catches violations immediately during execution.                |
|                                                                   |
+------------------------------------------------------------------+
```

## Quick Start

### Installation

```bash
pip install spec-test
# or with uv
uv add spec-test
```

### 1. Define a Feature

Features are high-level capabilities users care about:

```markdown
# docs/features/user-auth.md

## Feature: User Authentication

Users can securely log in and manage their sessions.

### Specs
- AUTH-001: Login with email/password
- AUTH-002: Session expires after 24 hours
- AUTH-003: Invalid credentials return 401
```

### 2. Write Formal Specs

Specs combine human-readable descriptions with machine-verifiable contracts:

```python
# specs/auth_specs.py

from spec_test import Spec

login_spec = Spec(
    id="AUTH-001",
    summary="User can login with valid credentials",

    # Formal contracts (machine-verifiable)
    requires=[
        "email is valid email format",
        "password.length >= 8",
    ],
    ensures=[
        "returns JWT token",
        "token.expiry == now + 24h",
    ],
    invariants=[
        "user.password is never logged",
        "failed attempts < 5 before lockout",
    ],
)
```

### 3. Implement with Contracts

```python
# src/auth.py

from spec_test import contract, requires, ensures

@contract(login_spec)
def login(email: str, password: str) -> Token:
    """
    Runtime contracts are checked automatically:
    - requires: validated before function runs
    - ensures: validated after function returns
    """
    user = db.get_user(email)
    if not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    return generate_token(user)
```

### 4. Add Property Tests

```python
# tests/test_auth.py

from spec_test import spec, property_test
from hypothesis import given, strategies as st

@spec("AUTH-001", "User can login with valid credentials")
@property_test
@given(
    email=st.emails(),
    password=st.text(min_size=8, max_size=128)
)
def test_login_with_valid_credentials(email, password):
    """Hypothesis generates 1000s of test cases automatically."""
    # Setup: create user with these credentials
    create_user(email, password)

    # Act
    token = login(email, password)

    # Assert
    assert token is not None
    assert token.user_email == email
```

### 5. Verify Everything

```bash
$ spec-test verify

  spec-test v2.0 - Verification Report
  =====================================

  Features: 3 total
    [*] User Authentication (3 specs)
    [*] API Tokens (2 specs)
    [ ] Billing (1 spec pending)

  Verification Layers:
    Contracts:  47/47 passing
    Properties: 23/23 passing (14,729 test cases)
    Proofs:     12/12 verified

  +--------------------------------------------------+
  |                                                  |
  |   AUTH-001: Login with email/password            |
  |   ----------------------------------------       |
  |   [x] Contract: requires validated               |
  |   [x] Contract: ensures validated                |
  |   [x] Property: 1,247 cases passed               |
  |   [x] Proof: token expiry mathematically proven  |
  |                                                  |
  +--------------------------------------------------+

  Coverage: 98% (49/50 specs verified)

  VERIFICATION PASSED
```

## Spec Format Reference

### Simple Spec (current v1 format)

Works today - link tests to requirements:

```python
from spec_test import spec

@spec("AUTH-001", "User can login with email/password")
def test_user_login():
    response = client.post("/login", json={
        "email": "user@example.com",
        "password": "secretpass"
    })
    assert response.status_code == 200
```

### Formal Spec (v2 format)

Full formal specification with contracts:

```python
from spec_test import Spec

transfer_money = Spec(
    id="PAY-001",
    summary="Transfer money between accounts",

    # Preconditions - must be true before execution
    requires=[
        "from_account.balance >= amount",
        "amount > 0",
        "from_account != to_account",
    ],

    # Postconditions - must be true after execution
    ensures=[
        "from_account.balance == old(from_account.balance) - amount",
        "to_account.balance == old(to_account.balance) + amount",
        "total_money() == old(total_money())",  # Conservation
    ],

    # Always true - checked at every step
    invariants=[
        "account.balance >= 0",  # No negative balances
        "audit_log.is_immutable()",
    ],
)
```

## For AI Agents

spec-test is designed for AI-assisted development workflows.

### Agent Workflow

```
1. Human writes FEATURE (what they want)
       |
       v
2. AI generates SPECS (formal requirements)
       |
       v
3. Human reviews SPECS (10 min instead of 2 hours)
       |
       v
4. AI implements CODE
       |
       v
5. spec-test VERIFIES (automated)
       |
       v
6. Ship with confidence
```

### Agent Instructions

Add to your `CLAUDE.md` or system prompt:

```markdown
## Specification-Driven Development

This project uses spec-test for verification. Follow this workflow:

1. Before implementing, write a formal spec:
   - Define requires (preconditions)
   - Define ensures (postconditions)
   - Define invariants (always-true properties)

2. Implement with @contract decorator for runtime checks

3. Add property tests with Hypothesis for edge cases

4. Run `spec-test verify` - must pass before committing

5. Never claim code works without verification passing
```

### Why This Works for AI

1. **Specs are reviewable** - Humans can verify 50 lines of specs faster than 500 lines of code

2. **Contracts catch AI mistakes** - Runtime checks catch when AI misunderstands requirements

3. **Property testing finds edge cases** - Hypothesis tests inputs the AI never considered

4. **Proofs provide certainty** - Mathematical verification eliminates doubt

## Architecture Philosophy

### Pure Functions + Immutable Data

Code that's easy to verify follows these patterns:

```python
# GOOD: Pure function, easy to verify
def calculate_total(items: list[Item]) -> Decimal:
    return sum(item.price * item.quantity for item in items)

# BAD: Side effects, hard to verify
def process_order(order_id: int) -> None:
    order = db.get(order_id)
    order.status = "processed"
    db.save(order)
    send_email(order.user)
    update_inventory(order.items)
```

Restructure side-effectful code:

```python
# GOOD: Separate pure logic from effects
def calculate_order_changes(order: Order) -> OrderChanges:
    """Pure function - returns what SHOULD change."""
    return OrderChanges(
        new_status="processed",
        inventory_deltas=calculate_deltas(order.items),
        email=compose_email(order.user),
    )

def apply_changes(changes: OrderChanges) -> None:
    """Effectful function - applies the changes."""
    # This is the only place with side effects
    db.update_status(changes.new_status)
    inventory.apply(changes.inventory_deltas)
    email.send(changes.email)
```

Now you can formally verify `calculate_order_changes` while keeping `apply_changes` simple.

## Commands

```bash
# Core verification
spec-test verify              # Full verification (contracts + properties + proofs)
spec-test verify --fast       # Skip proofs, run contracts + properties only
spec-test verify --contracts  # Contracts only (fastest)

# Exploration
spec-test list-specs          # List all specs
spec-test list-features       # List features and their specs
spec-test check AUTH-001      # Verify single spec

# Setup
spec-test init                # Initialize spec-test in a project
spec-test context             # Output context for LLM assistants
```

## Configuration

```toml
# pyproject.toml

[tool.spec-test]
spec_dirs = ["docs/specs", "specs"]
test_dirs = ["tests"]

[tool.spec-test.verification]
contracts = true          # Runtime contract checking
properties = true         # Hypothesis property testing
proofs = false            # Z3 formal proofs (opt-in)

[tool.spec-test.hypothesis]
max_examples = 1000       # Test cases per property
deadline = 5000           # Max ms per test case
```

## Why spec-test?

| Approach | Review Time | Confidence | Catches Edge Cases |
|----------|-------------|------------|-------------------|
| Code review | 2+ hours | Low | Rarely |
| Unit tests | 30 min | Medium | Sometimes |
| **spec-test** | **10 min** | **High** | **Always** |

The math is simple:

- Reviewing 500 lines of AI-generated code: **2 hours**
- Reviewing 50 lines of specs that code must satisfy: **10 minutes**
- Confidence with spec-test verification: **Higher than manual review**

## Roadmap

- [x] v1.0: Spec-to-test linking with `@spec` decorator
- [ ] v2.0: Formal specs with requires/ensures/invariants
- [ ] v2.1: Runtime contract enforcement
- [ ] v2.2: Hypothesis property testing integration
- [ ] v3.0: Z3 formal proof verification

## Contributing

```bash
# Clone and setup
git clone https://github.com/anthropics/spec-test.git
cd spec-test
uv sync

# Run verification (we use spec-test on itself)
uv run spec-test verify

# All specs must pass before committing
```

## License

MIT

---

**Stop reviewing code. Start verifying specs.**

```bash
pip install spec-test
```
