"""Generate verification reports."""

from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .types import SpecResult, SpecStatus, VerificationReport


class Reporter:
    """Generate and display verification reports."""

    def __init__(self):
        self.console = Console()

    def print_terminal(self, report: VerificationReport):
        """Print report to terminal with rich formatting."""

        # Header
        self.console.print()
        self.console.print(
            Panel.fit(
                "[bold]Specification Verification Report[/bold]",
                border_style="blue",
            )
        )
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
                result.spec.description[:50] + "..."
                if len(result.spec.description) > 50
                else result.spec.description,
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
            SpecStatus.PASSING: "[green]PASS[/green]",
            SpecStatus.FAILING: "[red]FAIL[/red]",
            SpecStatus.PENDING: "[yellow]NO TEST[/yellow]",
            SpecStatus.SKIPPED: "[dim]SKIP[/dim]",
        }.get(status, "?")

    def _get_test_info(self, result: SpecResult) -> str:
        """Get test path or status notes."""
        if result.test:
            return f"[dim]{result.test.test_path}[/dim]"
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
                self.console.print(f"  [yellow]!  {result.spec.id}[/yellow]: No test")
                self.console.print(
                    f"      [dim]{result.spec.source_file}:{result.spec.source_line}[/dim]"
                )
            elif result.status == SpecStatus.FAILING:
                self.console.print(f"  [red]X {result.spec.id}[/red]: Test failing")
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
            f"PASS {report.passing} | FAIL {report.failing} | NO TEST {report.missing}",
            "",
            "## Results",
            "",
            "| Spec ID | Description | Status | Test |",
            "|---------|-------------|--------|------|",
        ]

        for result in report.results:
            status = {
                SpecStatus.PASSING: "PASS",
                SpecStatus.FAILING: "FAIL",
                SpecStatus.PENDING: "NO TEST",
                SpecStatus.SKIPPED: "SKIP",
            }.get(result.status, "?")

            test_path = result.test.test_path if result.test else "-"
            desc = result.spec.description.replace("|", "\\|")

            lines.append(f"| {result.spec.id} | {desc} | {status} | `{test_path}` |")

        output.write_text("\n".join(lines))
