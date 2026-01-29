# Feature: Z3 Formal Proof Verification

Z3 integration enables formal verification of contracts using SMT solving, providing mathematical guarantees that code satisfies its specifications.

---

## Overview

Z3 is an SMT (Satisfiability Modulo Theories) solver that can mathematically prove properties about code. This feature translates Python contracts (preconditions/postconditions) into Z3 constraints and attempts to prove they always hold.

**Scope and Limitations:**
- Z3 verification works on a subset of Python: pure functions with numeric/boolean operations
- Complex data structures, I/O, and dynamic features are not verifiable
- Proofs are sound but incomplete: a failed proof doesn't mean a bug exists
- Z3 operates on symbolic execution, not concrete test values

---

## Provable Decorator

- **Z3-001**: @provable decorator marks functions for formal verification

  **Contracts:**
  - Requires: function has @contract with requires/ensures
  - Ensures: function registered for Z3 verification

- **Z3-002**: @provable decorator preserves runtime contract checking

  **Contracts:**
  - Requires: function decorated with @provable
  - Ensures: @contract runtime checks still execute at call time

- **Z3-003**: @provable accepts verification timeout parameter

  **Contracts:**
  - Requires: timeout is positive integer (seconds)
  - Ensures: Z3 solver times out after specified duration
  - Default: 30 seconds

- **Z3-004**: @provable accepts assumptions parameter for additional constraints

  **Contracts:**
  - Requires: assumptions is list of constraint expressions
  - Ensures: assumptions added to Z3 context before verification

- **Z3-005**: @provable can disable runtime checks when proof succeeds

  **Contracts:**
  - Requires: skip_runtime_if_proven=True
  - Ensures: runtime contract checks bypassed for proven functions

---

## Contract Translation

### Type Mapping

- **Z3-010**: Integer parameters translate to Z3 Int sort

  **Contracts:**
  - Requires: parameter annotated as int
  - Ensures: Z3 variable created with Int sort

- **Z3-011**: Float parameters translate to Z3 Real sort

  **Contracts:**
  - Requires: parameter annotated as float
  - Ensures: Z3 variable created with Real sort

- **Z3-012**: Boolean parameters translate to Z3 Bool sort

  **Contracts:**
  - Requires: parameter annotated as bool
  - Ensures: Z3 variable created with Bool sort

- **Z3-013**: Optional types translate to nullable Z3 variables

  **Contracts:**
  - Requires: parameter annotated as Optional[T]
  - Ensures: Z3 variable can be None or T

- **Z3-014**: List types translate to Z3 Array sort

  **Contracts:**
  - Requires: parameter annotated as List[T]
  - Ensures: Z3 Array(Int, T) created for indexable access

- **Z3-015** [FUTURE]: Dict types translate to Z3 Array sort with key type

  Deferred - requires complex key handling.

### Expression Translation

- **Z3-020**: Arithmetic expressions translate to Z3 arithmetic

  **Contracts:**
  - Requires: expression uses +, -, *, /, //, %, **
  - Ensures: equivalent Z3 arithmetic expression generated

- **Z3-021**: Comparison expressions translate to Z3 comparisons

  **Contracts:**
  - Requires: expression uses ==, !=, <, <=, >, >=
  - Ensures: equivalent Z3 comparison expression generated

- **Z3-022**: Boolean expressions translate to Z3 logic

  **Contracts:**
  - Requires: expression uses and, or, not
  - Ensures: equivalent Z3 And, Or, Not expressions generated

- **Z3-023**: Conditional expressions translate to Z3 If

  **Contracts:**
  - Requires: expression uses ternary if/else
  - Ensures: equivalent Z3 If expression generated

- **Z3-024**: Lambda preconditions/postconditions are inspected via AST

  **Contracts:**
  - Requires: contract uses lambda expression
  - Ensures: lambda body extracted and translated to Z3

- **Z3-025**: String contract expressions parsed to Z3

  **Contracts:**
  - Requires: contract uses string expression like "x > 0"
  - Ensures: string parsed to AST and translated to Z3

---

## Verification Patterns

### Numeric Bounds

- **Z3-030**: Verify result is non-negative

  **Contracts:**
  - Requires: postcondition asserts result >= 0
  - Ensures: Z3 proves no execution path returns negative

- **Z3-031**: Verify no integer overflow for bounded types

  **Contracts:**
  - Requires: @provable(check_overflow=True, bits=64)
  - Ensures: Z3 proves result fits in specified bit width

- **Z3-032**: Verify division by zero cannot occur

  **Contracts:**
  - Requires: function contains division operation
  - Ensures: Z3 proves divisor is never zero under preconditions

- **Z3-033**: Verify numeric range constraints

  **Contracts:**
  - Requires: postcondition asserts lo <= result <= hi
  - Ensures: Z3 proves result always in range

### Array/Sequence Safety

- **Z3-040**: Verify array index within bounds

  **Contracts:**
  - Requires: function accesses list[index]
  - Ensures: Z3 proves 0 <= index < len(list) under preconditions

- **Z3-041**: Verify slice bounds are valid

  **Contracts:**
  - Requires: function uses list[start:end]
  - Ensures: Z3 proves 0 <= start <= end <= len(list)

- **Z3-042**: Verify list is non-empty before access

  **Contracts:**
  - Requires: precondition asserts len(list) > 0
  - Ensures: Z3 uses constraint in array access proofs

### None Safety

- **Z3-050**: Verify no None dereference

  **Contracts:**
  - Requires: parameter is Optional[T] and accessed
  - Ensures: Z3 proves parameter is not None at access point

- **Z3-051**: Verify None check before access

  **Contracts:**
  - Requires: code pattern "if x is not None: x.attr"
  - Ensures: Z3 path-sensitive analysis proves safety

- **Z3-052**: Verify result is not None when declared non-optional

  **Contracts:**
  - Requires: return type is T (not Optional)
  - Ensures: Z3 proves no execution path returns None

### Loop Invariants

- **Z3-060**: Support loop invariant annotations

  **Contracts:**
  - Requires: @invariant decorator on loop or comment annotation
  - Ensures: invariant translated to Z3 and checked

- **Z3-061**: Verify loop invariant holds on entry

  **Contracts:**
  - Requires: loop has @invariant
  - Ensures: Z3 proves invariant true before first iteration

- **Z3-062**: Verify loop invariant preserved by iteration

  **Contracts:**
  - Requires: loop has @invariant
  - Ensures: Z3 proves invariant(n) implies invariant(n+1)

- **Z3-063**: Verify loop terminates (bounded loops only)

  **Contracts:**
  - Requires: loop has explicit bound (range, while with counter)
  - Ensures: Z3 proves termination via decreasing variant

- **Z3-064** [FUTURE]: Infer simple loop invariants automatically

  Deferred - requires sophisticated analysis.

---

## Proof Results and Caching

### Result Types

- **Z3-070**: Report PROVEN when Z3 proves all contracts

  **Contracts:**
  - Requires: Z3 returns unsat for negated postcondition
  - Ensures: verification status is PROVEN

- **Z3-071**: Report REFUTED when Z3 finds counter-example

  **Contracts:**
  - Requires: Z3 returns sat with model
  - Ensures: verification status is REFUTED with counter-example

- **Z3-072**: Report UNKNOWN when Z3 cannot decide

  **Contracts:**
  - Requires: Z3 returns unknown or times out
  - Ensures: verification status is UNKNOWN with reason

- **Z3-073**: Report SKIPPED for non-translatable functions

  **Contracts:**
  - Requires: function uses unsupported Python features
  - Ensures: verification status is SKIPPED with explanation

### Counter-Examples

- **Z3-080**: Generate concrete counter-example values

  **Contracts:**
  - Requires: proof fails with Z3 model
  - Ensures: concrete values for all parameters extracted

- **Z3-081**: Format counter-example as executable test case

  **Contracts:**
  - Requires: counter-example generated
  - Ensures: output is valid Python function call

- **Z3-082**: Include violated contract in counter-example

  **Contracts:**
  - Requires: counter-example generated
  - Ensures: shows which precondition or postcondition failed

- **Z3-083**: Minimize counter-example when possible

  **Contracts:**
  - Requires: counter-example generated
  - Ensures: attempt to find smaller values that still fail

### Caching

- **Z3-090**: Cache proof results by function signature and contract hash

  **Contracts:**
  - Requires: function verified
  - Ensures: result cached with hash of (source, contracts, Z3 version)

- **Z3-091**: Invalidate cache when function source changes

  **Contracts:**
  - Requires: function source modified
  - Ensures: cached proof invalidated

- **Z3-092**: Invalidate cache when contracts change

  **Contracts:**
  - Requires: @contract preconditions or postconditions modified
  - Ensures: cached proof invalidated

- **Z3-093**: Store cache in configurable location

  **Contracts:**
  - Requires: cache_dir configured in pyproject.toml or CLI
  - Ensures: proofs stored in specified directory
  - Default: .spec-test/proofs/

- **Z3-094**: Support incremental verification of changed functions only

  **Contracts:**
  - Requires: --incremental flag
  - Ensures: only re-verify functions with cache misses

---

## CLI Integration

- **Z3-100**: `spec-test verify --proofs` runs Z3 verification

  **Contracts:**
  - Requires: --proofs flag provided
  - Ensures: Z3 verification runs on all @provable functions

- **Z3-101**: `spec-test verify --proofs-only` runs only Z3 verification

  **Contracts:**
  - Requires: --proofs-only flag provided
  - Ensures: only Z3 verification runs, skips tests

- **Z3-102**: `spec-test prove FUNCTION` verifies single function

  **Contracts:**
  - Requires: function name or path provided
  - Ensures: Z3 verification runs on specified function only

- **Z3-103**: Proof results included in verification report

  **Contracts:**
  - Requires: --proofs flag used
  - Ensures: report shows PROVEN/REFUTED/UNKNOWN per function

- **Z3-104**: Exit code 3 when proofs fail

  **Contracts:**
  - Requires: any proof returns REFUTED
  - Ensures: process exits with code 3

- **Z3-105**: Exit code 0 when all proofs succeed or are unknown

  **Contracts:**
  - Requires: no REFUTED proofs
  - Ensures: process exits with code 0

- **Z3-106**: `--fail-on-unknown` makes UNKNOWN results fail

  **Contracts:**
  - Requires: --fail-on-unknown flag provided
  - Ensures: exit code 3 for any UNKNOWN proofs

- **Z3-107**: `--verbose` shows Z3 solver statistics

  **Contracts:**
  - Requires: --verbose flag with --proofs
  - Ensures: output includes solver time, memory, decisions

---

## Configuration

- **Z3-110**: Configure Z3 in pyproject.toml

  **Contracts:**
  - Requires: [tool.spec-test.z3] section exists
  - Ensures: Z3 settings loaded from configuration

  ```toml
  [tool.spec-test.z3]
  enabled = true
  timeout = 30
  cache_dir = ".spec-test/proofs"
  check_overflow = false
  integer_bits = 64
  ```

- **Z3-111**: Configure solver tactics

  **Contracts:**
  - Requires: tactics specified in config
  - Ensures: Z3 uses specified solver tactics

  ```toml
  [tool.spec-test.z3]
  tactics = ["simplify", "solve-eqs", "smt"]
  ```

- **Z3-112**: Configure proof parallelism

  **Contracts:**
  - Requires: parallel setting in config
  - Ensures: proofs run in parallel up to limit

  ```toml
  [tool.spec-test.z3]
  parallel = 4  # number of parallel proofs
  ```

- **Z3-113**: Disable Z3 for specific functions

  **Contracts:**
  - Requires: @provable(enabled=False) or config exclude list
  - Ensures: function skipped in Z3 verification

---

## Integration with Contracts

- **Z3-120**: Proven contracts can skip runtime checks

  **Contracts:**
  - Requires: proof status is PROVEN
  - Ensures: runtime checks skippable via configuration

- **Z3-121**: Track which contracts are proven vs runtime-only

  **Contracts:**
  - Requires: verification completes
  - Ensures: report distinguishes proven vs runtime contracts

- **Z3-122**: Warn when contract is too complex for Z3

  **Contracts:**
  - Requires: contract translation fails
  - Ensures: warning emitted with explanation

- **Z3-123**: Generate runtime fallback for unproven contracts

  **Contracts:**
  - Requires: proof status is UNKNOWN or SKIPPED
  - Ensures: runtime checks remain active

- **Z3-124**: Support mixed proven/runtime contracts on same function

  **Contracts:**
  - Requires: function has multiple contracts, some provable
  - Ensures: proven contracts skip runtime, others execute

---

## Error Handling

- **Z3-130**: Clear error when Z3 not installed

  **Contracts:**
  - Requires: z3-solver package not installed
  - Ensures: helpful error message with install instructions

- **Z3-131**: Graceful timeout handling

  **Contracts:**
  - Requires: Z3 solver times out
  - Ensures: returns UNKNOWN, does not crash

- **Z3-132**: Report unsupported Python features clearly

  **Contracts:**
  - Requires: function uses feature not translatable to Z3
  - Ensures: error lists specific unsupported feature

- **Z3-133**: Handle recursive functions with bounded unrolling

  **Contracts:**
  - Requires: function is recursive
  - Ensures: unroll to configurable depth, then assume correct

- **Z3-134**: Report when preconditions are unsatisfiable

  **Contracts:**
  - Requires: Z3 proves preconditions are contradictory
  - Ensures: warning that function can never be called validly

---

## Supported Python Subset

The following Python features are translatable to Z3:

**Supported:**
- Integer and float arithmetic
- Boolean logic
- Comparisons
- Conditional expressions (ternary)
- Simple if/else statements
- For loops over range()
- While loops with numeric conditions
- List indexing and slicing (with known bounds)
- len() on annotated sequences
- min(), max(), abs() builtins
- Type-annotated parameters

**Not Supported (returns SKIPPED):**
- Dynamic typing (no annotations)
- Arbitrary object attribute access
- Method calls (except builtins)
- String operations
- Dictionary operations (future)
- Set operations
- File I/O
- Exceptions (except for analysis)
- Generators and iterators
- Closures capturing mutable state
- Global variable mutation
- Class instance creation

---

## Example Usage

```python
from spec_test import contract, provable

@provable
@contract(
    requires=[lambda x: x >= 0],
    ensures=[lambda result: result >= 0]
)
def factorial(x: int) -> int:
    if x <= 1:
        return 1
    return x * factorial(x - 1)

# Z3 will prove:
# - For all x >= 0, factorial(x) >= 0
# - No integer overflow (if check_overflow=True)

@provable(timeout=60)
@contract(
    requires=[
        lambda items: len(items) > 0,
        lambda index: index >= 0
    ],
    ensures=[lambda result: result is not None]
)
def safe_get(items: List[int], index: int) -> Optional[int]:
    if index < len(items):
        return items[index]
    return None

# Z3 will attempt to prove:
# - index is always valid when accessing items[index]
# - result is not None given preconditions
# Note: This proof may fail, revealing the index < len check is needed
```

---

## Future Considerations

- **Z3-F01** [FUTURE]: Automatic invariant inference using Houdini algorithm
- **Z3-F02** [FUTURE]: Support for algebraic data types (dataclasses)
- **Z3-F03** [FUTURE]: Integration with hypothesis for hybrid testing/proving
- **Z3-F04** [FUTURE]: Proof certificates for external verification
- **Z3-F05** [FUTURE]: Support for quantified contracts (forall, exists)
- **Z3-F06** [FUTURE]: Modular verification with function summaries
