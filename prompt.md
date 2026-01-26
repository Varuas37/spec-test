# Prompt 1: spec-test Tool & Development Patterns Setup

## Context

You are setting up the foundational development infrastructure for a multi-repository project. This includes:

1. A reusable **spec-test** Python tool for specification-driven development
2. A **CLAUDE.md** file that defines development patterns and agent coordination

## Philosophy

**Every claim about system behavior must be backed by a passing test.**

- If there's no test, the behavior is unverified and untrusted
- Specs are written first, then implementation, then tests
- The verify script is the source of truth for project health
- Some specs may require AI-assisted verification (non-code behaviors)

---

## Part 1: spec-test Tool

Create a standalone, pip-installable Python tool called `spec-test`.

### Repository Structure

```
spec-test/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── spec_test/
│       ├── __init__.py
│       ├── decorators.py      # @spec decorator
│       ├── collector.py       # Collect specs from markdown
│       ├── runner.py          # Run tests and collect results
│       ├── verifier.py        # Main verification logic
│       ├── reporter.py        # Generate reports (markdown, terminal)
│       ├── ai_verifier.py     # AI-assisted verification for non-code specs
│       ├── pytest_plugin.py   # pytest plugin for --spec-verify flag
│       ├── cli.py             # CLI entry point
│       └── types.py           # Type definitions
├── tests/
│   ├── conftest.py
│   ├── test_decorators.py
│   ├── test_collector.py
│   ├── test_verifier.py
│   └── test_reporter.py
└── docs/
    └── specs/
        └── spec-test.md       # Dogfooding: spec-test's own specs
```

### pyproject.toml

```toml
[project]
name = "spec-test"
version = "0.1.0"
description = "Specification-driven development tool with test verification"
authors = [{ name = "Pulse Team" }]
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = [
    "pytest>=8.0.0",
    "rich>=13.0.0",
    "typer>=0.9.0",
    "pydantic>=2.0.0",
    "anthropic>=0.40.0",  # For AI-assisted verification
]

[project.optional-dependencies]
dev = [
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

[project.scripts]
spec-test = "spec_test.cli:app"

[project.entry-points.pytest11]
spec_test = "spec_test.pytest_plugin"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/spec_test"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
```

### Core Implementation

#### src/spec_test/types.py

```python
"""Type definitions for spec-test."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path


class SpecStatus(Enum):
    """Status of a specification requirement."""
    PENDING = "pending"          # No test written yet
    PASSING = "passing"          # Test exists and passes
    FAILING = "failing"          # Test exists but fails
    AI_VERIFIED = "ai_verified"  # Verified by AI agent (non-code)
    AI_FAILED = "ai_failed"      # AI verification failed
    SKIPPED = "skipped"          # Explicitly skipped


class VerificationType(Enum):
    """How a spec should be verified."""
    TEST = "test"                # Standard pytest test
    AI_REVIEW = "ai_review"      # AI reviews code/output
    MANUAL = "manual"            # Requires human verification


@dataclass
class SpecRequirement:
    """A single specification requirement parsed from markdown."""
    id: str
    description: str
    source_file: Path
    source_line: int
    verification_type: VerificationType = VerificationType.TEST
    ai_verification_prompt: Optional[str] = None
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class SpecTest:
    """A test linked to a specification."""
    spec_id: str
    description: str
    test_path: str          # module::function format
    test_file: Path
    test_line: int


@dataclass
class SpecResult:
    """Result of verifying a single spec."""
    spec: SpecRequirement
    status: SpecStatus
    test: Optional[SpecTest] = None
    error_message: Optional[str] = None
    ai_reasoning: Optional[str] = None  # For AI-verified specs


@dataclass
class VerificationReport:
    """Complete verification report."""
    results: list[SpecResult]
    total_specs: int = 0
    passing: int = 0
    failing: int = 0
    missing: int = 0
    ai_verified: int = 0
    
    def __post_init__(self):
        self.total_specs = len(self.results)
        self.passing = sum(1 for r in self.results if r.status == SpecStatus.PASSING)
        self.failing = sum(1 for r in self.results if r.status == SpecStatus.FAILING)
        self.missing = sum(1 for r in self.results if r.status == SpecStatus.PENDING)
        self.ai_verified = sum(1 for r in self.results if r.status == SpecStatus.AI_VERIFIED)
    
    @property
    def coverage_percent(self) -> float:
        if self.total_specs == 0:
            return 100.0
        verified = self.passing + self.ai_verified
        return (verified / self.total_specs) * 100
    
    @property
    def is_passing(self) -> bool:
        return self.failing == 0 and self.missing == 0
```

#### src/spec_test/decorators.py

```python
"""Decorators for linking tests to specifications."""

import functools
from typing import Callable, Optional
import pytest

# Global registry: spec_id -> list of test paths
_spec_registry: dict[str, list[dict]] = {}


def spec(
    spec_id: str,
    description: str,
    verification_notes: Optional[str] = None,
):
    """
    Decorator that links a test function to a specification requirement.
    
    Args:
        spec_id: Unique identifier matching the spec doc (e.g., "AUTH-001")
        description: Brief description of what this test verifies
        verification_notes: Optional notes about how this test verifies the spec
    
    Usage:
        @spec("AUTH-001", "User can create API token")
        def test_create_token_returns_valid_jwt():
            ...
        
        @spec("AUTH-002", "Token expires after TTL", 
              verification_notes="Uses time mocking to verify expiration")
        def test_token_expiry():
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Register this test
        if spec_id not in _spec_registry:
            _spec_registry[spec_id] = []
        
        _spec_registry[spec_id].append({
            "test_path": f"{func.__module__}::{func.__qualname__}",
            "description": description,
            "notes": verification_notes,
        })
        
        # Attach metadata to function
        func._spec_id = spec_id
        func._spec_description = description
        func._spec_notes = verification_notes
        
        # Add pytest marker for filtering: pytest -m "spec"
        marked = pytest.mark.spec(func)
        marked = pytest.mark.spec_id(spec_id)(marked)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Preserve spec metadata on wrapper
        wrapper._spec_id = spec_id
        wrapper._spec_description = description
        wrapper._spec_notes = verification_notes
        
        return wrapper
    
    return decorator


def get_spec_registry() -> dict[str, list[dict]]:
    """Get all registered spec -> test mappings."""
    return _spec_registry.copy()


def clear_registry():
    """Clear the registry (useful for testing)."""
    _spec_registry.clear()


def specs(*spec_ids: str):
    """
    Decorator for tests that verify multiple specs.
    
    Usage:
        @specs("AUTH-001", "AUTH-002")
        def test_token_creation_and_validation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        for spec_id in spec_ids:
            if spec_id not in _spec_registry:
                _spec_registry[spec_id] = []
            _spec_registry[spec_id].append({
                "test_path": f"{func.__module__}::{func.__qualname__}",
                "description": f"Multi-spec test covering {', '.join(spec_ids)}",
                "notes": None,
            })
        
        func._spec_ids = spec_ids
        
        # Add markers
        marked = pytest.mark.spec(func)
        for sid in spec_ids:
            marked = pytest.mark.spec_id(sid)(marked)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper._spec_ids = spec_ids
        return wrapper
    
    return decorator
```

#### src/spec_test/collector.py

```python
"""Collect specifications from markdown files."""

import re
from pathlib import Path
from typing import Iterator

from .types import SpecRequirement, VerificationType


# Pattern: **SPEC-001**: Description
# Or: - **SPEC-001**: Description  
# Or with verification type: **SPEC-001** [ai_review]: Description
SPEC_PATTERN = re.compile(
    r'\*\*([A-Z]+-\d+)\*\*'           # **SPEC-001**
    r'(?:\s*\[(\w+)\])?'              # Optional [verification_type]
    r':\s*(.+?)$',                     # : Description
    re.MULTILINE
)

# AI verification prompt in following line: <!-- ai: prompt here -->
AI_PROMPT_PATTERN = re.compile(r'<!--\s*ai:\s*(.+?)\s*-->')


def collect_specs(specs_dir: str | Path) -> list[SpecRequirement]:
    """
    Collect all specification requirements from markdown files.
    
    Args:
        specs_dir: Directory containing .md spec files
        
    Returns:
        List of SpecRequirement objects
    """
    specs_path = Path(specs_dir)
    if not specs_path.exists():
        return []
    
    specs = []
    for md_file in specs_path.glob("**/*.md"):
        specs.extend(_parse_spec_file(md_file))
    
    return specs


def _parse_spec_file(file_path: Path) -> Iterator[SpecRequirement]:
    """Parse a single markdown file for spec requirements."""
    content = file_path.read_text()
    lines = content.split('\n')
    
    for line_num, line in enumerate(lines, 1):
        match = SPEC_PATTERN.search(line)
        if not match:
            continue
        
        spec_id = match.group(1)
        verification_type_str = match.group(2)
        description = match.group(3).strip()
        
        # Determine verification type
        if verification_type_str:
            try:
                verification_type = VerificationType(verification_type_str.lower())
            except ValueError:
                verification_type = VerificationType.TEST
        else:
            verification_type = VerificationType.TEST
        
        # Check for AI prompt on next line
        ai_prompt = None
        if verification_type == VerificationType.AI_REVIEW and line_num < len(lines):
            next_line = lines[line_num]  # line_num is 1-indexed, so this gets next
            prompt_match = AI_PROMPT_PATTERN.search(next_line)
            if prompt_match:
                ai_prompt = prompt_match.group(1)
        
        yield SpecRequirement(
            id=spec_id,
            description=description,
            source_file=file_path,
            source_line=line_num,
            verification_type=verification_type,
            ai_verification_prompt=ai_prompt,
        )


def collect_spec_ids(specs_dir: str | Path) -> set[str]:
    """Collect just the spec IDs (for quick lookups)."""
    return {spec.id for spec in collect_specs(specs_dir)}
```

#### src/spec_test/runner.py

```python
"""Run tests and collect results."""

import subprocess
import json
import sys
from pathlib import Path
from typing import Optional

from .types import SpecTest
from .decorators import get_spec_registry


def discover_spec_tests(tests_dir: str | Path) -> dict[str, SpecTest]:
    """
    Discover all tests decorated with @spec.
    
    Returns:
        Dict mapping spec_id -> SpecTest
    """
    # Import all test modules to populate the registry
    tests_path = Path(tests_dir)
    if not tests_path.exists():
        return {}
    
    # Use pytest to collect tests
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            str(tests_path),
            "--collect-only", "-q",
            "--no-header",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    
    # Now get from registry (populated by imports during collection)
    # This is a bit hacky - we need a better approach
    # For now, we'll parse test files directly
    return _discover_from_files(tests_path)


def _discover_from_files(tests_dir: Path) -> dict[str, SpecTest]:
    """Parse test files to find @spec decorators."""
    import ast
    
    spec_tests: dict[str, SpecTest] = {}
    
    for py_file in tests_dir.glob("**/*.py"):
        if py_file.name.startswith("__"):
            continue
            
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue
        
        module_name = _get_module_name(py_file, tests_dir)
        
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            
            spec_info = _extract_spec_decorator(node)
            if spec_info:
                spec_id, description = spec_info
                test_path = f"{module_name}::{node.name}"
                
                spec_tests[spec_id] = SpecTest(
                    spec_id=spec_id,
                    description=description,
                    test_path=test_path,
                    test_file=py_file,
                    test_line=node.lineno,
                )
    
    return spec_tests


def _get_module_name(file_path: Path, base_dir: Path) -> str:
    """Convert file path to module name."""
    relative = file_path.relative_to(base_dir.parent)
    return str(relative.with_suffix("")).replace("/", ".").replace("\\", ".")


def _extract_spec_decorator(node: ast.FunctionDef) -> Optional[tuple[str, str]]:
    """Extract @spec decorator info from a function node."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            func = decorator.func
            if isinstance(func, ast.Name) and func.id == "spec":
                args = decorator.args
                if len(args) >= 2:
                    spec_id = _get_string_value(args[0])
                    description = _get_string_value(args[1])
                    if spec_id and description:
                        return (spec_id, description)
    return None


def _get_string_value(node: ast.expr) -> Optional[str]:
    """Extract string value from AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def run_test(test_path: str, tests_dir: Path) -> tuple[bool, Optional[str]]:
    """
    Run a specific test and return pass/fail status.
    
    Returns:
        Tuple of (passed: bool, error_message: Optional[str])
    """
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            test_path,
            "-v",
            "--tb=short",
            "--no-header",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    
    passed = result.returncode == 0
    error_message = None if passed else result.stdout + result.stderr
    
    return passed, error_message


def run_tests_by_spec_id(spec_id: str, tests_dir: Path) -> tuple[bool, Optional[str]]:
    """Run all tests for a given spec ID."""
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            str(tests_dir),
            "-v",
            "-m", f"spec_id({spec_id})",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    
    passed = result.returncode == 0
    error_message = None if passed else result.stdout + result.stderr
    
    return passed, error_message
```

#### src/spec_test/ai_verifier.py

```python
"""AI-assisted verification for non-code specifications."""

import os
from pathlib import Path
from typing import Optional

from anthropic import Anthropic

from .types import SpecRequirement, SpecStatus


class AIVerifier:
    """
    Verifies specifications that can't be tested with code.
    
    Examples:
    - Code follows naming conventions
    - Documentation exists and is accurate
    - Architecture patterns are followed
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key) if self.api_key else None
    
    def verify(
        self,
        spec: SpecRequirement,
        project_root: Path,
        context_files: Optional[list[Path]] = None,
    ) -> tuple[SpecStatus, str]:
        """
        Use AI to verify a specification.
        
        Args:
            spec: The specification to verify
            project_root: Root directory of the project
            context_files: Optional list of files to include as context
            
        Returns:
            Tuple of (status, reasoning)
        """
        if not self.client:
            return SpecStatus.PENDING, "No API key configured for AI verification"
        
        # Build context from files
        context = self._build_context(project_root, context_files)
        
        # Build verification prompt
        prompt = self._build_prompt(spec, context)
        
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            
            result_text = response.content[0].text
            
            # Parse response for pass/fail
            passed, reasoning = self._parse_response(result_text)
            
            status = SpecStatus.AI_VERIFIED if passed else SpecStatus.AI_FAILED
            return status, reasoning
            
        except Exception as e:
            return SpecStatus.PENDING, f"AI verification error: {str(e)}"
    
    def _build_context(
        self, 
        project_root: Path, 
        context_files: Optional[list[Path]]
    ) -> str:
        """Build context string from project files."""
        context_parts = []
        
        if context_files:
            for file_path in context_files:
                full_path = project_root / file_path
                if full_path.exists():
                    content = full_path.read_text()
                    context_parts.append(f"### {file_path}\n```\n{content}\n```")
        
        return "\n\n".join(context_parts)
    
    def _build_prompt(self, spec: SpecRequirement, context: str) -> str:
        """Build the verification prompt."""
        custom_prompt = spec.ai_verification_prompt or ""
        
        return f"""You are verifying a software specification requirement.

## Specification
- **ID**: {spec.id}
- **Description**: {spec.description}
- **Source**: {spec.source_file}:{spec.source_line}

## Verification Instructions
{custom_prompt if custom_prompt else "Verify that the codebase satisfies this specification."}

## Project Context
{context if context else "No specific files provided. Base your assessment on the specification description."}

## Your Task
1. Analyze whether the specification is satisfied
2. Provide clear reasoning
3. Give a final verdict

Respond in this format:
VERDICT: PASS or FAIL
REASONING: Your detailed explanation
"""
    
    def _parse_response(self, response: str) -> tuple[bool, str]:
        """Parse AI response into pass/fail and reasoning."""
        lines = response.strip().split('\n')
        
        passed = False
        reasoning = response
        
        for line in lines:
            if line.startswith("VERDICT:"):
                verdict = line.replace("VERDICT:", "").strip().upper()
                passed = verdict == "PASS"
            elif line.startswith("REASONING:"):
                reasoning = line.replace("REASONING:", "").strip()
                # Get rest of response as reasoning
                idx = response.find("REASONING:")
                if idx != -1:
                    reasoning = response[idx + len("REASONING:"):].strip()
        
        return passed, reasoning
```

#### src/spec_test/verifier.py

```python
"""Main verification logic."""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .types import (
    SpecRequirement, 
    SpecResult, 
    SpecStatus, 
    VerificationReport,
    VerificationType,
)
from .collector import collect_specs
from .runner import discover_spec_tests, run_test
from .ai_verifier import AIVerifier


class SpecVerifier:
    """Main class for verifying specifications against tests."""
    
    def __init__(
        self,
        specs_dir: str | Path = "docs/specs",
        tests_dir: str | Path = "tests",
        project_root: Optional[Path] = None,
        ai_verify: bool = True,
    ):
        self.specs_dir = Path(specs_dir)
        self.tests_dir = Path(tests_dir)
        self.project_root = project_root or Path.cwd()
        self.ai_verify = ai_verify
        self.ai_verifier = AIVerifier() if ai_verify else None
        self.console = Console()
    
    def verify(self, verbose: bool = False) -> VerificationReport:
        """
        Run full verification of all specs.
        
        Returns:
            VerificationReport with all results
        """
        # Collect specs from markdown
        specs = collect_specs(self.specs_dir)
        
        if not specs:
            self.console.print("[yellow]No specifications found[/yellow]")
            return VerificationReport(results=[])
        
        # Discover tests
        spec_tests = discover_spec_tests(self.tests_dir)
        
        results: list[SpecResult] = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task("Verifying specs...", total=len(specs))
            
            for spec in specs:
                result = self._verify_spec(spec, spec_tests, verbose)
                results.append(result)
                progress.advance(task)
        
        return VerificationReport(results=results)
    
    def _verify_spec(
        self,
        spec: SpecRequirement,
        spec_tests: dict[str, "SpecTest"],
        verbose: bool,
    ) -> SpecResult:
        """Verify a single specification."""
        
        # Handle different verification types
        if spec.verification_type == VerificationType.AI_REVIEW:
            return self._verify_with_ai(spec, verbose)
        
        if spec.verification_type == VerificationType.MANUAL:
            return SpecResult(
                spec=spec,
                status=SpecStatus.SKIPPED,
                error_message="Manual verification required",
            )
        
        # Standard test verification
        if spec.id not in spec_tests:
            return SpecResult(
                spec=spec,
                status=SpecStatus.PENDING,
                error_message=f"No test found for {spec.id}",
            )
        
        test = spec_tests[spec.id]
        passed, error = run_test(test.test_path, self.tests_dir)
        
        return SpecResult(
            spec=spec,
            status=SpecStatus.PASSING if passed else SpecStatus.FAILING,
            test=test,
            error_message=error,
        )
    
    def _verify_with_ai(self, spec: SpecRequirement, verbose: bool) -> SpecResult:
        """Verify a spec using AI."""
        if not self.ai_verifier:
            return SpecResult(
                spec=spec,
                status=SpecStatus.PENDING,
                error_message="AI verification disabled",
            )
        
        status, reasoning = self.ai_verifier.verify(spec, self.project_root)
        
        return SpecResult(
            spec=spec,
            status=status,
            ai_reasoning=reasoning,
        )
    
    def verify_single(self, spec_id: str) -> Optional[SpecResult]:
        """Verify a single spec by ID."""
        specs = collect_specs(self.specs_dir)
        spec = next((s for s in specs if s.id == spec_id), None)
        
        if not spec:
            return None
        
        spec_tests = discover_spec_tests(self.tests_dir)
        return self._verify_spec(spec, spec_tests, verbose=True)
```

#### src/spec_test/reporter.py

```python
"""Generate verification reports."""

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .types import VerificationReport, SpecResult, SpecStatus


class Reporter:
    """Generate and display verification reports."""
    
    def __init__(self):
        self.console = Console()
    
    def print_terminal(self, report: VerificationReport):
        """Print report to terminal with rich formatting."""
        
        # Header
        self.console.print()
        self.console.print(Panel.fit(
            "[bold]Specification Verification Report[/bold]",
            border_style="blue",
        ))
        self.console.print()
        
        # Results table
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
        table.add_column("Spec ID", style="cyan")
        table.add_column("Description")
        table.add_column("Status", justify="center")
        table.add_column("Test / Notes")
        
        for result in report.results:
            status_str = self._status_emoji(result.status)
            test_info = self._get_test_info(result)
            
            table.add_row(
                result.spec.id,
                result.spec.description[:50] + "..." if len(result.spec.description) > 50 else result.spec.description,
                status_str,
                test_info,
            )
        
        self.console.print(table)
        self.console.print()
        
        # Summary
        self._print_summary(report)
        
        # Failures detail
        if report.failing > 0 or report.missing > 0:
            self._print_failures(report)
    
    def _status_emoji(self, status: SpecStatus) -> str:
        """Convert status to emoji string."""
        return {
            SpecStatus.PASSING: "[green]✅ Pass[/green]",
            SpecStatus.FAILING: "[red]❌ Fail[/red]",
            SpecStatus.PENDING: "[yellow]⏳ No Test[/yellow]",
            SpecStatus.AI_VERIFIED: "[blue]🤖 AI Pass[/blue]",
            SpecStatus.AI_FAILED: "[red]🤖 AI Fail[/red]",
            SpecStatus.SKIPPED: "[dim]⏭️ Skip[/dim]",
        }.get(status, "❓")
    
    def _get_test_info(self, result: SpecResult) -> str:
        """Get test path or status notes."""
        if result.test:
            return f"[dim]{result.test.test_path}[/dim]"
        if result.ai_reasoning:
            return f"[dim]{result.ai_reasoning[:40]}...[/dim]"
        if result.error_message:
            return f"[dim]{result.error_message[:40]}[/dim]"
        return "-"
    
    def _print_summary(self, report: VerificationReport):
        """Print summary statistics."""
        total = report.total_specs
        
        summary = f"""[bold]Summary[/bold]
        
  Total Specs:     {total}
  [green]Passing:[/green]        {report.passing}
  [red]Failing:[/red]        {report.failing}
  [yellow]Missing Tests:[/yellow] {report.missing}
  [blue]AI Verified:[/blue]   {report.ai_verified}
  
  [bold]Coverage:[/bold]       {report.coverage_percent:.1f}%
"""
        self.console.print(Panel(summary, title="Results", border_style="blue"))
    
    def _print_failures(self, report: VerificationReport):
        """Print details about failures."""
        self.console.print()
        self.console.print("[bold red]Issues Found:[/bold red]")
        self.console.print()
        
        for result in report.results:
            if result.status == SpecStatus.PENDING:
                self.console.print(f"  [yellow]⚠️  {result.spec.id}[/yellow]: No test")
                self.console.print(f"      [dim]{result.spec.source_file}:{result.spec.source_line}[/dim]")
            elif result.status == SpecStatus.FAILING:
                self.console.print(f"  [red]❌ {result.spec.id}[/red]: Test failing")
                if result.test:
                    self.console.print(f"      [dim]{result.test.test_path}[/dim]")
    
    def generate_markdown(self, report: VerificationReport, output: Path):
        """Generate markdown report file."""
        lines = [
            "# Specification Status Report",
            "",
            f"*Generated: {datetime.now().isoformat()}*",
            "",
            f"**Coverage: {report.coverage_percent:.1f}%** | "
            f"✅ {report.passing} | ❌ {report.failing} | ⏳ {report.missing} | 🤖 {report.ai_verified}",
            "",
            "## Results",
            "",
            "| Spec ID | Description | Status | Test |",
            "|---------|-------------|--------|------|",
        ]
        
        for result in report.results:
            status = {
                SpecStatus.PASSING: "✅ Pass",
                SpecStatus.FAILING: "❌ Fail",
                SpecStatus.PENDING: "⏳ No Test",
                SpecStatus.AI_VERIFIED: "🤖 AI Pass",
                SpecStatus.AI_FAILED: "🤖 AI Fail",
                SpecStatus.SKIPPED: "⏭️ Skip",
            }.get(result.status, "❓")
            
            test_path = result.test.test_path if result.test else "-"
            desc = result.spec.description.replace("|", "\\|")
            
            lines.append(f"| {result.spec.id} | {desc} | {status} | `{test_path}` |")
        
        output.write_text("\n".join(lines))
```

#### src/spec_test/cli.py

```python
"""Command-line interface for spec-test."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .verifier import SpecVerifier
from .reporter import Reporter
from .collector import collect_specs

app = typer.Typer(
    name="spec-test",
    help="Specification-driven development tool with test verification",
)
console = Console()


@app.command()
def verify(
    specs_dir: Path = typer.Option(
        Path("docs/specs"),
        "--specs", "-s",
        help="Directory containing spec markdown files",
    ),
    tests_dir: Path = typer.Option(
        Path("tests"),
        "--tests", "-t", 
        help="Directory containing test files",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output markdown report to file",
    ),
    no_ai: bool = typer.Option(
        False,
        "--no-ai",
        help="Disable AI-assisted verification",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Verbose output",
    ),
    fail_on_missing: bool = typer.Option(
        True,
        "--fail-on-missing/--no-fail-on-missing",
        help="Exit with error if specs are missing tests",
    ),
):
    """
    Verify all specifications have passing tests.
    
    Reads specs from markdown files, discovers @spec decorated tests,
    and reports coverage.
    """
    verifier = SpecVerifier(
        specs_dir=specs_dir,
        tests_dir=tests_dir,
        ai_verify=not no_ai,
    )
    
    report = verifier.verify(verbose=verbose)
    
    reporter = Reporter()
    reporter.print_terminal(report)
    
    if output:
        reporter.generate_markdown(report, output)
        console.print(f"\n[green]Report saved to {output}[/green]")
    
    # Exit code
    if report.failing > 0:
        raise typer.Exit(code=1)
    if fail_on_missing and report.missing > 0:
        raise typer.Exit(code=2)


@app.command()
def list_specs(
    specs_dir: Path = typer.Option(
        Path("docs/specs"),
        "--specs", "-s",
        help="Directory containing spec markdown files",
    ),
):
    """List all specifications found in spec files."""
    specs = collect_specs(specs_dir)
    
    if not specs:
        console.print("[yellow]No specifications found[/yellow]")
        raise typer.Exit(code=0)
    
    console.print(f"\n[bold]Found {len(specs)} specifications:[/bold]\n")
    
    for spec in sorted(specs, key=lambda s: s.id):
        console.print(f"  [cyan]{spec.id}[/cyan]: {spec.description}")
        console.print(f"    [dim]{spec.source_file}:{spec.source_line}[/dim]")
    console.print()


@app.command()
def check(
    spec_id: str = typer.Argument(..., help="Spec ID to check (e.g., AUTH-001)"),
    specs_dir: Path = typer.Option(Path("docs/specs"), "--specs", "-s"),
    tests_dir: Path = typer.Option(Path("tests"), "--tests", "-t"),
):
    """Check a single specification."""
    verifier = SpecVerifier(specs_dir=specs_dir, tests_dir=tests_dir)
    result = verifier.verify_single(spec_id)
    
    if not result:
        console.print(f"[red]Spec {spec_id} not found[/red]")
        raise typer.Exit(code=1)
    
    reporter = Reporter()
    status_str = reporter._status_emoji(result.status)
    
    console.print(f"\n{status_str} [bold]{result.spec.id}[/bold]: {result.spec.description}")
    
    if result.test:
        console.print(f"  Test: [dim]{result.test.test_path}[/dim]")
    if result.error_message:
        console.print(f"  [red]{result.error_message}[/red]")
    if result.ai_reasoning:
        console.print(f"  AI: [dim]{result.ai_reasoning}[/dim]")


@app.command()
def init(
    path: Path = typer.Argument(
        Path("."),
        help="Project root to initialize",
    ),
):
    """Initialize spec-test in a project."""
    specs_dir = path / "docs" / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    
    # Create example spec file
    example_spec = specs_dir / "example.md"
    if not example_spec.exists():
        example_spec.write_text("""# Example Specification

## Overview
This is an example specification file. Replace with your actual specs.

## Requirements

### Core Features
- **EXAMPLE-001**: The system should do something useful
- **EXAMPLE-002**: The system should handle errors gracefully
- **EXAMPLE-003** [ai_review]: Code follows project naming conventions
  <!-- ai: Check that all functions use snake_case naming -->
""")
    
    console.print(f"[green]✅ Initialized spec-test in {path}[/green]")
    console.print(f"   Created: {specs_dir}")
    console.print(f"\nNext steps:")
    console.print(f"  1. Edit {example_spec}")
    console.print(f"  2. Write tests with @spec decorator")
    console.print(f"  3. Run: spec-test verify")


if __name__ == "__main__":
    app()
```

#### src/spec_test/__init__.py

```python
"""spec-test: Specification-driven development with test verification."""

from .decorators import spec, specs, get_spec_registry
from .types import (
    SpecStatus,
    SpecRequirement,
    SpecTest,
    SpecResult,
    VerificationReport,
    VerificationType,
)
from .verifier import SpecVerifier
from .reporter import Reporter

__version__ = "0.1.0"

__all__ = [
    # Decorators
    "spec",
    "specs",
    "get_spec_registry",
    # Types
    "SpecStatus",
    "SpecRequirement", 
    "SpecTest",
    "SpecResult",
    "VerificationReport",
    "VerificationType",
    # Classes
    "SpecVerifier",
    "Reporter",
]
```

### Dogfooding: spec-test's Own Specs

Create `docs/specs/spec-test.md`:

```markdown
# spec-test Specification

## Overview
spec-test is a tool for specification-driven development that links requirements to tests.

## Decorator Requirements

### @spec Decorator
- **DEC-001**: @spec decorator registers test in global registry
- **DEC-002**: @spec decorator adds pytest marker to test
- **DEC-003**: @spec decorator preserves function metadata
- **DEC-004**: @specs decorator supports multiple spec IDs

## Collector Requirements

### Spec Parsing
- **COL-001**: Collector finds specs in markdown files with **ID**: format
- **COL-002**: Collector extracts verification type from [brackets]
- **COL-003**: Collector extracts AI prompts from HTML comments
- **COL-004**: Collector handles nested directories

## Verifier Requirements

### Verification
- **VER-001**: Verifier matches specs to tests by ID
- **VER-002**: Verifier runs tests and captures pass/fail
- **VER-003**: Verifier reports missing tests as PENDING
- **VER-004**: Verifier calls AI for ai_review type specs

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
```

---

## Part 2: CLAUDE.md Development Patterns

Create a `CLAUDE.md` file that defines how agents should work on this project.

### CLAUDE.md

```markdown
# CLAUDE.md - Development Patterns & Agent Coordination

## Overview

This document defines development patterns and agent coordination for the Pulse project ecosystem. All AI agents working on this codebase must follow these guidelines.

## Core Philosophy

### Specification-Driven Development

**Every behavior claim must be backed by a test.**

1. **Spec First**: Before implementing any feature, the spec must exist in `docs/specs/`
2. **Implement**: Write code to satisfy the spec
3. **Test**: Write `@spec` decorated tests that verify each requirement
4. **Verify**: Run `spec-test verify` - must pass before committing
5. **Iterate**: If tests fail, fix code; if specs missing tests, write tests

### The Trust Hierarchy

```
Verified (test passes)     → Trusted behavior
Spec exists, no test       → Unverified claim  
No spec                    → Undocumented (might break)
```

---

## Agent Coordination

### Multi-Agent Workflow

For complex tasks, spin up specialized agents:

```
┌─────────────────────────────────────────────────────────┐
│  ORCHESTRATOR AGENT                                     │
│  - Reads task requirements                              │
│  - Breaks into subtasks                                 │
│  - Assigns to specialized agents                        │
│  - Validates outputs                                    │
└─────────────────────────────────────────────────────────┘
        │
        ├── SPEC AGENT
        │   - Writes/updates specs in docs/specs/
        │   - Ensures all requirements have IDs
        │   - Reviews spec coverage
        │
        ├── IMPLEMENTATION AGENT  
        │   - Writes production code
        │   - Follows clean architecture
        │   - No tests (separate concern)
        │
        ├── TEST AGENT
        │   - Writes @spec decorated tests
        │   - Ensures each spec ID has a test
        │   - Runs tests and fixes failures
        │
        └── REVIEW AGENT
            - Runs spec-test verify
            - Checks code quality
            - Validates architecture patterns
```

### Agent Communication Protocol

Agents communicate via structured task files:

```yaml
# .tasks/current.yaml
task_id: TASK-001
status: in_progress
assigned_to: implementation_agent

spec_ids:
  - AUTH-001
  - AUTH-002
  - AUTH-003

subtasks:
  - id: write_spec
    agent: spec_agent
    status: complete
    
  - id: implement
    agent: implementation_agent  
    status: in_progress
    
  - id: write_tests
    agent: test_agent
    status: pending
    depends_on: implement
    
  - id: verify
    agent: review_agent
    status: pending
    depends_on: write_tests
```

---

## Code Standards

### Clean Architecture Layers

```
src/
├── domain/           # Business entities, no dependencies
├── application/      # Use cases, depends on domain
├── infrastructure/   # External concerns, implements interfaces
└── api/              # HTTP layer, depends on application
```

**Rules:**
- Domain layer has ZERO external imports (no FastAPI, no SQLAlchemy)
- Application layer depends only on domain
- Infrastructure implements interfaces defined in domain/application
- API layer is thin - just routing to use cases

### File Naming

```python
# Entities: singular noun
user.py           # Contains User class

# Repositories: _repository suffix
user_repository.py          # Interface
pg_user_repository.py       # Postgres implementation

# Use cases: verb phrase
authenticate_user.py
create_token.py

# Tests: test_ prefix, mirrors source structure
tests/domain/test_user.py
tests/application/test_authenticate_user.py
```

### Test Structure

```python
"""
Tests for user authentication.

Specs covered:
- AUTH-001: Token creation
- AUTH-002: Token validation
"""
from spec_test import spec

class TestTokenCreation:
    """Tests for creating auth tokens."""
    
    @spec("AUTH-001", "User can create API token")
    def test_create_token_returns_valid_jwt(self):
        """
        Given a valid user
        When they request a token
        Then they receive a valid JWT
        """
        # Arrange
        user = User(id=uuid4(), email="test@example.com")
        
        # Act
        token = create_token(user)
        
        # Assert
        assert token is not None
        decoded = decode_token(token)
        assert decoded["user_id"] == str(user.id)
    
    @spec("AUTH-002", "Token expires after configured TTL")
    def test_token_has_expiration(self):
        ...
```

---

## Spec Writing Guidelines

### Spec File Format

```markdown
# Feature Name Specification

## Overview
Brief description of the feature.

## Requirements

### Category 1
- **PREFIX-001**: Clear, testable requirement
- **PREFIX-002**: Another requirement
- **PREFIX-003** [ai_review]: Non-code requirement
  <!-- ai: Instructions for AI verification -->

### Category 2  
- **PREFIX-010**: Requirements can skip numbers for grouping
```

### Spec ID Conventions

| Prefix | Domain |
|--------|--------|
| AUTH-  | Authentication |
| USER-  | User management |
| PLUG-  | Plugin system |
| DB-    | Database operations |
| API-   | API endpoints |
| SDK-   | SDK functionality |

### Good vs Bad Specs

```markdown
# ❌ Bad - vague, untestable
- **AUTH-001**: Authentication should work well

# ✅ Good - specific, testable
- **AUTH-001**: POST /auth/token with valid credentials returns 200 and JWT

# ❌ Bad - implementation detail
- **AUTH-002**: Use bcrypt for password hashing

# ✅ Good - behavior-focused  
- **AUTH-002**: Passwords are stored securely and cannot be retrieved in plaintext

# ❌ Bad - multiple behaviors
- **AUTH-003**: Users can login, logout, and reset passwords

# ✅ Good - single behavior
- **AUTH-003**: Users can login with email and password
- **AUTH-004**: Users can logout and invalidate their token
- **AUTH-005**: Users can request password reset via email
```

---

## Pre-Commit Checklist

Before committing, agents must verify:

```bash
# 1. All specs have tests
spec-test verify

# 2. All tests pass
pytest

# 3. Type checking passes
mypy src/

# 4. Linting passes
ruff check src/

# 5. Format is correct
ruff format --check src/
```

---

## Project-Specific Patterns

### Repository Pattern

```python
# domain/repositories/user_repository.py
from abc import ABC, abstractmethod
from typing import Optional
from ..entities.user import User

class IUserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]: ...
    
    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]: ...
    
    @abstractmethod
    async def save(self, user: User) -> User: ...

# infrastructure/repositories/pg_user_repository.py
class PgUserRepository(IUserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        # Implementation
        ...
```

### Use Case Pattern

```python
# application/use_cases/authenticate_user.py
from dataclasses import dataclass
from ..interfaces.password_hasher import IPasswordHasher
from ...domain.repositories.user_repository import IUserRepository

@dataclass
class AuthenticateUserInput:
    email: str
    password: str

@dataclass
class AuthenticateUserOutput:
    user_id: UUID
    token: str

class AuthenticateUserUseCase:
    def __init__(
        self,
        user_repo: IUserRepository,
        hasher: IPasswordHasher,
        token_service: ITokenService,
    ):
        self.user_repo = user_repo
        self.hasher = hasher
        self.token_service = token_service
    
    async def execute(self, input: AuthenticateUserInput) -> AuthenticateUserOutput:
        user = await self.user_repo.get_by_email(input.email)
        if not user:
            raise AuthenticationError("Invalid credentials")
        
        if not self.hasher.verify(input.password, user.password_hash):
            raise AuthenticationError("Invalid credentials")
        
        token = self.token_service.create(user)
        
        return AuthenticateUserOutput(user_id=user.id, token=token)
```

### Dependency Injection

```python
# infrastructure/container.py
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    
    # Database
    db_session = providers.Resource(
        create_session,
        url=config.database.url,
    )
    
    # Repositories
    user_repository = providers.Factory(
        PgUserRepository,
        session=db_session,
    )
    
    # Use cases
    authenticate_user = providers.Factory(
        AuthenticateUserUseCase,
        user_repo=user_repository,
        hasher=password_hasher,
        token_service=token_service,
    )
```

---

## Troubleshooting

### Common Issues

**"Spec XXX has no test"**
- Ensure test has `@spec("XXX", "description")` decorator
- Check test file is in `tests/` directory
- Verify test function name starts with `test_`

**"AI verification failed"**
- Check ANTHROPIC_API_KEY is set
- Review the AI prompt in spec file
- Add more context files for AI to review

**"Test passes but spec-test says failing"**
- Run `pytest` directly to see actual error
- Check spec ID matches exactly (case-sensitive)

---

## Quick Reference

```bash
# Initialize spec-test in project
spec-test init

# List all specs
spec-test list-specs

# Verify all specs
spec-test verify

# Check single spec
spec-test check AUTH-001

# Generate markdown report
spec-test verify --output docs/SPEC_STATUS.md

# Skip AI verification
spec-test verify --no-ai
```
```

---

## Execution Instructions

1. **Create the spec-test repository**
   ```bash
   mkdir spec-test && cd spec-test
   git init
   uv init
   ```

2. **Implement all files** as specified above

3. **Write tests for spec-test itself** (dogfooding)
   - Create tests in `tests/` with `@spec` decorators
   - Each spec in `docs/specs/spec-test.md` needs a test

4. **Verify spec-test works**
   ```bash
   uv run spec-test verify
   ```

5. **Publish to PyPI** (optional, for external use)
   ```bash
   uv build
   uv publish
   ```

---

## Success Criteria

The task is complete when:

1. ✅ All files created as specified
2. ✅ `uv run pytest` passes
3. ✅ `uv run spec-test verify` shows 100% coverage
4. ✅ `uv run spec-test init` works in a new directory
5. ✅ CLAUDE.md is comprehensive and clear
6. ✅ README.md documents usage for other developers

## Verification

Run these commands to verify completion:

```bash
cd spec-test

# Install dependencies
uv sync

# Run tests
uv run pytest -v

# Verify specs
uv run spec-test verify

# Check CLI works
uv run spec-test --help
uv run spec-test list-specs
```
