# Git Workflow Integration

## Overview

Automated spec verification via git pre-commit hooks to enforce testing standards before code enters version control.

## Related Issue

- [ISSUE-006: Git Workflow Integration](../issues/006-git-workflow-integration.md)

## Requirements

### Command-Line Interface

- **GIT-001**: `init --enable-git-workflow` flag installs pre-commit hook
- **GIT-002**: Hook installation backs up existing pre-commit hook to pre-commit.backup
- **GIT-003**: Hook installation makes pre-commit executable (chmod +x)
- **GIT-004**: Hook installation warns when .git directory not found
- **GIT-005**: Hook installation succeeds when .git directory exists

### Hook Behavior

- **GIT-010**: Pre-commit hook runs `spec-test verify` before commit
- **GIT-011**: Pre-commit hook blocks commit when specs fail
- **GIT-012**: Pre-commit hook blocks commit when tests missing
- **GIT-013**: Pre-commit hook allows commit when all specs pass
- **GIT-014**: Pre-commit hook can be bypassed with --no-verify
- **GIT-015**: Pre-commit hook auto-detects spec-test command in PATH
- **GIT-016**: Pre-commit hook falls back to python -m spec_test.cli
- **GIT-017**: Pre-commit hook shows clear error message on verification failure
- **GIT-018**: Pre-commit hook shows success message when verification passes

### Edge Cases

- **GIT-020**: Hook handles spec-test not installed gracefully
- **GIT-021**: Hook handles python not available gracefully
- **GIT-022**: Hook preserves exit code from spec-test verify
- **GIT-023**: Hook works in both git bash and zsh environments
- **GIT-024**: Hook message instructs user how to fix or bypass

### User Experience

- **GIT-030**: CLI shows confirmation when hook installed
- **GIT-031**: CLI shows skip message when git not initialized
- **GIT-032**: CLI shows backup confirmation when overwriting existing hook
- **GIT-033**: CLI help text documents --enable-git-workflow flag
