"""Trace links are validated source locations, never passing check receipts."""

import json

import pytest
from typer.testing import CliRunner

from spec_test.cli import app


def link(role, **patch):
    row = {
        "spec_id": "QUEUE-001",
        "role": role,
        "file": "src/lib.rs",
        "symbol": "try_enqueue" if role == "implements" else "proofs::queue_001",
        "language": "rust",
        "line": 17 if role == "implements" else 47,
    }
    return row | patch


@pytest.fixture
def trace(tmp_path):
    specs = tmp_path / "adr"
    specs.mkdir()
    spec_file = specs / "0042.md"
    spec_file.write_text("# Queue policy\n\n- **QUEUE-001**: Preserve occupancy when full.\n")
    index = tmp_path / "index.json"

    def run(rows, *, require=True, version=1):
        index.write_text(json.dumps({"schema_version": version, "links": rows}))
        args = ["trace", "--specs", str(specs), "--index", str(index)]
        if require:
            args += ["--require", "QUEUE-001"]
        return CliRunner().invoke(app, args)

    return run, spec_file


def test_trace_connects_adr_to_rust_and_proof_without_attesting_pass(trace):
    run, spec_file = trace
    implementation, proof = link("implements"), link("verifies")
    result = run([proof, implementation])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "schema_version": 1,
        "requirements": [{
            "spec_id": "QUEUE-001",
            "requirement": {"file": spec_file.as_posix(), "line": 3},
            "links": [implementation, proof],
        }],
    }


@pytest.mark.parametrize(("rows", "message"), [
    ([], "missing trace roles"),
    ([link("implements")], "missing trace roles: verifies"),
    ([link("verifies")], "missing trace roles: implements"),
    ([link("implements", spec_id="TYPO-001"), link("implements"), link("verifies")],
     "Unknown requirement ID: TYPO-001"),
    ([link("implements"), link("implements", line=18), link("verifies")], "duplicate"),
    ([link("implements"), link("verifies", symbol="try_enqueue")], "separate symbols"),
    ([link("implements", file="../outside.rs"), link("verifies")], "invalid trace source path"),
    ([link("implements", line=True), link("verifies")], "invalid trace row"),
    ([link("implements", status="passed"), link("verifies")], "invalid trace row"),
])
def test_trace_rejects_drift_and_non_trace_fields(trace, rows, message):
    run, _ = trace
    result = run(rows)
    assert result.exit_code == 2
    assert message in result.stderr
    assert not result.stdout


def test_trace_rejects_other_versions_and_duplicate_requirements(trace):
    run, spec_file = trace
    rows = [link("implements"), link("verifies")]
    assert "schema version" in run(rows, version=True).stderr
    spec_file.write_text(spec_file.read_text() * 2)
    assert "Duplicate requirement ID" in run(rows).stderr


def test_combines_indexes_without_borrowing_roles_from_other_languages(trace, tmp_path):
    _, spec_file = trace
    rust, ts = tmp_path / "rust.json", tmp_path / "ts.json"

    def save(index, rows):
        index.write_text(json.dumps({"schema_version": 1, "links": rows}))

    save(rust, [link("implements"), link("verifies")])
    ts_implementation = link("implements", language="typescript", file="src/queue.ts")
    save(ts, [ts_implementation])
    args = ["trace", "--specs", str(spec_file.parent), "--index", str(rust), "--index", str(ts)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert "typescript): missing trace roles: verifies" in result.stderr
    save(ts, [ts_implementation, link("verifies", language="typescript", file="tests/queue.ts")])
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    [row] = json.loads(result.stdout)["requirements"]
    assert {(l["language"], l["role"]) for l in row["links"]} == {
        (language, role)
        for language in ("rust", "typescript")
        for role in ("implements", "verifies")
    }
