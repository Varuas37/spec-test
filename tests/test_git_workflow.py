"""Tests for git workflow integration."""

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from rich.text import Text

from spec_test import spec


def run_spec_test(*args, cwd=None, **kwargs):
    """Run spec-test CLI via python module for reliable testing."""
    cmd = [sys.executable, "-m", "spec_test.cli"] + list(args)
    return subprocess.run(cmd, cwd=cwd, **kwargs)


@spec("GIT-001", "`init --enable-git-workflow` flag installs pre-commit hook")
def test_init_with_git_workflow_flag(tmp_path):
    """Test that --enable-git-workflow flag installs the hook."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    # Run spec-test init with flag
    result = run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook_path.exists()


@spec("GIT-002", "Hook installation backs up existing pre-commit hook to pre-commit.backup")
def test_hook_backs_up_existing(tmp_path):
    """Test that existing hooks are backed up."""
    # Initialize git and create existing hook
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    hooks_dir = tmp_path / ".git" / "hooks"
    existing_hook = hooks_dir / "pre-commit"
    existing_hook.write_text("#!/bin/sh\necho 'old hook'\n")

    # Run spec-test init
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    backup_path = hooks_dir / "pre-commit.backup"
    assert backup_path.exists()
    assert "old hook" in backup_path.read_text()


@spec("GIT-003", "Hook installation makes pre-commit executable (chmod +x)")
def test_hook_is_executable(tmp_path):
    """Test that installed hook has executable permissions."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    mode = hook_path.stat().st_mode
    assert mode & stat.S_IEXEC  # Owner execute permission


@spec("GIT-004", "Hook installation warns when .git directory not found")
def test_hook_warns_no_git(tmp_path):
    """Test warning when git not initialized."""
    result = run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert "not found" in result.stdout.lower() or "warning" in result.stdout.lower()


@spec("GIT-005", "Hook installation succeeds when .git directory exists")
def test_hook_succeeds_with_git(tmp_path):
    """Test successful installation when git exists."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    result = run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "installed" in result.stdout.lower() or "✓" in result.stdout


@spec("GIT-010", "Pre-commit hook runs `spec-test verify` before commit")
def test_hook_runs_verify(tmp_path):
    """Test that hook executes spec-test verify."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    hook_content = (tmp_path / ".git" / "hooks" / "pre-commit").read_text()
    assert "verify" in hook_content and "spec" in hook_content.lower()


@spec("GIT-011", "Pre-commit hook blocks commit when specs fail")
def test_hook_blocks_failing_specs(tmp_path):
    """Test that hook blocks commits with failing specs."""
    # Setup git repo with spec-test
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    # Create a failing test
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_fail.py").write_text("""
from spec_test import spec

@spec("EXAMPLE-001", "Test")
def test_fail():
    assert False
""")

    # Try to commit - configure git first
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)

    result = subprocess.run(
        ["git", "commit", "-m", "test"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0  # Commit should be blocked


@spec("GIT-012", "Pre-commit hook blocks commit when tests missing")
def test_hook_blocks_missing_tests(tmp_path):
    """Test that hook blocks commits with missing tests."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    # example.md has specs but no tests
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)

    result = subprocess.run(
        ["git", "commit", "-m", "test"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0  # Should block due to missing tests


@spec("GIT-013", "Pre-commit hook allows commit when all specs pass")
def test_hook_allows_passing_specs(tmp_path):
    """Test that hook allows commits when all specs pass."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    # Add passing tests for all specs
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_pass.py").write_text("""
from spec_test import spec

@spec("EXAMPLE-001", "Test 1")
def test_1():
    assert True

@spec("EXAMPLE-002", "Test 2")
def test_2():
    assert True
""")

    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)

    result = subprocess.run(
        ["git", "commit", "-m", "test"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0  # Commit should succeed


@spec("GIT-014", "Pre-commit hook can be bypassed with --no-verify")
def test_hook_bypass_with_no_verify(tmp_path):
    """Test that --no-verify bypasses the hook."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    # Even with missing tests, --no-verify should work
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True)

    result = subprocess.run(
        ["git", "commit", "--no-verify", "-m", "test"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0  # Should succeed with --no-verify


@spec("GIT-015", "Pre-commit hook auto-detects spec-test command in PATH")
def test_hook_detects_spec_test_in_path(tmp_path):
    """Test that hook tries to find spec-test in PATH."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    hook_content = (tmp_path / ".git" / "hooks" / "pre-commit").read_text()
    assert "command -v spec-test" in hook_content


@spec("GIT-016", "Pre-commit hook falls back to python -m spec_test.cli")
def test_hook_falls_back_to_python_module(tmp_path):
    """Test that hook can use python -m fallback."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    hook_content = (tmp_path / ".git" / "hooks" / "pre-commit").read_text()
    assert "python" in hook_content and "spec_test.cli" in hook_content


@spec("GIT-017", "Pre-commit hook shows clear error message on verification failure")
def test_hook_shows_clear_error(tmp_path):
    """Test that hook provides helpful error messages."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    hook_content = (tmp_path / ".git" / "hooks" / "pre-commit").read_text()
    assert "Commit blocked" in hook_content or "failed" in hook_content
    assert "--no-verify" in hook_content


@spec("GIT-018", "Pre-commit hook shows success message when verification passes")
def test_hook_shows_success_message(tmp_path):
    """Test that hook shows success confirmation."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
    )

    hook_content = (tmp_path / ".git" / "hooks" / "pre-commit").read_text()
    assert "verified" in hook_content.lower() or "✅" in hook_content


@spec("GIT-030", "CLI shows confirmation when hook installed")
def test_cli_confirms_hook_install(tmp_path):
    """Test that CLI shows installation confirmation."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    result = run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert "installed" in result.stdout.lower() or "✓" in result.stdout


@spec("GIT-031", "CLI shows skip message when git not initialized")
def test_cli_shows_skip_message(tmp_path):
    """Test that CLI shows warning when git not available."""
    result = run_spec_test(
        "init", "--enable-git-workflow",
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert "warning" in result.stdout.lower() or "not found" in result.stdout.lower()


@spec("GIT-033", "CLI help text documents --enable-git-workflow flag")
def test_cli_help_documents_flag():
    """Test that --help shows the git workflow flag."""
    result = run_spec_test(
        "init", "--help",
        capture_output=True,
        text=True,
        env={**os.environ, "COLUMNS": "120", "FORCE_COLOR": "1"},
    )

    assert "--enable-git-workflow" in Text.from_ansi(result.stdout).plain
    assert result.returncode == 0


@pytest.fixture
def isolated_hook_repo(tmp_path):
    """Use a disposable repo without inherited Git templates or global config."""
    tmp_path = tmp_path.resolve()
    subprocess.run(["git", "-c", "init.templateDir=", "init", str(tmp_path)], check=True,
                   capture_output=True)
    run = run_spec_test("init", str(tmp_path), "--enable-git-workflow", capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    return tmp_path


def run_hook(repo, path, shell="/bin/sh"):
    return subprocess.run(
        [shell, str(repo / ".git/hooks/pre-commit")],
        cwd=repo, env={**os.environ, "PATH": str(path)},
        capture_output=True, text=True,
    )


def executable(path, content):
    path.write_text("#!/bin/sh\n" + content)
    path.chmod(0o700)


@spec("GIT-020", "Missing Python package fails closed with installation guidance")
@pytest.mark.skipif(not Path("/bin/sh").exists(), reason="POSIX hook required")
def test_missing_spec_test_package(isolated_hook_repo):
    import shlex

    path = isolated_hook_repo / "tools"
    path.mkdir()
    executable(path / "python3", f'exec {shlex.quote(sys.executable)} -I -S "$@"\n')
    result = run_hook(isolated_hook_repo, path)
    assert result.returncode == 1
    assert "spec-test is not installed" in result.stdout
    assert "pip install spec-test" in result.stdout


@spec("GIT-021", "Neither CLI nor Python on PATH fails closed")
@pytest.mark.skipif(not Path("/bin/sh").exists(), reason="POSIX hook required")
def test_missing_cli_and_python(isolated_hook_repo):
    path = isolated_hook_repo / "empty-path"
    path.mkdir()
    result = run_hook(isolated_hook_repo, path)
    assert result.returncode == 1
    assert "Cannot find spec-test or python" in result.stdout


@spec("GIT-022", "The hook returns the verifier's exit code")
@pytest.mark.skipif(not Path("/bin/sh").exists(), reason="POSIX hook required")
def test_hook_preserves_verifier_exit_code(isolated_hook_repo):
    path = isolated_hook_repo / "tools"
    path.mkdir()
    executable(path / "spec-test", '[ "$1" = verify ] || exit 27\nexit 2\n')
    assert run_hook(isolated_hook_repo, path).returncode == 2


@spec("GIT-023", "The POSIX hook works when invoked in both supported shells")
@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_installed_hook_runs_with_each_shell(isolated_hook_repo, shell):
    import shutil

    shell_path = shutil.which(shell)
    if not shell_path:
        pytest.skip(f"{shell} unavailable")
    path = isolated_hook_repo / "tools"
    path.mkdir()
    executable(path / "spec-test", '[ "$1" = verify ]\n')
    result = run_hook(isolated_hook_repo, path, shell=shell_path)
    assert result.returncode == 0 and "All specs verified" in result.stdout


@spec("GIT-024", "An installer-generated hook tells the developer how to fix verification")
@pytest.mark.skipif(not Path("/bin/sh").exists(), reason="POSIX hook required")
def test_failed_hook_prints_fix_instructions(isolated_hook_repo):
    path = isolated_hook_repo / "tools"
    path.mkdir()
    executable(path / "spec-test", "exit 1\n")
    result = run_hook(isolated_hook_repo, path)
    assert result.returncode == 1
    assert "Fix failing tests" in result.stdout and "Add missing tests" in result.stdout
    assert "git commit --no-verify" in result.stdout


@spec("GIT-032", "Replacing a hook reports where the prior hook was copied")
def test_hook_replacement_reports_and_preserves_backup(isolated_hook_repo):
    hook = isolated_hook_repo / ".git/hooks/pre-commit"
    old = "#!/bin/sh\nexit 17\n"
    hook.write_text(old)
    run = run_spec_test(
        "init", str(isolated_hook_repo), "--enable-git-workflow", capture_output=True, text=True
    )
    assert run.returncode == 0
    assert "Backing up existing hook to pre-commit.backup" in Text.from_ansi(run.stdout).plain
    assert hook.with_name("pre-commit.backup").read_text() == old
    assert old != hook.read_text()
