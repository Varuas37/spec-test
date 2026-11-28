"""Exercise the published proof exit contract in fresh processes."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from spec_test import specs
from spec_test.prover import Z3_AVAILABLE


@pytest.mark.skipif(not Z3_AVAILABLE, reason="Z3 extra not installed")
@specs("Z3-104", "Z3-105", "Z3-106")
def test_refutation_and_inconclusive_results_never_count_as_linked_proof(tmp_path):
    design = tmp_path / "design" / "specs"
    design.mkdir(parents=True)
    (design / "sample.md").write_text("**APP-001** [provable]: Nonnegative result\n")
    source = Path(__file__).resolve().parents[1] / "src"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(source), str(tmp_path)))}

    def run(module, expression, *args, spec_id="APP-001"):
        (tmp_path / f"{module}.py").write_text(
            "from spec_test import contract, provable\n"
            f"@provable(spec={spec_id!r})\n"
            "@contract(requires=[lambda x: x >= 0], ensures=[lambda r: r >= 0])\n"
            f"def proof(x: int) -> int:\n    return {expression}\n"
        )
        return subprocess.run(
            [sys.executable, "-m", "spec_test.cli", "verify", "--proofs",
             "--proof-module", module, *args],
            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
        )

    for result, expected_code, marker in [
        (run("good", "x + 1"), 0, "PROVEN"),
        (run("bad", "x - 1"), 4, "REFUTED"),
        (run("unsupported", "abs(x)"), 2, "SKIPPED"),
        (run("strict", "abs(x)", "--fail-on-unknown", "--no-fail-on-missing"), 4, "SKIPPED"),
    ]:
        assert result.returncode == expected_code and marker in result.stdout, (
            result.stdout + result.stderr
        )


    scope = tmp_path / "scope.toml"
    scope.write_text("schema_version = 1\ndeferred = []\n")
    unlinked = run(
        "unlinked", "x + 1", "--scope", str(scope), spec_id="APP-002",
    )
    assert unlinked.returncode == 5
    assert "undefined specifications: APP-002" in unlinked.stdout
