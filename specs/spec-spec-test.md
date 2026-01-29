# spec-test Specification

## Overview
spec-test is a tool for specification-driven development that links requirements to tests.

## Decorator Requirements

### @spec Decorator
- **DEC-001**: @spec decorator registers test in global registry
- **DEC-002**: @spec decorator adds pytest marker to test
- **DEC-003**: @spec decorator preserves function metadata
- **DEC-004**: @specs decorator supports multiple spec IDs
- **DEC-005**: @spec decorator preserves async function behavior
- **DEC-006**: @spec decorator works regardless of decorator order with pytest.mark.asyncio
- **DEC-007**: @specs decorator preserves async function behavior

## Collector Requirements

### Spec Parsing
- **COL-001**: Collector finds specs in all .md files with **ID**: format
- **COL-002**: Collector extracts verification type from [brackets]
- **COL-003**: Collector searches nested directories recursively within specs/
- **COL-004**: Collector skips files starting with underscore

## Runner Requirements

### Test Discovery
- **RUN-001**: Runner discovers @spec decorated methods inside test classes
- **RUN-002**: Runner generates correct pytest node ID for class-based tests

## Verifier Requirements

### Verification
- **VER-001**: Verifier matches specs to tests by ID
- **VER-002**: Verifier runs tests and captures pass/fail
- **VER-003**: Verifier reports missing tests as PENDING

## Reporter Requirements

### Output
- **REP-001**: Reporter prints colored terminal output
- **REP-002**: Reporter generates markdown file
- **REP-003**: Reporter shows coverage percentage
- **REP-004**: Reporter lists failures with details

## CLI Requirements

### Commands
- **CLI-001**: `verify` command runs full verification
- **CLI-002**: `list-specs` command shows all specs
- **CLI-003**: `check` command verifies single spec
- **CLI-004**: `init` command scaffolds project
- **CLI-005**: Exit code 1 on test failures
- **CLI-006**: Exit code 2 on missing tests (when --fail-on-missing)
