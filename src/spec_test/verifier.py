"""Main verification logic."""

from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .collector import collect_specs
from .runner import discover_spec_tests, run_test
from .types import (
    SpecRequirement,
    SpecResult,
    SpecStatus,
    SpecTest,
    VerificationReport,
    VerificationType,
)


class SpecVerifier:
    """Main class for verifying specifications against tests."""

    def __init__(
        self,
        specs_dir: str | Path = "specs",
        tests_dir: str | Path = "tests",
        project_root: Optional[Path] = None,
    ):
        self.specs_dir = Path(specs_dir)
        self.tests_dir = Path(tests_dir)
        self.project_root = project_root or Path.cwd()
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
        spec_tests: dict[str, SpecTest],
        verbose: bool,
    ) -> SpecResult:
        """Verify a single specification."""

        # Handle SKIP verification type
        if spec.verification_type == VerificationType.SKIP:
            return SpecResult(
                spec=spec,
                status=SpecStatus.SKIPPED,
                error_message="Skipped",
            )

        # Handle manual verification type
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

    def verify_single(self, spec_id: str) -> Optional[SpecResult]:
        """Verify a single spec by ID."""
        specs = collect_specs(self.specs_dir)
        spec = next((s for s in specs if s.id == spec_id), None)

        if not spec:
            return None

        spec_tests = discover_spec_tests(self.tests_dir)
        return self._verify_spec(spec, spec_tests, verbose=True)
