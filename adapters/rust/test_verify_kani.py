"""Refusal tests for the optional Kani producer; no solver install required."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).with_name("verify_kani.py")
SPEC = importlib.util.spec_from_file_location("verify_kani", SCRIPT)
assert SPEC and SPEC.loader
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)


def empty_receipt() -> dict:
    root = Path("/isolated/adapter")
    timestamp = datetime(2026, 11, 27, 12, tzinfo=UTC).isoformat()
    name = verify.HARNESS
    return {
        "metadata": {"version": "1.0", "kani_version": verify.VERSION, "timestamp": timestamp},
        "tools": {"kani": verify.VERSION},
        "project": {"workspace_root": str(root), "crate_name": ["spec_test_rust_queue", "verify"]},
        "harness_metadata": [{
            "pretty_name": name, "crate_name": "spec_test_rust_queue",
            "source": {"file": "src/proofs/kani.rs"},
            "attributes": {"kind": "Proof", "should_panic": False},
        }],
        "verification_results": {
            "summary": {"total_harnesses": 1, "executed": 1, "status": "completed",
                        "successful": 1, "failed": 0},
            "results": [{
                "harness_id": name, "status": "Success",
                "checks": [
                    {"id": 1, "function": name, "category": "assertion", "status": "Success"},
                    *[
                        {"id": index, "function": name, "category": "cover",
                         "status": "Satisfied", "description": label}
                        for index, label in enumerate(sorted(verify.COVERS), start=2)
                    ],
                ],
            }],
        },
        "error_details": [{"harness_id": name, "has_errors": False}],
        "property_details": [{
            "harness_id": name,
            "property_details": {"total_properties": 4, "passed": 1, "satisfied": 3, "failed": 0,
                                 "unreachable": 0, "undetermined": 0, "solver_error": 0,
                                 "unsatisfiable": 0, "uncovered": 0},
        }],
    }


class ReportTests(unittest.TestCase):
    def parse(self, report):
        start = datetime(2026, 11, 27, 12, tzinfo=UTC)
        return verify.verify_report(
            report, Path("/isolated/adapter"), start, start + timedelta(seconds=1)
        )

    def test_positive_report(self):
        self.assertEqual(self.parse(empty_receipt()), 1)

    def test_refusals(self):
        mutations = [
            ("empty", (), None),
            ("schema", ("metadata", "version"), "2.0"),
            ("version", ("tools", "kani"), "0.67.0"),
            ("stale", ("metadata", "timestamp"), "2026-11-27T11:59:59Z"),
            ("wrong workspace", ("project", "workspace_root"), "/another/adapter"),
            ("wrong harness", ("harness_metadata", 0, "pretty_name"), "other::harness"),
            ("zero harnesses", ("verification_results", "summary", "executed"), 0),
            ("partial", ("verification_results", "summary", "status"), "partial"),
            ("false integer", ("verification_results", "summary", "executed"), True),
            ("failed", ("verification_results", "results", 0, "status"), "Failure"),
            ("skipped", ("verification_results", "results", 0, "status"), "Skipped"),
            ("wrong result", ("verification_results", "results", 0, "harness_id"), "other"),
            ("extra errors", ("error_details", 0, "has_errors"), True),
            ("unreachable cover", ("verification_results", "results", 0, "checks", 1, "status"),
             "Unreachable"),
            ("missing cover", ("verification_results", "results", 0, "checks", 1, "category"),
             "assertion"),
            ("duplicate cover", ("verification_results", "results", 0, "checks", 1, "description"),
             sorted(verify.COVERS)[1]),
            ("incomplete tally", ("property_details", 0, "property_details", "undetermined"), 1),
        ]
        good = empty_receipt()
        for case, keys, value in mutations:
            with self.subTest(case=case), self.assertRaises(verify.ProofError):
                if not keys:
                    self.parse(value)
                else:
                    changed = deepcopy(good)
                    node = changed
                    for key in keys[:-1]:
                        node = node[key]
                    node[keys[-1]] = value
                    self.parse(changed)

    def test_missing_empty_invalid_and_ambiguous_json_files(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with self.assertRaises(verify.ProofError):
                verify.load_report(output)
            for value in ("", "{", '{"metadata": {}, "metadata": {}}'):
                with self.subTest(value=value), self.assertRaises(verify.ProofError):
                    output.write_text(value, encoding="utf-8")
                    verify.load_report(output)


@unittest.skipUnless(os.name == "posix", "fake cargo launcher requires POSIX executables")
class CliTests(unittest.TestCase):
    def run_cli(self, case):
        with TemporaryDirectory() as directory:
            cargo = Path(directory) / "cargo"
            cargo.write_text(
                f"#!{sys.executable}\n"
                "import os, sys\n"
                "from pathlib import Path\n"
                "case = os.environ['FAKE_CARGO_CASE']\n"
                "if sys.argv[1:] == ['kani', '--version']:\n"
                " print('Kani Rust Verifier ' + ('0.67.0' if case == 'wrong-version' else '0.68.0') + ' (cargo plugin)')\n"
                "else:\n"
                " path = Path(sys.argv[sys.argv.index('--export-json')+1])\n"
                " assert not path.exists()\n"
                " if case == 'fresh-invalid': path.write_text('{}')\n"
                " if case == 'solver-failure': raise SystemExit(1)\n",
                encoding="utf-8",
            )
            cargo.chmod(stat.S_IRWXU)
            return subprocess.run(
                [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False,
                env={**os.environ, "PATH": f"{directory}{os.pathsep}{os.environ['PATH']}",
                     "FAKE_CARGO_CASE": case},
            )

    def test_solver_failures_emit_only_failed_evidence(self):
        for case in ("wrong-version", "missing-report", "fresh-invalid", "solver-failure"):
            with self.subTest(case=case):
                process = self.run_cli(case)
                self.assertEqual(process.returncode, 1, process.stderr)
                checks = json.loads(process.stdout)["checks"]
                self.assertEqual(len(checks), 1)
                self.assertEqual(checks[0]["status"], "failed")
                self.assertEqual(checks[0]["kind"], "implementation-proof")


if __name__ == "__main__":
    unittest.main()
