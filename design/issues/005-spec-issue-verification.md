# ISSUE-005: Spec-to-Issue Verification

## Summary
Add verification that each spec file links to a related issue, ensuring the "why" is always documented.

## Motivation
The issues-first workflow requires:
1. Write an issue (document why)
2. Write specs (document what)
3. Implement (document how)

Without enforcement, developers may skip step 1 and go straight to specs, losing valuable context about decisions and trade-offs.

## Detailed Description

### Spec File Format
Each spec file should have a "Related Issue" section:
```markdown
# Feature: Something

## Related Issue
- [ISSUE-001: Feature Name](../issues/001-feature.md)

## Requirements
- **FEAT-001**: ...
```

### Verification
The collector should:
1. Parse spec files for "Related Issue" section
2. Extract issue references
3. Optionally verify linked issue files exist

### CLI Integration
```bash
# Check specs have issues
spec-test verify --check-issues

# List specs missing issues
spec-test list-specs --show-issues
```

### Reporting
```
Specification Verification Report
=================================
FEAT-001  PASS   Feature description
  Issue: ISSUE-001 (../issues/001-feature.md)

FEAT-002  PASS   Another feature
  Issue: MISSING - No related issue found
```

## Options Considered

### Option A: Strict enforcement
**Pros**: Ensures all specs have issues
**Cons**: May be too strict for quick iterations

### Option B: Warning only (chosen)
**Pros**: Encourages best practice without blocking
**Cons**: Can be ignored

### Option C: Optional flag
**Pros**: Flexible - strict when needed
**Cons**: Easy to forget

## Decision
**Option B + C**: Warn by default, fail with `--require-issues` flag. This encourages the workflow without blocking development.

## Related Specs
- [spec-spec-test.md](../specs/spec-spec-test.md)
  - COL-005: Collector extracts related issue from spec files
  - COL-006: Collector validates issue file exists
  - CLI-007: List-specs shows issue status
  - REP-005: Reporter shows issue linkage

## Status
- [x] Issue written
- [ ] Specs defined
- [ ] Implementation complete
- [ ] Tests passing
