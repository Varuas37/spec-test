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
from .prover import (
    ProofResult,
    get_provable_registry,
    verify_function,
)
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
        Path("design/specs"),
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
    proofs: bool = typer.Option(
        False,
        "--proofs",
        "-p",
        help="Run Z3 formal proof verification on @provable functions",
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

    # Run formal proof verification if requested
    proof_failures = 0
    if proofs:
        proof_results = _run_proofs(verbose)
        proof_failures = proof_results.get("refuted", 0)

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
    if proofs and proof_failures > 0:
        raise typer.Exit(code=4)


def _run_proofs(verbose: bool) -> dict[str, int]:
    """Run Z3 formal proof verification on @provable functions.

    Returns dict with counts: proven, refuted, unknown, skipped
    """
    registry = get_provable_registry()

    if not registry:
        if verbose:
            console.print("[dim]No @provable functions registered[/dim]")
        return {"proven": 0, "refuted": 0, "unknown": 0, "skipped": 0}

    results = {"proven": 0, "refuted": 0, "unknown": 0, "skipped": 0}
    outcomes = []

    console.print(f"\n[bold]Running Z3 Proof Verification[/bold] ({len(registry)} functions)")
    console.print()

    for spec_id, info in registry.items():
        # Try to get the actual function to verify
        # We need to import the module and get the function
        try:
            import importlib
            module = importlib.import_module(info.func_module)
            func = getattr(module, info.func_name, None)

            if func is None:
                outcomes.append((spec_id, info.func_name, ProofResult.SKIPPED, "Function not found"))
                results["skipped"] += 1
                continue

            outcome = verify_function(func)
            outcomes.append((spec_id, info.func_name, outcome.result, outcome.message))

            key = outcome.result.value
            results[key] = results.get(key, 0) + 1

            # Show counter-example if refuted
            if outcome.result == ProofResult.REFUTED and outcome.counter_example:
                if verbose:
                    console.print(f"  Counter-example: {outcome.counter_example}")

        except Exception as e:
            outcomes.append((spec_id, info.func_name, ProofResult.SKIPPED, str(e)))
            results["skipped"] += 1

    # Display results
    for spec_id, func_name, result, message in outcomes:
        if result == ProofResult.PROVEN:
            status = "[green]✓ PROVEN[/green]"
        elif result == ProofResult.REFUTED:
            status = "[red]✗ REFUTED[/red]"
        elif result == ProofResult.UNKNOWN:
            status = "[yellow]? UNKNOWN[/yellow]"
        else:
            status = "[dim]○ SKIPPED[/dim]"

        console.print(f"  {status} {spec_id}: {func_name}")
        if verbose and message:
            console.print(f"    [dim]{message}[/dim]")

    # Summary panel
    total = sum(results.values())
    summary = f"Proven: {results['proven']} | Refuted: {results['refuted']} | Unknown: {results['unknown']} | Skipped: {results['skipped']}"

    if results["refuted"] > 0:
        border_style = "red"
    elif results["proven"] > 0 and results["unknown"] == 0:
        border_style = "green"
    else:
        border_style = "yellow"

    console.print(Panel(
        summary,
        title="Proof Verification Summary",
        border_style=border_style,
    ))

    return results


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
        Path("design/specs"),
        "--specs",
        "-s",
        help="Directory containing spec markdown files",
    ),
    show_issues: bool = typer.Option(
        False,
        "--show-issues",
        "-i",
        help="Show related issue status for each spec",
    ),
):
    """List all specifications found in spec files."""
    specs = collect_specs(specs_dir)

    if not specs:
        console.print("[yellow]No specifications found[/yellow]")
        raise typer.Exit(code=0)

    # Count specs with/without issues
    with_issues = sum(1 for s in specs if s.has_issue)
    without_issues = len(specs) - with_issues

    console.print(f"\n[bold]Found {len(specs)} specifications:[/bold]")
    if show_issues:
        issue_status = f"[green]{with_issues} with issues[/green]"
        if without_issues > 0:
            issue_status += f", [yellow]{without_issues} missing issues[/yellow]"
        console.print(f"  {issue_status}\n")
    else:
        console.print()

    for spec in sorted(specs, key=lambda s: s.id):
        console.print(f"  [cyan]{spec.id}[/cyan]: {spec.description}")
        console.print(f"    [dim]{spec.source_file}:{spec.source_line}[/dim]")

        if show_issues:
            if spec.has_issue:
                for issue in spec.related_issues:
                    exists = Path(issue.path).exists()
                    status = "[green]✓[/green]" if exists else "[red]✗ not found[/red]"
                    console.print(f"    Issue: {status} {issue.title}")
            else:
                console.print(f"    Issue: [yellow]⚠ No related issue[/yellow]")

    console.print()


@app.command()
def check(
    spec_id: str = typer.Argument(..., help="Spec ID to check (e.g., AUTH-001)"),
    specs_dir: Path = typer.Option(Path("design/specs"), "--specs", "-s"),
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

This project uses `spec-test` for specification-driven development.

## Workflow

1. **Issues** document intentions in `design/issues/`
2. **Specs** define requirements in `design/specs/`
3. **Tests** use `@spec("ID", "description")` decorator
4. **Run** `spec-test verify` to check all specs have passing tests

## Directory Structure

```
design/
  issues/    # Why - intentions, pros/cons, context
  specs/     # What - formal requirements
  prompts/   # How - AI agent instructions
```

## Spec Format

```markdown
- **PREFIX-001**: Description of requirement
```

## Test Format

```python
from spec_test import spec

@spec("PREFIX-001", "Description")
def test_something():
    assert result == expected
```

## Commands

```bash
spec-test verify          # Check all specs have passing tests
spec-test list-specs      # List all specs
spec-test check PREFIX-001  # Check single spec
```

## Rules

1. Write an issue before writing specs
2. Every spec must link to an issue
3. Every spec ID must have a corresponding `@spec` test
4. Run `spec-test verify` before committing
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
    # Create design directory structure
    design_dir = path / "design"
    specs_dir = design_dir / "specs"
    issues_dir = design_dir / "issues"
    prompts_dir = design_dir / "prompts"

    for d in [specs_dir, issues_dir, prompts_dir]:
        d.mkdir(parents=True, exist_ok=True)
    console.print(f"Created {design_dir}/ (specs/, issues/, prompts/)")

    # Create example spec file
    example_spec = specs_dir / "example.md"
    if not example_spec.exists():
        example_spec.write_text("""# Example Specification

## Overview
This is an example specification file. Replace with your actual specs.

## Related Issue
- [ISSUE-001](../issues/001-example.md)

## Requirements

### Core Features
- **EXAMPLE-001**: The system should do something useful
- **EXAMPLE-002**: The system should handle errors gracefully
- **EXAMPLE-003** [manual]: Code follows project naming conventions
""")

    # Create example issue file
    example_issue = issues_dir / "001-example.md"
    if not example_issue.exists():
        example_issue.write_text("""# ISSUE-001: Example Feature

## Summary
Brief description of what this feature/change is about.

## Motivation
Why are we doing this? What problem does it solve?

## Detailed Description
Full details of the intended behavior, edge cases, and considerations.

## Pros
- List benefits

## Cons
- List drawbacks or trade-offs

## Related Specs
- [EXAMPLE-001](../specs/example.md)
- [EXAMPLE-002](../specs/example.md)

## Status
- [ ] Issue written
- [ ] Specs defined
- [ ] Implementation complete
- [ ] Tests passing
""")

    # Create CLAUDE.md with spec-test instructions
    claude_md = path / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text("""# CLAUDE.md - Agent Instructions

## Specification-Driven Development

This project uses `spec-test` for specification-driven development.

## Workflow

1. **Issues** document intentions in `design/issues/`
2. **Specs** define requirements in `design/specs/`
3. **Tests** use `@spec("ID", "description")` decorator
4. **Run** `spec-test verify` to check all specs have passing tests

## Directory Structure

```
design/
  issues/    # Why - intentions, pros/cons, context
  specs/     # What - formal requirements
  prompts/   # How - AI agent instructions
```

## Spec Format

```markdown
- **PREFIX-001**: Description of requirement
```

## Test Format

```python
from spec_test import spec

@spec("PREFIX-001", "Description")
def test_something():
    assert result == expected
```

## Commands

```bash
spec-test verify          # Check all specs have passing tests
spec-test list-specs      # List all specs
spec-test check PREFIX-001  # Check single spec
```

## Rules

1. Write an issue before writing specs
2. Every spec must link to an issue
3. Every spec ID must have a corresponding `@spec` test
4. Run `spec-test verify` before committing
""")
        console.print("Created CLAUDE.md")

    # Install AI agent skills
    installed_skills = _install_skills(path)
    if installed_skills:
        console.print("\n[bold cyan]AI Agent Skills Installed[/bold cyan]")
        console.print("Installed skills to .claude/skills/:")
        for skill in installed_skills:
            console.print(f"  - {skill}")
        console.print("\n[yellow]To use these skills with Claude Code:[/yellow]")
        console.print("  Add them to your agent system by running:")
        console.print("  [dim]claude-code skills add .claude/skills/*.md[/dim]")
        console.print("  Then you can use them with: /spec-workflow, /spec-issue, etc.")

    console.print("\n[green]Ready! Run 'spec-test verify' to check your specs.[/green]")


if __name__ == "__main__":
    app()
