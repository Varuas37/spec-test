# ISSUE-006: Git Workflow Integration

## Summary

Add git pre-commit hook integration to automatically verify specs before allowing commits.

## Motivation

**Problem**: Developers can accidentally commit code with failing or missing tests, breaking the continuous verification workflow that spec-test promotes.

**Current State**: Users must manually remember to run `spec-test verify` before committing.

**Desired State**: Automatic verification enforced at commit time via git hooks.

## Detailed Description

Users should be able to opt-in to automated spec verification by running:
```bash
spec-test init --enable-git-workflow
```

This should install a git pre-commit hook that:
1. Runs `spec-test verify` before each commit
2. Blocks commits if verification fails (failing or missing tests)
3. Allows bypass with `git commit --no-verify` for emergencies
4. Provides clear error messages about what failed

## Pros

- **Enforcement**: Ensures specs are always verified before code enters version control
- **Catches mistakes early**: Prevents committing broken code
- **Team alignment**: All team members follow same verification workflow
- **CI/CD savings**: Fewer failed CI builds due to missing/failing tests
- **Opt-in**: Users choose when to enable strict enforcement
- **Emergency escape**: `--no-verify` available when needed

## Cons

- **Slower commits**: Adds verification time to every commit
- **Learning curve**: Developers need to understand the hook system
- **Hook conflicts**: May conflict with existing pre-commit hooks (mitigated by backup)
- **Not portable**: Hooks don't travel with the repo (by design)

## Trade-offs

**Chosen Approach**: Install git hook via `--enable-git-workflow` flag

**Alternatives Considered**:
1. **Always install hook**: Too aggressive, removes user choice
2. **Use pre-commit framework**: Extra dependency, adds complexity
3. **GitHub Actions only**: Doesn't catch issues locally, wastes CI time
4. **Manual documentation**: Already tried, users forget

## Related Specs

- [GIT-001](../specs/git-workflow.md)
- [GIT-002](../specs/git-workflow.md)
- [GIT-003](../specs/git-workflow.md)
- [GIT-004](../specs/git-workflow.md)
- [GIT-005](../specs/git-workflow.md)

## Status

- [x] Issue written
- [x] Specs defined
- [x] Implementation complete
- [ ] Tests passing
- [ ] Documentation updated
