"""Exercise the generated starter project through the real CLI."""

import subprocess
import sys
from pathlib import Path

from spec_test import specs


@specs("EXAMPLE-001", "EXAMPLE-002")
def test_starter_verification_reports_passing_and_missing_evidence(tmp_path):
    cli = [sys.executable, "-m", "spec_test.cli"]
    subprocess.run([*cli, "init", str(tmp_path)], check=True, capture_output=True)
    spec_path = tmp_path / "design/specs/example.md"
    bundled_reference = Path(__file__).resolve().parents[1] / "design/specs/example.md"
    assert spec_path.read_text() == bundled_reference.read_text()
    tests = tmp_path / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_demo.py").write_text(
        'from spec_test import spec\n'
        '@spec("EXAMPLE-001", "A passing starter check")\n'
        'def test_demo():\n'
        '    assert True\n'
    )
    run = subprocess.run(
        [*cli, "verify", "-s", str(spec_path.parent), "-t", str(tests),
         "--require-issues", "--evidence-output", str(tmp_path / "checks.json")],
        text=True, capture_output=True, cwd=tmp_path,
    )
    assert run.returncode == 2, run.stdout + run.stderr
    assert "EXAMPLE-002" in run.stdout and "Missing Tests: 1" in run.stdout
    import json
    checks = json.loads((tmp_path / "checks.json").read_text())["checks"]
    assert [(row["spec_id"], row["status"]) for row in checks] == [("EXAMPLE-001", "passed")]


def test_init_installs_polyglot_guidance_at_skill_paths(tmp_path):
    subprocess.run(
        [sys.executable, "-m", "spec_test.cli", "init", str(tmp_path)],
        check=True, capture_output=True,
    )
    skills = tmp_path / ".claude" / "skills"
    workflow = (skills / "spec-workflow" / "SKILL.md").read_text()
    implement = (skills / "spec-implement" / "SKILL.md").read_text()
    verify = (skills / "spec-verify" / "SKILL.md").read_text()
    assert "spec-test plan --root ." in workflow and "spec-test.toml" in workflow
    assert 'spec_test::implements("QUEUE-001")' in implement
    assert "@specTestImplements QUEUE-001" in implement
    assert 'specProperty("QUEUE-001"' in implement
    assert "spec-test trace" in verify and "--evidence" in verify
    assert "do not require Kani" in verify
