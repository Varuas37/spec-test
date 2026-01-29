# Migration Guide: spec-test v1 to v2

## Overview

This prompt guides you through migrating a project from spec-test v1 to v2.

## Breaking Changes in v2

### 1. Directory Structure

**v1**: Specs in `docs/specs/spec-*.md` or `specs/*.md`
**v2**: Design artifacts in `design/` directory:
```
design/
  issues/    # Why - intentions, pros/cons, context
  specs/     # What - formal requirements
  prompts/   # How - AI agent instructions
```

### 2. File Naming Convention

**v1**: Files had to be named `spec-*.md`
**v2**: Any `.md` file in `design/specs/` is recognized

### 3. Workflow

**v1**: Specs → Tests
**v2**: Issues → Specs → Tests (issues document intentions first)

## New Features in v2

### 1. Runtime Contracts

`@contract` decorator with requires/ensures/invariants:

```python
from spec_test import contract

@contract(
    spec="CART-001",
    requires=[lambda items: len(items) > 0],
    ensures=[lambda result: result >= 0],
    invariants=[lambda items: all(i.price > 0 for i in items)],
)
def calculate_total(items):
    return sum(item.price for item in items)
```

### 2. Old State Capture

Compare pre/post state in postconditions:

```python
@contract(
    capture_old=True,
    ensures=[lambda result, old: len(result) == len(old.items) + 1],
)
def append_item(items, item):
    return items + [item]
```

### 3. Coverage Analysis

```bash
spec-test verify --coverage --coverage-threshold 80
```

### 4. Skip Tag

```markdown
- **FEAT-001** [SKIP]: Feature deferred to next release
```

## Migration Steps

### Step 1: Create Design Directory Structure

```bash
mkdir -p design/issues design/specs design/prompts
```

### Step 2: Move Specs

```bash
# From docs/specs/
mv docs/specs/*.md design/specs/

# Or from specs/
mv specs/*.md design/specs/
```

### Step 3: Rename Spec Files (Optional)

```bash
cd design/specs
for f in spec-*.md; do
  mv "$f" "${f#spec-}"
done
```

### Step 4: Create Issues for Existing Specs

For each spec file, create a corresponding issue in `design/issues/` documenting:
- Why the feature exists
- Pros and cons considered
- Related context

### Step 5: Update CLAUDE.md

```markdown
## Workflow

1. **Issues** document intentions in `design/issues/`
2. **Specs** define requirements in `design/specs/`
3. **Tests** use `@spec("ID", "description")` decorator
4. **Run** `spec-test verify` to check all specs have passing tests
```

### Step 6: Update CI/CD Pipelines

```yaml
# Before
- spec-test verify --specs docs/specs

# After
- spec-test verify --specs design/specs
```

### Step 7: Re-initialize (Optional)

```bash
spec-test init
```

### Step 8: Verify Migration

```bash
spec-test verify
```

## Checklist

- [ ] Created `design/` directory structure
- [ ] Moved specs to `design/specs/`
- [ ] Created issues in `design/issues/`
- [ ] Updated CLAUDE.md
- [ ] Updated CI/CD pipelines
- [ ] `spec-test verify` passes
