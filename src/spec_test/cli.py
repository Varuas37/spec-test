"""Command-line interface for spec-test."""

import json
import shutil
import stat
import subprocess
import sys
from importlib import import_module, resources
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from . import __version__
from .collector import collect_specs
from .evidence import Evidence, load_evidence, write_evidence
from .prover import (
    ProofResult,
    Z3_AVAILABLE,
    get_provable_registry,
    verify_function,
)
from .reporter import Reporter
from . import repo_plan
from .types import SpecStatus, VerificationType
from .verifier import SpecVerifier

app = typer.Typer(
    name="spec-test",
    help="Make AI-generated code trustworthy through mathematical verification",
)
console = Console()


def version_callback(value: bool):
    """Display version and exit."""
    if value:
        console.print(f"spec-test version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
):
    """spec-test: Make AI-generated code trustworthy through mathematical verification."""
    pass


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
    proof_module: Optional[list[str]] = typer.Option(
        None, "--proof-module", help="Import a trusted module containing proofs (repeatable)"
    ),
    fail_on_unknown: bool = typer.Option(
        False, "--fail-on-unknown", help="Fail if any requested proof is unknown or skipped"
    ),
    receipts: Optional[list[Path]] = typer.Option(
        None, "--evidence", help="Load a trusted native runner receipt (repeatable)"
    ),
    evidence_output: Optional[Path] = typer.Option(
        None, "--evidence-output", help="Write all observed checks as JSON"
    ),
    require_issues: bool = typer.Option(
        False, "--require-issues", "--check-issues", help="Require valid local issue links"
    ),
):
    """
    Verify all specifications have passing tests.

    Reads specs from markdown files, discovers @spec decorated tests,
    runs tests, and reports spec coverage. Optionally checks code coverage.
    """
    if not proofs and (proof_module or fail_on_unknown):
        raise typer.BadParameter("Proof options require --proofs")
    if proofs:
        if not Z3_AVAILABLE:
            console.print("Z3 is not installed. Install with: pip install 'spec-test[z3]'")
            raise typer.Exit(code=4)
        for module_name in proof_module or []:
            try:
                import_module(module_name)
            except Exception as exc:
                console.print(f"Cannot import proof module {module_name}: {exc}", markup=False)
                raise typer.Exit(code=4) from exc
        if not get_provable_registry():
            console.print("No proofs registered. Use --proof-module with an importable module.")
            raise typer.Exit(code=4)

    verifier = SpecVerifier(
        specs_dir=specs_dir,
        tests_dir=tests_dir,
    )

    try:
        external = [check for path in receipts or [] for check in load_evidence(path)]
        proof_checks = _run_proofs(verbose) if proofs else []
        report = verifier.verify(verbose=verbose, evidence=tuple(external + proof_checks))
        known = {result.spec.id for result in report.results}
        unknown_ids = sorted({check.spec_id for check in external} - known)
        if unknown_ids:
            raise ValueError(f"Evidence references undefined specifications: {', '.join(unknown_ids)}")
        if evidence_output:
            write_evidence(evidence_output, report.evidence)
    except (OSError, ValueError) as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(code=5) from exc

    bad_links = {}
    for result in report.results:
        spec = result.spec
        if not spec.related_issues or any(not issue.exists for issue in spec.related_issues):
            bad_links.setdefault(str(spec.source_file), []).append(spec.id)
    for file, ids in sorted(bad_links.items()):
        console.print(
            f"Missing or broken Related Issue link in {file}: {', '.join(ids)}",
            markup=False,
        )

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

    proof_failures = any(
        check.status == "failed"
        or (fail_on_unknown and check.status in {"unknown", "skipped"})
        for check in proof_checks
    )

    if output:
        reporter.generate_markdown(report, output)
        console.print(f"\n[green]Report saved to {output}[/green]")

    # Exit codes
    if require_issues and (bad_links or not report.results):
        raise typer.Exit(code=5)
    if proof_failures:
        raise typer.Exit(code=4)
    if report.failing > 0:
        raise typer.Exit(code=1)
    if fail_on_missing and (report.missing or report.unknown):
        raise typer.Exit(code=2)
    if coverage and (coverage_percent is None or coverage_percent < coverage_threshold):
        raise typer.Exit(code=3)


def _run_proofs(verbose: bool) -> list[Evidence]:
    """Run Z3 formal proof verification on @provable functions.

    Returns typed receipts for the combined report.
    """
    registry = get_provable_registry()

    if not registry:
        if verbose:
            console.print("[dim]No @provable functions registered[/dim]")
        return []

    results = {"proven": 0, "refuted": 0, "unknown": 0, "skipped": 0}
    outcomes = []
    checks = []

    console.print(f"\n[bold]Running Z3 Proof Verification[/bold] ({len(registry)} functions)")
    console.print()

    result_status = {
        ProofResult.PROVEN: "passed",
        ProofResult.REFUTED: "failed",
        ProofResult.UNKNOWN: "unknown",
        ProofResult.SKIPPED: "skipped",
    }
    for spec_id, info in registry.items():
        witness = None
        try:
            if info.function is None:
                result, message = ProofResult.SKIPPED, "Function not found"
            else:
                outcome = verify_function(info.function)
                result, message = outcome.result, outcome.message
                witness = outcome.counter_example
        except Exception as exc:
            result, message = ProofResult.SKIPPED, str(exc)
        outcomes.append((spec_id, info.func_name, result, message))
        results[result.value] += 1
        checks.append(Evidence(
            spec_id, "implementation-proof", "z3-python", info.full_name,
            result_status[result], {"message": message, "counterexample": witness},
        ))
        if result == ProofResult.REFUTED and witness is not None:
            console.print(f"  Counter-example: {witness}", markup=False)

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
        if message and (verbose or result != ProofResult.PROVEN):
            console.print(f"    {message}", markup=False, style="dim")

    # Summary panel
    summary = f"Proven: {results['proven']} | Refuted: {results['refuted']} | Unknown: {results['unknown']} | Skipped: {results['skipped']}"

    if results["refuted"] > 0:
        border_style = "red"
    elif results["proven"] > 0 and results["unknown"] == 0 and results["skipped"] == 0:
        border_style = "green"
    else:
        border_style = "yellow"

    console.print(Panel(
        summary,
        title="Proof Verification Summary",
        border_style=border_style,
    ))

    return checks


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
    with_issues = sum(
        1 for s in specs if s.has_issue and all(issue.exists for issue in s.related_issues)
    )
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
                    exists = issue.exists
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
    if result.status in {SpecStatus.FAILING, SpecStatus.PENDING, SpecStatus.UNKNOWN}:
        raise typer.Exit(code=1)


@app.command("review-packet")
def review_packet(
    specs_dir: Path = typer.Option(Path("design/specs"), "--specs", "-s"),
    output: Path = typer.Option(..., "--output", "-o"),
):
    """Export manual/AI-assisted review inputs without calling an external service."""
    packet = []
    for requirement in collect_specs(specs_dir):
        if requirement.verification_type is not VerificationType.MANUAL:
            continue
        packet.append({
            "spec_id": requirement.id,
            "requirement": requirement.description,
            "source": str(requirement.source_file),
            "line": requirement.source_line,
            "issue_titles": [issue.title for issue in requirement.related_issues],
            "review_hint": requirement.review_notes,
            "status": "needs-human-review",
        })
    output.write_text(
        json.dumps({"schema_version": 1, "items": packet}, indent=2) + "\n",
        encoding="utf-8",
    )
    console.print(f"Prepared {len(packet)} unverified review items.")


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

    # Fall back to src/spec_test/skills for development mode
    # __file__ is src/spec_test/cli.py
    dev_skills = Path(__file__).parent / "skills"
    if dev_skills.exists() and dev_skills.is_dir():
        skills_sources.append(("dev", dev_skills))

    if not skills_sources:
        return []

    skills_dir.mkdir(parents=True, exist_ok=True)

    # Use the first available source
    source_type, source_path = skills_sources[0]

    if source_type == "package":
        # Use importlib.resources traversable
        for skill_item in source_path.iterdir():
            # Copy skill directories (each contains SKILL.md)
            if skill_item.is_dir() and skill_item.name.startswith("spec-"):
                dest_dir = skills_dir / skill_item.name
                dest_dir.mkdir(exist_ok=True)

                # Copy SKILL.md from the skill directory
                skill_file = skill_item / "SKILL.md"
                if skill_file.exists():
                    dest_file = dest_dir / "SKILL.md"
                    dest_file.write_text(skill_file.read_text())
                    installed.append(skill_item.name)
    else:
        # Use regular Path for dev mode
        for skill_item in source_path.iterdir():
            # Copy skill directories (each contains SKILL.md)
            if skill_item.is_dir() and skill_item.name.startswith("spec-"):
                dest_dir = skills_dir / skill_item.name
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                shutil.copytree(skill_item, dest_dir)
                installed.append(skill_item.name)

    return sorted(installed)


def _setup_git_hooks(path: Path) -> bool:
    """Set up git pre-commit hook to run spec-test verify.

    Returns True if successful, False otherwise.
    """
    git_dir = path / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        console.print("[yellow]Warning: .git directory not found. Initialize git first.[/yellow]")
        return False

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    pre_commit_hook = hooks_dir / "pre-commit"

    # Check if hook already exists
    if pre_commit_hook.exists():
        console.print(f"[yellow]Warning: {pre_commit_hook} already exists.[/yellow]")
        console.print("Backing up existing hook to pre-commit.backup")
        backup_path = hooks_dir / "pre-commit.backup"
        shutil.copy(pre_commit_hook, backup_path)

    # Create pre-commit hook script
    hook_script = """#!/bin/sh
# spec-test verification hook
# Prevents commits when specs are failing or missing tests

echo "Running spec-test verification..."

# Use the installed CLI, or a Python interpreter that can import it.
if command -v spec-test >/dev/null 2>&1; then
    set -- spec-test
else
    if command -v python3 >/dev/null 2>&1; then
        PYTHON=python3
    elif command -v python >/dev/null 2>&1; then
        PYTHON=python
    else
        echo "❌ Cannot find spec-test or python. Install spec-test first."
        exit 1
    fi
    if ! "$PYTHON" -c 'import importlib.util, sys; sys.exit(importlib.util.find_spec("spec_test") is None)'; then
        echo "❌ spec-test is not installed for $PYTHON. Install with: $PYTHON -m pip install spec-test"
        exit 1
    fi
    set -- "$PYTHON" -m spec_test.cli
fi

"$@" verify
verification_status=$?

if [ "$verification_status" -ne 0 ]; then
    echo ""
    echo "❌ Commit blocked: spec-test verification failed"
    echo "   - Fix failing tests"
    echo "   - Add missing tests"
    echo "   - Or skip with: git commit --no-verify"
    exit "$verification_status"
fi

echo "✅ All specs verified"
exit 0
"""

    pre_commit_hook.write_text(hook_script)

    # Make hook executable
    pre_commit_hook.chmod(pre_commit_hook.stat().st_mode | stat.S_IEXEC)

    return True


@app.command()
def init(
    path: Path = typer.Argument(
        Path("."),
        help="Project root to initialize",
    ),
    enable_git_workflow: bool = typer.Option(
        False,
        "--enable-git-workflow",
        help="Set up git pre-commit hook to run spec-test verify",
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
- **EXAMPLE-001**: A starter requirement with passing evidence is reported as passing.
- **EXAMPLE-002**: A starter requirement without evidence is reported as missing and verification exits nonzero.
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
        console.print("  [dim]claude-code skills add .claude/skills/*[/dim]")
        console.print("  Then you can use them with: /spec-workflow, /spec-issue, etc.")

    # Set up git workflow if requested
    if enable_git_workflow:
        console.print()
        if _setup_git_hooks(path):
            console.print("[bold green]✓ Git pre-commit hook installed[/bold green]")
            console.print("  Specs will be verified before each commit")
            console.print("  Skip verification with: [dim]git commit --no-verify[/dim]")
        else:
            console.print("[yellow]Git workflow setup skipped[/yellow]")

    console.print("\n[green]Ready! Run 'spec-test verify' to check your specs.[/green]")


@app.command()
def plan(
    root: Path = typer.Option(Path("."), "--root", help="Repository or project directory"),
    write_config: bool = typer.Option(False, "--write-config", help="Save detected checks without overwriting"),
) -> None:
    """Detect native checks or read spec-test.toml, without running commands."""
    try:
        result = repo_plan.discover(root)
        if write_config:
            repo_plan.write_config(root, result)
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(result.as_dict(), indent=2))


@app.command("run-checks")
def run_checks(
    root: Path = typer.Option(Path("."), "--root", help="Repository or project directory"),
    trust_repo: bool = typer.Option(False, "--trust-repo", help="Authorize execution of repository code"),
) -> None:
    """Run planned native checks in a trusted checkout; does not satisfy spec IDs by itself."""
    if not trust_repo:
        typer.echo("Review spec-test plan, then use --trust-repo to run repository code.", err=True)
        raise typer.Exit(2)
    try:
        root = root.resolve(strict=True)
        result = repo_plan.discover(root)
        for note in result.notes:
            typer.echo(note, err=True)
        if not result.checks:
            raise ValueError("No runnable checks in this project")
        status = repo_plan.run_checks(root, result)
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    if status:
        raise typer.Exit(status)


if __name__ == "__main__":
    app()
