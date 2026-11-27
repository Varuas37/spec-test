"""Reconcile actual runner evidence with written specifications."""

from pathlib import Path
from typing import Optional

from rich.console import Console

from .collector import collect_specs
from .evidence import Evidence, require_unique
from .runner import discover_spec_test_groups, run_test_receipts
from .types import SpecRequirement, SpecResult, SpecStatus, VerificationReport, VerificationType


class SpecVerifier:
    """Verify each requirement using its declared kind of evidence."""

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

    def verify(self, verbose: bool = False, evidence: tuple[Evidence, ...] = ()) -> VerificationReport:
        specs = collect_specs(self.specs_dir)
        if not specs:
            self.console.print("[yellow]No specifications found[/yellow]")
        return self._verify(specs, evidence)

    def _verify(self, specs: list[SpecRequirement], evidence: tuple[Evidence, ...]):
        groups = discover_spec_test_groups(self.tests_dir)
        eligible = {
            spec.id
            for spec in specs
            if spec.verification_type not in {VerificationType.SKIP, VerificationType.MANUAL}
        }
        outcomes = run_test_receipts([test.test_path for id in eligible for test in groups.get(id, [])])
        checks = list(evidence)
        for id in sorted(eligible):
            for test in groups.get(id, []):
                status, details = outcomes[test.test_path]
                checks.append(Evidence(id, test.evidence_kind, "pytest", test.test_path, status, details))
        require_unique(checks)
        by_id: dict[str, list[Evidence]] = {}
        for check in checks:
            by_id.setdefault(check.spec_id, []).append(check)

        results = []
        for spec in specs:
            all_checks = by_id.get(spec.id, [])
            required = [c for c in all_checks if c.kind == spec.verification_type.value]
            test = next(iter(groups.get(spec.id, [])), None)
            if spec.verification_type == VerificationType.SKIP:
                status, reason = SpecStatus.SKIPPED, "Explicitly deferred"
            elif spec.verification_type == VerificationType.MANUAL:
                status, reason = SpecStatus.SKIPPED, "Human verification required"
            elif any(c.status == "failed" for c in all_checks):
                status, reason = SpecStatus.FAILING, "Linked verification failed"
            elif not required:
                status, reason = SpecStatus.PENDING, f"No {spec.verification_type.value} evidence"
            elif any(c.status != "passed" for c in required):
                status, reason = SpecStatus.UNKNOWN, "Required evidence was skipped or inconclusive"
            else:
                status, reason = SpecStatus.PASSING, None
            results.append(SpecResult(spec, status, test, reason, all_checks))
        return VerificationReport(results=results, evidence=checks)

    def verify_single(self, spec_id: str) -> Optional[SpecResult]:
        specs = [s for s in collect_specs(self.specs_dir) if s.id == spec_id]
        results = self._verify(specs, ()).results
        return results[0] if results else None
