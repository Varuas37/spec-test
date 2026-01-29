# Migration Guide: spec-test v1 to v2

## Overview

This prompt guides you through migrating a project from spec-test v1 to v2.

## Breaking Changes in v2

### 1. Specs Directory Location

**v1**: Specs were in `docs/specs/spec-*.md`
**v2**: Specs are in `specs/*.md`

### 2. File Naming Convention

**v1**: Files had to be named `spec-*.md` (e.g., `spec-auth.md`)
**v2**: Any `.md` file in `specs/` is recognized (e.g., `auth.md`)

### 3. Collector Behavior

**v1**: Recursively searched `docs/specs/` for `spec-*.md` files
**v2**: Recursively searches `specs/` for all `.md` files

## New Features in v2

### 1. Runtime Contracts

New `@contract` decorator for precondition/postcondition checking:

```python
from spec_test import contract

@contract(
    spec_id="CART-001",
    pre=lambda items: len(items) > 0,
    post=lambda result: result >= 0
)
def calculate_total(items):
    return sum(item.price for item in items)
```

### 2. Coverage Analysis

New `--coverage` flag for code coverage reporting:

```bash
spec-test verify --coverage --coverage-threshold 80
```

### 3. Skip Tag

Mark specs as skipped with `[SKIP]` tag:

```markdown
- **FEAT-001** [SKIP]: Feature deferred to next release
```

### 4. Context Command

New command to output CLAUDE.md for AI agents:

```bash
spec-test context
```

### 5. AI Agent Skills

`spec-test init` now installs AI agent skills to `.claude/skills/`:
- `spec-feature.md` - Create new features with specs
- `spec-implement.md` - Implement code matching specs
- `spec-verify.md` - Run verification and fix issues
- `spec-review.md` - Review specifications

## Migration Steps

### Step 1: Move Specs Directory

```bash
# If you have docs/specs/, move it to specs/
mv docs/specs specs

# Or create specs/ and move files
mkdir -p specs
mv docs/specs/*.md specs/
```

### Step 2: Rename Spec Files (Optional)

You can optionally simplify file names:

```bash
# Example: spec-auth.md -> auth.md
cd specs
for f in spec-*.md; do
  mv "$f" "${f#spec-}"
done
```

### Step 3: Subdirectories (No Changes Needed)

v2 still searches subdirectories recursively within `specs/`, so no changes needed for nested specs.

### Step 4: Update CLAUDE.md

If you have a `CLAUDE.md`, update path references:

```markdown
# Change this:
1. **Specs live in** `docs/specs/*.md`

# To this:
1. **Specs live in** `specs/*.md`
```

### Step 5: Update CI/CD Pipelines

If your CI uses custom paths, update them:

```yaml
# Before (v1)
- spec-test verify --specs docs/specs

# After (v2)
- spec-test verify --specs specs
```

### Step 6: Re-initialize Skills (Optional)

To get the updated AI agent skills:

```bash
spec-test init
```

This will install updated skills to `.claude/skills/`.

### Step 7: Verify Migration

Run verification to ensure everything works:

```bash
spec-test verify
```

## Checklist

- [ ] Specs moved from `docs/specs/` to `specs/`
- [ ] Files renamed from `spec-*.md` to `*.md` (optional)
- [ ] CLAUDE.md updated with new paths
- [ ] CI/CD pipelines updated
- [ ] `spec-test verify` passes
