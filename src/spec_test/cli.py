"""Command-line interface for spec-test."""

import subprocess
import sys
from importlib import resources
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from .collector import collect_specs
from .reporter import Reporter
from .verifier import SpecVerifier

app = typer.Typer(
    name="spec-test",
    help="Make AI-generated code trustworthy through mathematical verification",
)
console = Console()


@app.command()
def verify(
    specs_dir: Path = typer.Option(
        Path("docs/specs"),
        "--specs",
        "-s",
        help="Directory containing spec markdown files",
    ),
    tests_dir: Path = typer.Option(
        Path("tests"),
        "--tests",
        "-t",
        help="Directory containing test files",
    ),
    source_dir: Optional[Path] = typer.Option(
        None,
        "--source",
        help="Source directory for coverage (e.g., src/mypackage)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output markdown report to file",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
    fail_on_missing: bool = typer.Option(
        True,
        "--fail-on-missing/--no-fail-on-missing",
        help="Exit with error if specs are missing tests",
    ),
    coverage: bool = typer.Option(
        False,
        "--coverage",
        "-c",
        help="Run with code coverage analysis",
    ),
    coverage_threshold: int = typer.Option(
        80,
        "--coverage-threshold",
        help="Minimum coverage percentage required (default: 80)",
    ),
):
    """
    Verify all specifications have passing tests.

    Reads specs from markdown files, discovers @spec decorated tests,
    runs tests, and reports spec coverage. Optionally checks code coverage.
    """
    verifier = SpecVerifier(
        specs_dir=specs_dir,
        tests_dir=tests_dir,
    )

    report = verifier.verify(verbose=verbose)

    reporter = Reporter()
    reporter.print_terminal(report)

    # Run coverage analysis if requested
    coverage_percent = None
    if coverage:
        coverage_percent = _run_coverage(tests_dir, source_dir, verbose)

        if coverage_percent is not None:
            status = "[green]PASS[/green]" if coverage_percent >= coverage_threshold else "[red]FAIL[/red]"
            console.print(Panel(
                f"Code Coverage: {coverage_percent:.1f}% (threshold: {coverage_threshold}%) {status}",
                title="Coverage Report",
                border_style="blue",
            ))

    if output:
        reporter.generate_markdown(report, output)
        console.print(f"\n[green]Report saved to {output}[/green]")

    # Exit codes
    if report.failing > 0:
        raise typer.Exit(code=1)
    if fail_on_missing and report.missing > 0:
        raise typer.Exit(code=2)
    if coverage and coverage_percent is not None and coverage_percent < coverage_threshold:
        raise typer.Exit(code=3)


def _run_coverage(tests_dir: Path, source_dir: Optional[Path], verbose: bool) -> Optional[float]:
    """Run pytest with coverage and return coverage percentage."""
    cmd = [
        sys.executable, "-m", "pytest",
        str(tests_dir),
        "--cov-report=term-missing",
        "--cov-report=json:.coverage.json",
    ]

    if source_dir:
        cmd.append(f"--cov={source_dir}")
    else:
        # Try to auto-detect source directory
        for candidate in ["src", "."]:
            if Path(candidate).exists():
                cmd.append(f"--cov={candidate}")
                break

    if not verbose:
        cmd.append("-q")

    try:
        result = subprocess.run(cmd, capture_output=not verbose, text=True)

        # Parse coverage from JSON report
        import json
        coverage_file = Path(".coverage.json")
        if coverage_file.exists():
            with open(coverage_file) as f:
                data = json.load(f)
                return data.get("totals", {}).get("percent_covered", 0)
    except Exception as e:
        if verbose:
            console.print(f"[yellow]Coverage analysis failed: {e}[/yellow]")

    return None


@app.command()
def list_specs(
    specs_dir: Path = typer.Option(
        Path("docs/specs"),
        "--specs",
        "-s",
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


@app.command()
def context(
    path: Path = typer.Argument(
        Path("."),
        help="Project root to search for CLAUDE.md",
    ),
):
    """
    Output CLAUDE.md content for LLM context.

    Searches for CLAUDE.md in the project root and outputs its contents.
    Useful for providing spec-test workflow instructions to AI assistants.
    """
    claude_md = path / "CLAUDE.md"

    if not claude_md.exists():
        # Try to output a default CLAUDE.md template
        default_content = """# CLAUDE.md - Agent Instructions

## Specification-Driven Development

This project uses `spec-test` for specification-driven development. Every behavior must be backed by a passing test.

## Workflow

1. **Specs live in** `docs/specs/*.md`
2. **Tests use** `@spec("ID", "description")` decorator to link to specs
3. **Run** `spec-test verify` to check all specs have passing tests

## Spec Format

In markdown files, specs are defined as:
```
- **PREFIX-001**: Description of requirement
```

## Test Format

```python
from spec_test import spec

@spec("PREFIX-001", "Description")
def test_something():
    # Test implementation
    assert result == expected
```

## Commands

```bash
spec-test verify          # Check all specs have passing tests
spec-test list-specs      # List all specs
spec-test check PREFIX-001  # Check single spec
spec-test context         # Output this context for LLMs
```

## Rules

1. Never claim a feature works without a test
2. Every spec ID in docs/specs must have a corresponding `@spec` test
3. Run `spec-test verify` before committing - it must pass
4. If a spec has no test, write the test first
"""
        console.print(
            "[yellow]No CLAUDE.md found. Here's the default spec-test context:[/yellow]\n"
        )
        console.print(default_content)
        return

    content = claude_md.read_text()
    console.print(content)


def _install_skills(path: Path) -> list[str]:
    """Install AI agent skills from the package to the project.

    Returns list of installed skill filenames.
    """
    skills_dir = path / ".claude" / "skills"
    installed = []

    # Try to find skills in package first, then fall back to project root (dev mode)
    skills_sources = []

    try:
        # Try package location first
        skills_pkg = resources.files("spec_test") / "skills"
        if skills_pkg.is_dir():
            skills_sources.append(("package", skills_pkg))
    except (TypeError, AttributeError, FileNotFoundError):
        pass

    # Fall back to project root for development mode
    # __file__ is src/spec_test/cli.py, so .parent.parent.parent gets to project root
    dev_skills = Path(__file__).parent.parent.parent / "skills"
    if dev_skills.exists() and dev_skills.is_dir():
        skills_sources.append(("dev", dev_skills))

    if not skills_sources:
        return []

    skills_dir.mkdir(parents=True, exist_ok=True)

    # Use the first available source
    source_type, source_path = skills_sources[0]

    if source_type == "package":
        # Use importlib.resources traversable
        for skill_file in source_path.iterdir():
            if skill_file.is_file() and skill_file.name.endswith(".md"):
                dest = skills_dir / skill_file.name
                dest.write_text(skill_file.read_text())
                installed.append(skill_file.name)
    else:
        # Use regular Path for dev mode
        for skill_file in source_path.iterdir():
            if skill_file.is_file() and skill_file.name.endswith(".md"):
                dest = skills_dir / skill_file.name
                dest.write_text(skill_file.read_text())
                installed.append(skill_file.name)

    return sorted(installed)


@app.command()
def init(
    path: Path = typer.Argument(
        Path("."),
        help="Project root to initialize",
    ),
):
    """Initialize spec-test in a project."""
    # Create specs directory
    specs_dir = path / "docs" / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"Created {specs_dir}/")

    # Create example spec file (must match spec-*.md pattern)
    example_spec = specs_dir / "spec-example.md"
    if not example_spec.exists():
        example_spec.write_text("""# Example Specification

## Overview
This is an example specification file. Replace with your actual specs.
Spec files must be named spec-*.md to be discovered.

## Requirements

### Core Features
- **EXAMPLE-001**: The system should do something useful
- **EXAMPLE-002**: The system should handle errors gracefully
- **EXAMPLE-003** [manual]: Code follows project naming conventions
""")

    # Create CLAUDE.md with spec-test instructions
    claude_md = path / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text("""# CLAUDE.md - Agent Instructions

## Specification-Driven Development

This project uses `spec-test` for specification-driven development. Every behavior must be backed by a passing test.

## Workflow

1. **Specs live in** `docs/specs/*.md`
2. **Tests use** `@spec("ID", "description")` decorator to link to specs
3. **Run** `spec-test verify` to check all specs have passing tests

## Spec Format

In markdown files, specs are defined as:
```
- **PREFIX-001**: Description of requirement
```

## Test Format

```python
from spec_test import spec

@spec("PREFIX-001", "Description")
def test_something():
    # Test implementation
    assert result == expected
```

## Commands

```bash
spec-test verify          # Check all specs have passing tests
spec-test list-specs      # List all specs
spec-test check PREFIX-001  # Check single spec
spec-test context         # Output CLAUDE.md for LLM context
```

## Rules

1. Never claim a feature works without a test
2. Every spec ID in docs/specs must have a corresponding `@spec` test
3. Run `spec-test verify` before committing - it must pass
4. If a spec has no test, write the test first
""")
        console.print("Created CLAUDE.md")

    # Install AI agent skills
    installed_skills = _install_skills(path)
    if installed_skills:
        console.print("Installed AI agent skills to .claude/skills/")
        for skill in installed_skills:
            console.print(f"  - {skill}")

    console.print("\n[green]Ready! Run 'spec-test verify' to check your specs.[/green]")


if __name__ == "__main__":
    app()
