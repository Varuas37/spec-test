# spec-test

**Make AI-generated code trustworthy through specification-driven development.**

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
|  AI Generates  | --> |    spec-test      | --> |  Verified Code  |
|     Code       |     |     VERIFIES      |     |   Ready to Ship |
+----------------+     +-------------------+     +-----------------+
```

## Quick Start

### Installation

```bash
pip install spec-test

# With Z3 formal proofs (optional)
pip install spec-test[z3]
```

### 1. Initialize Project

```bash
spec-test init
```

Creates:
```
design/
  issues/     # Why - intentions, decisions
  specs/      # What - formal requirements
  prompts/    # How - AI instructions
```

### 2. Write an Issue First

Document *why* before *what*:

```markdown
# design/issues/001-user-auth.md

## Summary
Add user authentication to the API.

## Motivation
Users need secure access to their data.

## Decision
Use JWT tokens with 24h expiry.
```

### 3. Define Specs

```markdown
# design/specs/auth.md

## User Authentication

### Related Issue
- [001-user-auth](../issues/001-user-auth.md)

### Requirements
- **AUTH-001**: User can login with valid email and password
- **AUTH-002**: Invalid credentials return 401 error
- **AUTH-003**: JWT token expires after 24 hours
- **AUTH-010** [integration]: User session persists to database
```

### 4. Implement with Tests

```python
from spec_test import spec

@spec("AUTH-001", "User can login with valid email and password")
def test_login_success():
    result = login("user@example.com", "password123")
    assert result.success
    assert result.token is not None
```

### 5. Add Runtime Contracts

```python
from spec_test import contract

@contract(
    spec="AUTH-001",
    requires=[
        lambda email, password: "@" in email,
        lambda email, password: len(password) >= 8,
    ],
    ensures=[
        lambda result: result.token is not None,
    ],
)
def login(email: str, password: str) -> LoginResult:
    user = db.get_user(email)
    if verify_password(password, user.password_hash):
        return LoginResult(success=True, token=generate_jwt(user))
    return LoginResult(success=False, token=None)
```

### 6. Verify

```bash
$ spec-test verify

╭─────────────────────────────────────────╮
│   Specification Verification Report     │
╰─────────────────────────────────────────╯

✓ AUTH-001: User can login with valid email and password
✓ AUTH-002: Invalid credentials return 401 error
✓ AUTH-003: JWT token expires after 24 hours
! AUTH-010: No test

Summary: 3 passing, 0 failing, 1 missing
```

## Architecture: Functional Core, Imperative Shell

All code should follow this pattern with **Dependency Injection**:

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

## Verification Types

Mark specs with verification type in brackets:

| Type | Meaning |
|------|---------|
| (none) | Automated unit test |
| `[integration]` | Integration test (real I/O) |
| `[manual]` | Manual human verification |
| `[contract]` | Runtime contract verification |
| `[provable]` | Z3 formal proof |

```markdown
- **AUTH-001**: User can login (unit test)
- **AUTH-010** [integration]: Session persists to database
- **AUTH-020** [manual]: UI follows brand guidelines
- **AUTH-030** [provable]: Token expiry is always positive
```

## Runtime Contracts

### Basic Contract

```python
from spec_test import contract

@contract(
    spec="CART-001",
    requires=[lambda items: len(items) > 0],
    ensures=[lambda result: result >= 0],
)
def calculate_total(items: list[Item]) -> Decimal:
    return sum(item.price * item.quantity for item in items)
```

### With Invariants

```python
@contract(
    spec="CART-002",
    requires=[lambda items, discount: discount >= 0],
    ensures=[lambda result: result >= 0],
    invariants=[lambda items, discount: discount <= 100],
)
def apply_discount(items: list[Item], discount: int) -> Decimal:
    total = calculate_total(items)
    return total * (1 - discount / 100)
```

### Comparing Pre/Post State with `old()`

```python
from spec_test import contract, Old

@contract(
    spec="LIST-001",
    capture_old=True,
    ensures=[lambda result, old: len(result) == len(old.items) + 1],
)
def append_item(items: list, item) -> list:
    return items + [item]
```

## Z3 Formal Proofs

For mathematical verification of pure functions:

```bash
pip install spec-test[z3]
```

```python
from spec_test import provable, contract

@provable(spec="MATH-001")
@contract(
    requires=[lambda x, y: x >= 0, lambda x, y: y >= 0],
    ensures=[lambda result: result >= 0],
)
def add_positive(x: int, y: int) -> int:
    return x + y
```

```bash
$ spec-test verify --proofs

╭─────────────────────────────────────╮
│   Proof Verification Summary        │
╰─────────────────────────────────────╯
Proven: 1 | Refuted: 0 | Unknown: 0
```

## For AI Agents

spec-test is designed for AI-assisted development.

### Workflow

```
Write Issue --> Define Specs --> Implement Code --> Verify --> Review
    |               |                 |               |          |
  (why)           (what)            (how)          (check)    (approve)
```

### Add to CLAUDE.md

```markdown
## Specification-Driven Development

This project uses spec-test. Every behavior must be backed by a passing test.

## Architecture
- Pure functions for business logic (Functional Core)
- Dependency Injection for I/O (Imperative Shell)
- Integration tests only for verifying real I/O

## Rules
1. Write an issue before writing specs
2. Every spec ID must have a corresponding @spec test
3. Run `spec-test verify` before committing
4. Prefer pure functions; push side effects to edges
```

### AI Agent Skills

Initialize with skills for Claude:

```bash
spec-test init
```

Installs skills to `.claude/skills/`:
- `spec-workflow.md` - Complete development workflow
- `spec-issue.md` - Writing issues
- `spec-feature.md` - Defining specifications
- `spec-implement.md` - Implementation with architecture principles
- `spec-verify.md` - Running verification

## Commands

```bash
spec-test verify              # Verify all specs have passing tests
spec-test verify --proofs     # Include Z3 formal proof verification
spec-test verify --coverage   # Include code coverage analysis
spec-test list-specs          # List all specifications
spec-test list-specs -i       # Show related issues for each spec
spec-test check AUTH-001      # Verify single spec
spec-test init                # Initialize spec-test in a project
spec-test context             # Output CLAUDE.md for LLM context
```

## Roadmap

> **Note:** spec-test is in active development.

- [x] Spec-to-test linking with `@spec` decorator
- [x] Runtime contracts with `@contract` (requires/ensures/invariants)
- [x] `old()` support for comparing pre/post state
- [x] Z3 formal proof verification with `@provable`
- [x] Issues-first workflow with `design/` structure
- [x] AI agent skills
- [ ] Hypothesis property testing integration
- [ ] Spec coverage reporting

## Contributing

```bash
git clone https://github.com/Varuas37/spec-test.git
cd spec-test
uv sync

# Run tests
uv run pytest

# Run verification
uv run spec-test verify
```

## License

MIT

---

**Stop reviewing code. Start verifying specs.**

```bash
pip install spec-test
```
