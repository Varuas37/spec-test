"""Run spec-linked properties through the public verifier in clean processes."""

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from spec_test import spec, specs

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("hypothesis") is None, reason="Hypothesis extra not installed"
)


def _project(root, requirements, source):
    tests = root / "tests"
    specs_dir = root / "design" / "specs"
    issues_dir = root / "design" / "issues"
    for directory in (tests, specs_dir, issues_dir):
        directory.mkdir(parents=True)
    (tests / "test_generated.py").write_text(dedent(source), encoding="utf-8")
    (issues_dir / "properties.md").write_text("# Properties under test\n", encoding="utf-8")
    (specs_dir / "properties.md").write_text(
        "# Properties\n\n## Related Issue\n- [Properties](../issues/properties.md)\n\n"
        "## Requirements\n"
        + "".join(f"- **{spec_id}** [property]: {description}\n"
                  for spec_id, description in requirements.items()),
        encoding="utf-8",
    )


def _isolated_env():
    env = os.environ.copy()
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD"):
        env.pop(key, None)
    src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (src, env.get("PYTHONPATH"))))
    return env


def _verify(root, name, variables=None):
    log = root / f"{name}.jsonl"
    receipt = root / f"{name}.evidence.json"
    env = {**_isolated_env(), "EXAMPLES_LOG": str(log), **(variables or {})}
    process = subprocess.run(
        [sys.executable, "-m", "spec_test.cli", "verify", "--require-issues",
         "--evidence-output", str(receipt)],
        cwd=root, env=env, capture_output=True, text=True, timeout=45,
    )
    return process, receipt, log


def _statuses(receipt):
    data = json.loads(receipt.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert all(check["runner"] == "pytest" for check in data["checks"])
    return {(check["spec_id"], check["kind"]): check["status"] for check in data["checks"]}


def _examples(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


@specs("HYP-041", "HYP-043", "HYP-045", "HYP-046", "HYP-047", "HYP-050", "HYP-061")
def test_verify_applies_forwarded_settings_and_emits_passing_property_evidence(tmp_path):
    _project(tmp_path, {
        "PROP-001": "Mapping overrides the active profile",
        "PROP-002": "Native settings inherit unspecified values from the active profile",
    }, """
        import json
        import os
        from pathlib import Path

        from hypothesis import HealthCheck, Verbosity, settings, strategies as st
        from spec_test import property_test

        settings.register_profile(
            "spec-test-properties", max_examples=17, deadline=None,
            derandomize=True, suppress_health_check=[HealthCheck.too_slow],
        )
        settings.load_profile("spec-test-properties")

        def record(case, value, expected_max, expected_health, expected_verbosity):
            active = settings.default
            assert active.max_examples == expected_max
            assert active.deadline is None
            assert set(active.suppress_health_check) == {expected_health}
            assert active.verbosity is expected_verbosity
            assert active.derandomize
            with Path(os.environ["EXAMPLES_LOG"]).open("a", encoding="utf-8") as log:
                log.write(json.dumps([case, value]) + "\\n")

        @property_test("PROP-001", strategies={"amount": st.integers()}, settings={
            "max_examples": 3,
            "suppress_health_check": [HealthCheck.filter_too_much],
            "verbosity": Verbosity.verbose,
        })
        def test_mapping(amount):
            record("mapping", amount, 3, HealthCheck.filter_too_much, Verbosity.verbose)

        @property_test("PROP-002", settings=settings(max_examples=5))
        def test_settings(amount: int):
            record("native", amount, 5, HealthCheck.too_slow, Verbosity.normal)
        """)
    first, first_receipt, first_log = _verify(tmp_path, "settings-first")
    second, second_receipt, second_log = _verify(tmp_path, "settings-second")
    expected = {("PROP-001", "property"): "passed", ("PROP-002", "property"): "passed"}
    for run, receipt in ((first, first_receipt), (second, second_receipt)):
        assert run.returncode == 0, run.stdout + run.stderr
        assert _statuses(receipt) == expected

    first_records = _examples(first_log)
    second_records = _examples(second_log)
    for case_name, budget in (("mapping", 3), ("native", 5)):
        first_values = [value for case, value in first_records if case == case_name]
        second_values = [value for case, value in second_records if case == case_name]
        assert len(first_values) == budget
        assert first_values == second_values


@specs("HYP-032", "HYP-033", "HYP-044", "HYP-054")
def test_verify_stores_and_reuses_examples_in_separate_processes(tmp_path):
    database = tmp_path / "examples"
    _project(tmp_path, {"PROP-003": "Persist and replay the same falsification"}, """
        import json
        import os
        from pathlib import Path

        from hypothesis import Phase, Verbosity, strategies as st
        from hypothesis.database import DirectoryBasedExampleDatabase
        from spec_test import property_test

        @property_test("PROP-003", strategies={"amount": st.just(5)}, settings={
            "database": DirectoryBasedExampleDatabase(Path(os.environ["EXAMPLE_DATABASE"])),
            "phases": ((Phase.reuse,) if os.environ["REPLAY_ONLY"] == "yes" else (Phase.generate,)),
            "verbosity": Verbosity.normal,
            "derandomize": False,
            "max_examples": 3,
            "deadline": None,
        })
        def test_falsified(amount):
            with Path(os.environ["EXAMPLES_LOG"]).open("a", encoding="utf-8") as log:
                log.write(json.dumps(amount) + "\\n")
            assert amount < 5
        """)

    options = {"EXAMPLE_DATABASE": str(database), "REPLAY_ONLY": "yes"}
    empty, empty_receipt, empty_log = _verify(tmp_path, "database-empty", options)
    assert empty.returncode == 2, empty.stdout + empty.stderr
    assert _statuses(empty_receipt) == {("PROP-003", "property"): "skipped"}
    assert not _examples(empty_log)

    generated, generated_receipt, generated_log = _verify(
        tmp_path, "database-generate", {**options, "REPLAY_ONLY": "no"}
    )
    assert generated.returncode == 1, generated.stdout + generated.stderr
    assert _statuses(generated_receipt) == {("PROP-003", "property"): "failed"}
    assert set(_examples(generated_log)) == {5}
    assert any(entry.is_file() for entry in database.rglob("*"))

    replayed, replayed_receipt, replayed_log = _verify(tmp_path, "database-replay", options)
    assert replayed.returncode == 1, replayed.stdout + replayed.stderr
    assert _statuses(replayed_receipt) == {("PROP-003", "property"): "failed"}
    assert set(_examples(replayed_log)) == {5}


@spec("HYP-042", "Spec verification fails for an example over the configured deadline")
def test_verify_reports_failure_when_forwarded_deadline_is_exceeded(tmp_path):
    _project(tmp_path, {"PROP-004": "A deliberately slow example exceeds its deadline"}, """
        import os
        from time import sleep
        from hypothesis import strategies as st
        from spec_test import property_test

        limit = 1 if os.environ["DEADLINE_ACTIVE"] == "yes" else None

        @property_test("PROP-004", strategies={"amount": st.just(1)}, settings={"deadline": limit})
        def test_slow(amount):
            sleep(0.04)
            assert amount == 1
        """)
    control, control_receipt, _ = _verify(tmp_path, "no-deadline", {"DEADLINE_ACTIVE": "no"})
    assert control.returncode == 0, control.stdout + control.stderr
    assert _statuses(control_receipt) == {("PROP-004", "property"): "passed"}

    result, receipt, _ = _verify(tmp_path, "deadline", {"DEADLINE_ACTIVE": "yes"})
    assert result.returncode == 1, result.stdout + result.stderr
    assert _statuses(receipt) == {("PROP-004", "property"): "failed"}


@spec("HYP-034", "Native pytest statistics report generated passing and failing examples")
def test_native_pytest_reports_hypothesis_example_counts(tmp_path):
    _project(tmp_path, {
        "PROP-005": "Print the count of passing generated examples",
        "PROP-006": "Print the count of failing generated examples",
    }, """
        from hypothesis import strategies as st
        from spec_test import property_test

        @property_test("PROP-005", settings={"max_examples": 3, "derandomize": True})
        def test_counts_pass(value: int):
            assert type(value) is int

        @property_test("PROP-006", strategies={"amount": st.just(5)})
        def test_counts_fail(amount):
            assert amount < 5
        """)
    process = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--hypothesis-show-statistics"],
        cwd=tmp_path, env=_isolated_env(), capture_output=True, text=True, timeout=45,
    )
    assert process.returncode == 1, process.stdout + process.stderr
    assert "test_counts_pass:" in process.stdout
    assert re.search(r"3 passing(?: examples)?, 0 failing", process.stdout), process.stdout
    assert "test_counts_fail:" in process.stdout
    assert re.search(r"0 passing(?: examples)?, [1-9]\d* failing", process.stdout), process.stdout
