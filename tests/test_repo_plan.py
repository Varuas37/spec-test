import json
import sys

import pytest
from typer.testing import CliRunner

from spec_test.cli import app


def test_detects_three_languages_and_does_not_run_node_script(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\naddopts = '-q'\n")
    (tmp_path / "Cargo.toml").write_text("[workspace]\nmembers = []\n")
    (tmp_path / "Cargo.lock").touch()
    (tmp_path / "tsconfig.json").write_text("{}")
    (tmp_path / "package.json").write_text(json.dumps({
        "packageManager": "pnpm@11.9.0",
        "scripts": {"test": "touch do-not-execute"},
    }))
    cli = CliRunner()
    result = cli.invoke(app, ["plan", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["source"] == "detected"
    assert {c["language"]: c["argv"] for c in report["checks"]} == {
        "python": [sys.executable, "-m", "pytest"],
        "rust": ["cargo", "test", "--workspace", "--locked"],
        "typescript": ["pnpm", "test"],
    }
    assert not (tmp_path / "do-not-execute").exists()


def test_node_without_script_or_unambiguous_manager_is_not_guessed(tmp_path):
    package = tmp_path / "package.json"
    package.write_text("{}")
    cli = CliRunner()
    args = ["plan", "--root", str(tmp_path)]
    assert "no nonempty test script" in cli.invoke(app, args).stdout
    package.write_text('{"scripts":{"test":"test-runner"}}')
    (tmp_path / "pnpm-lock.yaml").touch()
    (tmp_path / "yarn.lock").touch()
    assert "unknown or ambiguous" in cli.invoke(app, args).stdout


def test_generated_config_is_portable_and_never_overwrites(tmp_path):
    (tmp_path / "pytest.ini").touch()
    cli = CliRunner()
    args = ["plan", "--root", str(tmp_path), "--write-config"]
    assert cli.invoke(app, args).exit_code == 0
    config = tmp_path / "spec-test.toml"
    data = config.read_text()
    assert 'argv = ["python", "-m", "pytest"]' in data
    result = cli.invoke(app, args[:-1])
    assert json.loads(result.stdout)["source"] == "spec-test.toml"
    assert cli.invoke(app, args).exit_code == 2
    assert config.read_text() == data


def config(root, *commands, cwd="."):
    rows = ["schema_version = 1"]
    for i, argv in enumerate(commands):
        rows += [f'\n[[checks]]\nid = "check-{i}"\nlanguage = "custom"',
                 f"cwd = {json.dumps(cwd)}", f"argv = {json.dumps(argv)}"]
    (root / "spec-test.toml").write_text("\n".join(rows))


def test_custom_commands_require_explicit_execution_and_fail_closed(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    config(tmp_path, ["python", "-c", "raise SystemExit(7)"],
           ["python", "-c", "from pathlib import Path; Path('ran').write_text('ok')"], cwd="work")
    cli = CliRunner()
    args = ["run-checks", "--root", str(tmp_path)]
    assert cli.invoke(app, args).exit_code == 2
    assert not (work / "ran").exists()
    result = cli.invoke(app, [*args, "--trust-repo"])
    assert result.exit_code == 1
    assert (work / "ran").read_text() == "ok"
    assert "[check-0] failed" in result.stdout
    assert "[check-1] passed" in result.stdout


@pytest.mark.parametrize("cwd", ["..", "/tmp", "./work", "C:/work", "missing", "../other"])
def test_config_rejects_a_non_contained_working_directory(tmp_path, cwd):
    config(tmp_path, ["cargo", "test"], cwd=cwd)
    result = CliRunner().invoke(app, ["plan", "--root", str(tmp_path)])
    assert result.exit_code == 2
    assert "invalid cwd" in result.stderr


def test_config_cannot_follow_a_directory_symlink_outside_root(tmp_path):
    outside = tmp_path / "other"
    root = tmp_path / "repo"
    outside.mkdir()
    root.mkdir()
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("cannot create directory symlinks")
    config(root, ["cargo", "test"], cwd="link")
    result = CliRunner().invoke(app, ["plan", "--root", str(root)])
    assert result.exit_code == 2
    assert "leaves project root" in result.stderr


def test_missing_executable_does_not_pass(tmp_path):
    config(tmp_path, ["spec-test-unavailable-executable-aa63fe77"])
    result = CliRunner().invoke(app, ["run-checks", "--root", str(tmp_path), "--trust-repo"])
    assert result.exit_code == 1
    assert "[check-0] failed" in result.stdout
