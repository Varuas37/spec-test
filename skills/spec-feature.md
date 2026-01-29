# spec-feature: Create a New Feature with Specifications

## Overview

This skill guides you through defining a new feature using specification-driven development. The workflow ensures every feature is fully specified before implementation begins.

## When to Use

- User asks to "add a feature" or "implement a new capability"
- User describes functionality that does not exist yet
- User wants to plan a feature before coding
- Starting work on a new user story or epic

## Workflow

### Step 1: Understand the Feature

Before writing specs, clarify:

1. **What** does this feature do?
2. **Who** is it for (user type/actor)?
3. **Why** is it needed (business value)?
4. **How** will users interact with it?

Ask clarifying questions if any of these are unclear.

### Step 2: Create or Update Spec File

Specs live in `design/specs/*.md` files. Create a new file or add to an existing one.

**File naming**: `{domain}.md` (e.g., `auth.md`, `payments.md`)

### Step 3: Write Specifications

Use this format for each requirement:

```markdown
## Feature Name

### Overview
Brief description of the feature.

### Requirements

#### Category Name
- **PREFIX-001**: First requirement description
- **PREFIX-002**: Second requirement description
- **PREFIX-003** [manual]: Requirement needing manual verification
```

### Step 4: Assign Spec IDs

Follow this convention:

- **PREFIX**: Short domain code (3-5 chars, uppercase)
  - `AUTH` for authentication
  - `CART` for shopping cart
  - `API` for API endpoints
  - `USER` for user management

- **NUMBER**: Sequential, zero-padded (001, 002, 003...)

### Step 5: Verify Spec Coverage

Run to see what needs tests:

```bash
spec-test list-specs
```

## Spec Format Reference

### Basic Requirement

```markdown
- **AUTH-001**: User can log in with email and password
```

### With Verification Type

```markdown
- **AUTH-002** [manual]: Password reset email is sent within 5 minutes
- **AUTH-003** [contract]: Password hash uses bcrypt with cost factor 12
```

### Verification Types

| Type | Meaning | Test Type |
|------|---------|-----------|
| (none) | Automated unit test | Fast, pure function test |
| `[integration]` | Integration test required | Tests real I/O (DB, API, etc.) |
| `[manual]` | Manual verification | Human check required |
| `[contract]` | Contract/property-based | Runtime @contract verification |
| `[provable]` | Formal proof | Z3 mathematical verification |

## Examples

### Example 1: User Authentication Feature

```markdown
# User Authentication Specification

## Overview
Authentication system allowing users to sign up, log in, and manage sessions.

## Requirements

### Sign Up
- **AUTH-001**: User can create account with email and password
- **AUTH-002**: Email must be unique across all accounts
- **AUTH-003**: Password must be at least 8 characters
- **AUTH-004**: Password must contain uppercase, lowercase, and number

### Login
- **AUTH-010**: User can log in with valid email and password
- **AUTH-011**: Login fails with invalid credentials
- **AUTH-012**: Account is locked after 5 failed attempts

### Session Management
- **AUTH-020**: Successful login returns JWT token
- **AUTH-021**: Token expires after 24 hours
- **AUTH-022** [manual]: User can view active sessions
```

### Example 2: Shopping Cart Feature

```markdown
# Shopping Cart Specification

## Overview
Shopping cart allowing users to add, remove, and checkout items.

## Requirements

### Cart Operations
- **CART-001**: User can add item to cart
- **CART-002**: User can remove item from cart
- **CART-003**: User can update item quantity
- **CART-004**: Cart persists across sessions for logged-in users

### Cart Calculations
- **CART-010**: Cart total is sum of (price * quantity) for all items
- **CART-011**: Cart applies percentage discounts correctly
- **CART-012**: Cart applies fixed amount discounts correctly
- **CART-013**: Discount cannot reduce total below zero
```

## Commands

```bash
# List all specs to see current coverage
spec-test list-specs

# Check if your new specs are discovered
spec-test list-specs --specs specs

# Verify after writing tests
spec-test verify
```

## Architecture: Functional Core, Imperative Shell

When designing features, structure specs to separate:

**Functional Core** (pure logic, most specs):
- Business rules, calculations, validations
- Data transformations
- Decision logic

**Imperative Shell** (side effects, mark as `[integration]`):
- Database persistence
- External API calls
- Email/notification sending
- File I/O

### Example: Separating Core and Shell Specs

```markdown
## Order Processing

### Core Logic (unit testable, can use @provable)
- **ORDER-001**: Order total is sum of item prices
- **ORDER-002**: Tax calculated at configured rate
- **ORDER-003**: Discount cannot reduce total below zero
- **ORDER-004**: Invalid quantity rejected (must be > 0)

### Integration (real I/O, mark as [integration])
- **ORDER-020** [integration]: Order persists to database
- **ORDER-021** [integration]: Confirmation email sent after order
- **ORDER-022** [integration]: Inventory decremented on order
```

**Why this matters:**
- Core specs → fast unit tests, Z3 proofs possible
- Integration specs → slower tests, run separately, fewer of them
- Clear separation makes testing strategy obvious

## Checklist

Before moving to implementation:

- [ ] Each requirement has a unique ID
- [ ] IDs follow PREFIX-NNN convention
- [ ] Requirements are testable (clear pass/fail criteria)
- [ ] Pure logic specs separated from I/O specs
- [ ] I/O specs marked with `[integration]`
- [ ] Manual verification items are marked `[manual]`
- [ ] Specs are saved in `design/specs/*.md`
- [ ] Running `spec-test list-specs` shows new specs
