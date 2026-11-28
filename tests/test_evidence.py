"""Integration checks for runner evidence, issue links and exit codes."""

import json
import pytest

from typer.testing import CliRunner

from spec_test import spec, specs
from spec_test.cli import app
from spec_test.verifier import SpecVerifier


def subject(tmp, definitions):
    specs = tmp / "specs"
    tests = tmp / "tests"
    issues = tmp / "issues"
    for path in (specs, tests, issues):
        path.mkdir()
    (specs / "demo.md").write_text(definitions)
    return specs, tests, issues


@spec("VER-002", "Run and distinguish every linked or parametrized test")
def test_pytest_evidence_does_not_pass_skips_or_lose_siblings(tmp_path):
    specs, tests, _ = subject(
        tmp_path, "**CASE-001**: Samples\n**CASE-002**: More samples\n**CASE-003**: Manual skips\n"
    )
    (tests / "test_cases.py").write_text("""
import pytest
from spec_test import spec

@spec("CASE-001", "passing sibling")
def test_first(): pass

@spec("CASE-001", "skipped sibling")
@pytest.mark.skip()
def test_second(): pass

@spec("CASE-002", "passing case is not evidence for the failing case")
@pytest.mark.parametrize("value", [0, 1])
def test_two(value): assert value == 0

@spec("CASE-003", "xfail is not proof")
@pytest.mark.xfail()
def test_xfail(): assert False
""")
    report = SpecVerifier(specs, tests).verify()
    assert [r.status.value for r in report.results] == ["unknown", "failing", "unknown"]
    assert [c.status for c in report.results[0].evidence] == ["passed", "skipped"]
    assert not report.is_passing


@spec("COL-006", "CI can require that linked local issue files exist")
def test_strict_issues(tmp_path):
    specs, tests, issues = subject(
        tmp_path, "## Related Issue\n- [Why](../issues/reason.md)\n\n**LINK-001** [manual]: Read it\n"
    )
    args = [
        "verify", "--specs", str(specs), "--tests", str(tests), "--require-issues"
    ]
    bad = CliRunner().invoke(app, args)
    assert bad.exit_code == 5 and "Missing or broken Related Issue" in bad.output
    (issues / "reason.md").write_text("Meaningful rationale\n")
    assert CliRunner().invoke(app, args).exit_code == 0


@spec("VER-006", "A model is not evidence of the implementation proof")
def test_reports_proof_kinds_separately(tmp_path):
    specs, tests, _ = subject(tmp_path, "**QUEUE-001** [provable]: A bound\n")
    p = tmp_path / "evidence.json"
    output = tmp_path / "combined.json"
    command = [
        "verify", "--specs", str(specs), "--tests", str(tests),
        "--evidence", str(p), "--evidence-output", str(output),
    ]
    row = dict(spec_id="QUEUE-001", kind="model-proof", runner="demo", name="bound", status="passed")
    p.write_text(json.dumps({"schema_version": 1, "checks": [row]}))
    assert CliRunner().invoke(app, command).exit_code == 2
    row.update(kind="implementation-proof", status="unknown")
    p.write_text(json.dumps({"schema_version": 1, "checks": [row]}))
    assert CliRunner().invoke(app, command).exit_code == 2
    row.update(status="passed")
    p.write_text(json.dumps({"schema_version": 1, "checks": [row]}))
    assert CliRunner().invoke(app, command).exit_code == 0
    assert json.loads(output.read_text())["checks"][0]["status"] == "passed"
    row.update(spec_id="OTHER-001")
    p.write_text(json.dumps({"schema_version": 1, "checks": [row]}))
    assert CliRunner().invoke(app, command).exit_code == 5


@spec("VER-003", "Duplicate receipts or no result are never green")
def test_refuses_bad_receipts(tmp_path):
    specs, tests, _ = subject(tmp_path, "**QUEUE-001**: A bound\n")
    p = tmp_path / "receipt.json"
    command = ["verify", "-s", str(specs), "-t", str(tests), "--evidence", str(p)]
    row = dict(spec_id="QUEUE-001", kind="test", runner="demo", name="bound", status="passed")
    for checks in ([], [row, row]):
        p.write_text(json.dumps({"schema_version": 1, "checks": checks}))
        assert CliRunner().invoke(app, command).exit_code == 5


@spec("EVID-005", "AI review packet requests human review without approving it")
def test_ai_review_packet_is_offline_and_never_credits_coverage(tmp_path):
    specs, tests, _ = subject(
        tmp_path, "**REVIEW-001** [ai_review]: Assess usability\n<!-- ai: inspect spacing -->\n"
    )
    output = tmp_path / "review.json"
    run = CliRunner().invoke(
        app, ["review-packet", "-s", str(specs), "-o", str(output)]
    )
    assert run.exit_code == 0
    item, = json.loads(output.read_text())["items"]
    assert item["status"] == "needs-human-review"
    assert item["review_hint"] == "inspect spacing"
    report = SpecVerifier(specs, tests).verify()
    assert report.skipped == 1 and report.passing == 0


@spec("EVID-010", "Offline review records bind to the exported inputs but cannot satisfy verify")
def test_human_review_handoff_has_no_evidence_import(tmp_path, monkeypatch):
    import hashlib
    import socket

    specs, tests, _ = subject(
        tmp_path, "**REVIEW-001** [manual]: Check keyboard focus\n"
    )
    output = tmp_path / "review.json"
    command = ["review-packet", "-s", str(specs), "-o", str(output)]

    def refuse_network(*args, **kwargs):
        raise AssertionError("review-packet must stay offline")

    monkeypatch.setattr(socket.socket, "connect", refuse_network)
    assert CliRunner().invoke(app, command).exit_code == 0
    original = output.read_bytes()
    assert CliRunner().invoke(app, command).exit_code == 0
    assert output.read_bytes() == original
    item, = json.loads(original)["items"]
    digest = item.pop("review_input_sha256")
    canonical = json.dumps(item, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == digest

    (specs / "demo.md").write_text("**REVIEW-001** [manual]: Check pointer focus\n")
    assert CliRunner().invoke(app, command).exit_code == 0
    updated, = json.loads(output.read_text())["items"]
    assert updated["review_input_sha256"] != digest

    updated["status"] = "approved"
    output.write_text(json.dumps({"schema_version": 1, "items": [updated]}))
    verify = ["verify", "-s", str(specs), "-t", str(tests), "--evidence", str(output)]
    assert CliRunner().invoke(app, verify).exit_code == 5
    output.write_text(json.dumps({
        "schema_version": 1,
        "checks": [{
            "spec_id": "REVIEW-001", "kind": "manual", "runner": "reviewer",
            "name": "pointer focus", "status": "passed",
        }],
    }))
    assert CliRunner().invoke(app, verify).exit_code == 5
    report = SpecVerifier(specs, tests).verify()
    assert report.passing == 0 and report.skipped == 1


@specs("EVID-006", "HYP-050", "HYP-061")
def test_hypothesis_property_is_receipted(tmp_path):
    import pytest
    pytest.importorskip("hypothesis")
    specs, tests, _ = subject(tmp_path, "**PROP-001** [property]: Doubling is even\n")
    (tests / "test_property.py").write_text("""
from spec_test import property_test

@property_test(spec_id="PROP-001", settings={"max_examples": 10})
def test_even(value: int):
    assert (value * 2) % 2 == 0
""")
    report = SpecVerifier(specs, tests).verify()
    assert report.passing == 1
    check, = report.evidence
    assert check.kind == "property" and check.status == "passed"


@spec("EVID-007", "Specs and runner receipts accept prefixes such as Z3")
def test_numbered_prefix_cannot_hide_the_proof_roadmap(tmp_path):
    specs, tests, _ = subject(tmp_path, "**Z3-901** [provable]: A bound\n")
    report = SpecVerifier(specs, tests).verify()
    assert report.total_specs == report.missing == 1
    assert report.results[0].spec.id == "Z3-901"
    p = tmp_path / "evidence.json"
    row = dict(spec_id="Z3-901", kind="implementation-proof", runner="demo", name="bound", status="passed")
    p.write_text(json.dumps({"schema_version": 1, "checks": [row]}))
    args = ["verify", "-s", str(specs), "-t", str(tests), "--evidence", str(p)]
    assert CliRunner().invoke(app, args).exit_code == 0


@spec("EVID-008", "Deselected parameter cases make the full requirement inconclusive")
def test_filters_cannot_hide_an_unexecuted_case(tmp_path, monkeypatch):
    specs, tests, _ = subject(tmp_path, "**CASE-001**: Every case matters\n")
    (tests / "test_cases.py").write_text("""
import pytest
from spec_test import spec

@spec("CASE-001", "One passing and one failing case")
@pytest.mark.parametrize("value", [0, 1], ids=["good", "bad"])
def test_values(value): assert value == 0
""")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k good")
    report = SpecVerifier(specs, tests).verify()
    assert report.unknown == 1 and not report.is_passing


@spec("EVID-009", "Explicit parameter selectors keep their individual outcomes")
def test_batch_reports_individual_parameter_outcomes(tmp_path):
    from spec_test.runner import run_tests_batch

    path = tmp_path / "test_cases.py"
    path.write_text("""
import pytest

@pytest.mark.parametrize("value", [0, 1], ids=["a [nested]::good", "bad"])
def test_values(value): assert value == 0
""")
    good = f"{path}::test_values[a [nested]::good]"
    bad = f"{path}::test_values[bad]"
    results = run_tests_batch([good, bad], tmp_path)
    assert results[good] == (True, None)
    assert results[bad][0] is False and "failed" in results[bad][1]


@pytest.mark.parametrize("runner", ["kani", "example-alternate-engine"])
def test_external_proof_receipt_can_select_either_runner(tmp_path, runner):
    """Exercise the receipt boundary; these fixtures do not claim real engine runs."""
    specs, tests, _ = subject(tmp_path, "**QUEUE-901** [provable]: One queue rule\n")
    receipt = tmp_path / "proof.json"
    args = ["verify", "-s", str(specs), "-t", str(tests)]
    cli = CliRunner()
    assert cli.invoke(app, args).exit_code != 0

    check = dict(spec_id="QUEUE-901", kind="model-proof", runner=runner,
                 name="queue_rule", status="passed")

    def write():
        receipt.write_text(json.dumps({"schema_version": 1, "checks": [check]}))

    cli_args = [*args, "--evidence", str(receipt)]
    write()
    assert cli.invoke(app, cli_args).exit_code != 0
    check.update(kind="implementation-proof", status="unknown")
    write()
    assert cli.invoke(app, cli_args).exit_code != 0
    check["status"] = "passed"
    write()
    assert cli.invoke(app, cli_args).exit_code == 0


@spec("HYP-055", "List discovers a property link without importing or running the test")
def test_list_spec_indicates_a_link_not_a_result(tmp_path):
    specs, tests, _ = subject(
        tmp_path, "**LIST-001**: Runs a property\n**LIST-002** [property]: Only declared\n"
    )
    (tests / "test_property.py").write_text(
        "raise AssertionError('do not execute this module')\n"
        "@property_test('LIST-001')\n"
        "def test_prop(x: int): pass\n"
    )
    listed = CliRunner().invoke(app, ["list-specs", "-s", str(specs), "-t", str(tests)])
    assert listed.exit_code == 0
    first, second = listed.output.split("LIST-002")
    assert "LIST-001" in first and "[property] linked test (not run)" in first
    assert "[property]" not in second


@spec("EVID-011", "Explicit deferrals never change coverage or waive a real check")
def test_scoped_verify_is_strict_except_reviewed_missing_evidence(tmp_path):
    specs, tests, _ = subject(tmp_path, "**GATE-001**: Shipped\n**GATE-002**: Later\n")
    passing = "from spec_test import spec\n@spec('GATE-001', 'shipped')\ndef test_one(): pass\n"
    probe = tests / "test_gate.py"
    probe.write_text(passing)
    path = tmp_path / "scope.toml"
    command = ["verify", "-s", str(specs), "-t", str(tests)]

    def run_with_gap(spec_id):
        path.write_text(
            f' schema_version = 1\n [[deferred]]\n ids = ["{spec_id}"]\n reason = "Later"\n'
        )
        return CliRunner().invoke(app, [*command, "--scope", str(path)])

    assert CliRunner().invoke(app, command).exit_code == 2
    selected = run_with_gap("GATE-002")
    assert selected.exit_code == 0, selected.output
    assert "GATE-002" in selected.output and "still missing evidence" in selected.output
    assert run_with_gap("GATE-999").exit_code == 5
    assert run_with_gap("GATE-001").exit_code == 5

    (specs / "demo.md").write_text(
        "**GATE-001**: Shipped\n**GATE-002**: Later\n**GATE-003**: Unclassified\n"
    )
    assert run_with_gap("GATE-002").exit_code == 2
    for outcome in ["assert False", "pytest.skip()"]:
        probe.write_text(
            passing + "import pytest\n@spec('GATE-002', 'now linked')\n"
            + f"def test_two(): {outcome}\n"
        )
        rejected = run_with_gap("GATE-002")
        assert rejected.exit_code == 5
        assert "not an unverified item with no evidence" in rejected.output
