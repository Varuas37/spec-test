"""Run the QUEUE-001 proof using the exact Kani 0.68.0 JSON export."""

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any

VERSION = "0.68.0"
HARNESS = "proofs::queue_001_transition"
COVERS = {"invalid occupancy", "full queue", "available slot"}
ADAPTER_DIR = Path(__file__).resolve().parent
MAX_REPORT_BYTES = 2 * 1024 * 1024


class ProofError(ValueError):
    """Kani could not establish the required implementation proof."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofError(message)


def own_result(rows: Any, label: str) -> dict:
    require(isinstance(rows, list) and len(rows) == 1, f"expected one {label} row")
    row = rows[0]
    require(isinstance(row, dict) and row.get("harness_id") == HARNESS, f"wrong {label} harness")
    return row


def count_is(row: dict, key: str, expected: int) -> bool:
    value = row.get(key)
    return type(value) is int and value == expected


def unique_object(items: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in items:
        require(key not in result, f"duplicate Kani report key: {key}")
        result[key] = value
    return result


def verify_report(
    report: Any,
    workspace: Path,
    started: datetime,
    ended: datetime,
) -> int:
    """Validate one completed, non-vacuous run of the expected harness."""
    try:
        meta = report["metadata"]
        require(meta["version"] == "1.0", "unsupported Kani report schema")
        require(
            meta["kani_version"] == report["tools"]["kani"] == VERSION,
            "unexpected Kani report version",
        )
        timestamp = datetime.fromisoformat(meta["timestamp"])
        require(
            timestamp.utcoffset() is not None and started <= timestamp <= ended,
            "Kani report timestamp is not from this execution",
        )

        project = report["project"]
        require(
            project["workspace_root"] == str(workspace)
            and "spec_test_rust_queue" in project["crate_name"],
            "unexpected Kani project",
        )
        harnesses = report["harness_metadata"]
        require(isinstance(harnesses, list) and len(harnesses) == 1, "expected one harness")
        harness = harnesses[0]
        require(
            harness["pretty_name"] == HARNESS
            and harness["crate_name"] == "spec_test_rust_queue"
            and harness["source"]["file"] == "src/lib.rs"
            and harness["attributes"]["kind"] == "Proof"
            and harness["attributes"]["should_panic"] is False,
            "incorrect Kani harness metadata",
        )

        verification = report["verification_results"]
        summary = verification["summary"]
        require(
            summary["status"] == "completed"
            and all(
                count_is(summary, key, expected)
                for key, expected in (
                    ("total_harnesses", 1), ("executed", 1), ("successful", 1), ("failed", 0)
                )
            ),
            "Kani did not complete exactly one successful harness",
        )
        result = own_result(verification["results"], "result")
        require(result["status"] == "Success", "Kani harness did not succeed")
        require(
            own_result(report["error_details"], "error").get("has_errors") is False,
            "Kani reported harness errors",
        )

        checks = result["checks"]
        require(isinstance(checks, list) and bool(checks), "Kani did not report checks")
        ids = set()
        covers = set()
        ordinary = 0
        harness_assertions = 0
        for check in checks:
            ident = check["id"]
            require(
                type(ident) is int and ident > 0 and ident not in ids,
                "invalid or duplicate Kani check ID",
            )
            ids.add(ident)
            category = check["category"]
            if category == "cover":
                label = check["description"]
                require(
                    label in COVERS and label not in covers and check["function"] == HARNESS,
                    "unexpected or duplicate Kani cover",
                )
                require(check["status"] == "Satisfied", f"Kani cover not reached: {label}")
                covers.add(label)
            else:
                require(check["status"] == "Success", "Kani reported an unsuccessful check")
                ordinary += 1
                if category == "assertion" and check["function"] == HARNESS:
                    harness_assertions += 1
        require(covers == COVERS, "missing Kani covers")
        require(harness_assertions > 0, "missing Kani harness assertions")

        properties = own_result(report["property_details"], "property")["property_details"]
        require(
            all(
                count_is(properties, key, expected)
                for key, expected in (
                    ("total_properties", len(checks)), ("passed", ordinary),
                    ("satisfied", len(COVERS)), ("failed", 0), ("unreachable", 0),
                    ("undetermined", 0), ("solver_error", 0), ("unsatisfiable", 0),
                    ("uncovered", 0),
                )
            ),
            "Kani property totals do not match a complete proof",
        )
        return ordinary
    except (KeyError, TypeError, AttributeError) as error:
        raise ProofError("malformed or incomplete Kani JSON report") from error
    except ValueError as error:
        if isinstance(error, ProofError):
            raise
        raise ProofError("invalid Kani report timestamp") from error


def load_report(path: Path) -> Any:
    try:
        info = path.lstat()
        require(
            stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_REPORT_BYTES,
            "invalid Kani JSON report file",
        )
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ProofError("Kani did not create a readable JSON report") from error


def run_command(args: list[str], workspace: Path, environment: dict[str, str], timeout: int):
    try:
        return subprocess.run(
            args, cwd=workspace, env=environment, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace", check=False,
        )
    except OSError as error:
        raise ProofError(f"cannot invoke cargo kani: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise ProofError("cargo kani timed out") from error


def run_proof(workspace: Path = ADAPTER_DIR) -> str:
    with TemporaryDirectory(prefix="spec-test-kani-") as scratch:
        root = Path(scratch)
        report_file = root / "kani.json"
        environment = {
            **os.environ,
            "CARGO_TARGET_DIR": str(root / "target"),
            "CARGO_NET_OFFLINE": "true",
        }
        version = run_command(["cargo", "kani", "--version"], workspace, environment, 20)
        require(
            version.returncode == 0 and version.stdout.splitlines()[:1]
            == [f"Kani Rust Verifier {VERSION} (cargo plugin)"],
            f"install and set up Kani {VERSION} before running this adapter",
        )
        require(
            not report_file.exists() and not report_file.is_symlink(),
            "Kani report path was not fresh",
        )
        started = datetime.now(UTC)
        completed = run_command(
            ["cargo", "kani", "--harness", HARNESS, "--exact", "-Z", "unstable-options",
             "--export-json", str(report_file)],
            workspace,
            environment,
            120,
        )
        ended = datetime.now(UTC)
        if completed.returncode:
            tail = "\n".join((completed.stdout + "\n" + completed.stderr).splitlines()[-12:])
            raise ProofError(f"cargo kani exited {completed.returncode}\n{tail}")
        ordinary = verify_report(load_report(report_file), workspace, started, ended)
        return f"Kani {VERSION}; 1/1 harness; {ordinary} checks passed; {len(COVERS)}/3 covers reached."


def main() -> int:
    argparse.ArgumentParser(
        description=f"Run the QUEUE-001 implementation proof using Kani {VERSION}.",
    ).parse_args()
    try:
        details = run_proof()
        status = "passed"
    except ProofError as error:
        status = "failed"
        details = str(error).splitlines()[0]
        print(str(error), file=sys.stderr)
    row = {
        "spec_id": "QUEUE-001",
        "kind": "implementation-proof",
        "runner": "kani",
        "name": HARNESS.rsplit("::", 1)[-1],
        "status": status,
        "details": details,
    }
    print(json.dumps({"schema_version": 1, "checks": [row]}))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
