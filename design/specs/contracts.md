# Feature: Runtime Contracts

Contracts enforce preconditions and postconditions at runtime.

## Related Issue
- [ISSUE-002: Runtime Contract Enforcement](../issues/002-runtime-contracts.md)

---

## Contract Decorator

- **CONTRACT-001**: @contract decorator validates preconditions

  **Contracts:**
  - Requires: requires is list of callables
  - Ensures: raises ContractError if any precondition fails

- **CONTRACT-002**: @contract decorator validates postconditions

  **Contracts:**
  - Requires: ensures is list of callables
  - Ensures: raises ContractError if any postcondition fails

- **CONTRACT-003**: @contract links to spec ID

  **Contracts:**
  - Requires: spec is valid spec ID string
  - Ensures: contract registered with spec_id for verification

- **CONTRACT-004**: @contract preserves function behavior

  **Contracts:**
  - Requires: all preconditions pass
  - Ensures: returns same result as undecorated function

- **CONTRACT-005**: @contract works with async functions

  **Contracts:**
  - Requires: function is async
  - Ensures: awaitable behavior preserved, contracts checked

- **CONTRACT-006**: @contract validates invariants before and after execution

  **Contracts:**
  - Requires: invariants is list of callables
  - Ensures: each invariant checked before AND after function execution

- **CONTRACT-007**: @contract supports old() for capturing pre-state

  **Contracts:**
  - Requires: capture_old=True
  - Ensures: postconditions receive (result, old) where old has deep copies of args

---

## Contract Validation

- **CONTRACT-010**: Callable preconditions receive function arguments

  **Contracts:**
  - Requires: precondition is callable
  - Ensures: called with (*args, **kwargs) of decorated function

- **CONTRACT-011**: Callable postconditions receive result

  **Contracts:**
  - Requires: postcondition is callable
  - Ensures: called with (result) of decorated function

- **CONTRACT-012** [SKIP]: String preconditions evaluated as expressions

  Deferred - requires expression parsing.

- **CONTRACT-013**: Callable invariants receive function arguments

  **Contracts:**
  - Requires: invariant is callable
  - Ensures: called with (*args, **kwargs) of decorated function

- **CONTRACT-014**: Old object provides access to captured argument values

  **Contracts:**
  - Requires: capture_old=True on contract
  - Ensures: old.argname returns deep copy of original argument value

---

## Contract Discovery

- **CONTRACT-020**: Discover contracts by spec ID

  **Contracts:**
  - Requires: contract has spec="SPEC-ID"
  - Ensures: contract discoverable for verification reporting

- **CONTRACT-021**: Report contract coverage in verify

  **Contracts:**
  - Requires: spec exists
  - Ensures: shows contract status (defined/missing) per spec
