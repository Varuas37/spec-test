# Feature: Core Verification

spec-test links specifications to tests and verifies code meets requirements.

---

## Spec Collection

- **CORE-001**: Collect specs from specs/ directory

  **Contracts:**
  - Requires: specs/ directory exists
  - Ensures: returns list of all specs from .md files

- **CORE-002**: Parse spec ID format **PREFIX-NNN**

  **Contracts:**
  - Requires: file contains markdown
  - Ensures: extracts id, description, source file, line number

- **CORE-003**: Parse [SKIP] tag

  **Contracts:**
  - Requires: spec line exists
  - Ensures: spec.verification_type = SKIP when [SKIP] present

- **CORE-004**: Parse [manual] tag

  **Contracts:**
  - Requires: spec line exists
  - Ensures: spec.verification_type = MANUAL when [manual] present

---

## Test Linking

- **CORE-010**: @spec decorator links test to spec ID

  **Contracts:**
  - Requires: spec_id is valid format, description is string
  - Ensures: test registered in global registry with spec_id as key

- **CORE-011**: @specs decorator supports multiple IDs

  **Contracts:**
  - Requires: all spec_ids are valid format
  - Ensures: test registered for each spec_id

---

## Verification

- **CORE-020**: Match specs to tests by ID

  **Contracts:**
  - Requires: specs collected, tests discovered
  - Ensures: each spec linked to its test (if exists)

- **CORE-021**: Run tests and capture results

  **Contracts:**
  - Requires: test exists for spec
  - Ensures: status is PASSING or FAILING based on test result

- **CORE-022**: Report missing tests as PENDING

  **Contracts:**
  - Requires: spec exists
  - Ensures: status is PENDING when no test found

- **CORE-023**: Skip verification for [SKIP] specs

  **Contracts:**
  - Requires: spec has [SKIP] tag
  - Ensures: status is SKIPPED, no test required

---

## CLI

- **CORE-030**: verify command runs full verification

  **Contracts:**
  - Requires: specs/ directory exists
  - Ensures: reports pass/fail/pending for each spec, exit code reflects status

- **CORE-031**: list-specs command shows all specs

  **Contracts:**
  - Requires: specs/ directory exists
  - Ensures: lists spec ID, description, source location

- **CORE-032**: check command verifies single spec

  **Contracts:**
  - Requires: spec_id provided, spec exists
  - Ensures: reports status for that spec only
