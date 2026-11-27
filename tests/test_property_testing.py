from __future__ import annotations

import importlib.util
import inspect
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

from spec_test.contracts import ContractError, contract
from spec_test.decorators import get_spec_registry, spec, specs
from spec_test.property_testing import (
    PropertyConfigurationError,
    StrategyGenerationError,
    property_test,
)

requires_hypothesis = pytest.mark.skipif(
    importlib.util.find_spec("hypothesis") is None, reason="Hypothesis extra not installed"
)


@requires_hypothesis
@spec("HYP-001", "Property tests link to their declared specification ID")
def test_property_carries_spec_link_and_runner_evidence_kind():
    @property_test("PROP-001", "link this")
    def linked(value: bool):
        assert type(value) is bool

    assert linked._spec_id == "PROP-001"
    assert linked._spec_evidence_kind == "property"
    assert any(item["description"] == "link this" for item in get_spec_registry()["PROP-001"])
    assert ("spec_id", ("PROP-001",)) in {(m.name, m.args) for m in linked.pytestmark}
    linked()


@requires_hypothesis
@spec("HYP-002", "Forward dict or native settings to Hypothesis")
@pytest.mark.parametrize("native", [False, True])
def test_settings_are_forwarded(native):
    from hypothesis import settings

    values = []
    kwargs = {"max_examples": 5, "database": None, "derandomize": True}

    @property_test("PROP-002", settings=settings(**kwargs) if native else kwargs)
    def linked(value: int):
        values.append(value)

    linked()
    assert len(values) == 5


@requires_hypothesis
@spec("HYP-003", "Decorating preserves Python metadata")
def test_property_preserves_metadata_and_exposes_normal_test_signature():
    def original(value: int):
        """Original property documentation."""

    linked = property_test("PROP-003")(original)
    assert linked.__name__ == original.__name__
    assert linked.__qualname__ == original.__qualname__
    assert linked.__doc__ == original.__doc__
    assert linked.__module__ == original.__module__
    assert not inspect.signature(linked).parameters


@requires_hypothesis
@spec("HYP-004", "A decorated property executes as a real pytest test")
def test_pytest_falsifies_and_replays_an_explicit_example(tmp_path):
    test_file = tmp_path / "test_property_cli.py"
    test_file.write_text(
        """
from hypothesis import example, strategies as st
from spec_test.property_testing import property_test

@example(amount=2)
@property_test("PROP-004", strategies={"amount": st.just(0)})
def test_generated(amount):
    assert amount < 2
""",
        encoding="utf-8",
    )
    src = Path(__file__).resolve().parents[1] / "src"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(src), *sys.path[1:]])}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(test_file)],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "assert 2 < 2" in result.stdout


@requires_hypothesis
@spec("HYP-010", "Generate supported inputs from postponed type annotations")
def test_infers_named_primitive_strategies():
    @property_test("PROP-010", settings={"max_examples": 8, "derandomize": True})
    def generated(n: int, flag: bool, *, number: float, text: str, raw: bytes):
        assert type(n) is int
        assert type(flag) is bool
        assert type(number) is float and math.isfinite(number)
        assert type(text) is str
        assert type(raw) is bytes

    generated()


@requires_hypothesis
@spec("HYP-013", "Explicit named strategies override primitive inference")
def test_explicit_strategy_override_and_partial_inference():
    from hypothesis import strategies as st

    seen = []

    @property_test("PROP-013", strategies={"n": st.just(123), "items": st.just([])})
    def generated(n: int, items: list[int], flag: bool):
        assert n == 123
        assert items == []
        assert type(flag) is bool
        seen.append(flag)

    generated()
    assert set(seen) == {True, False}


@requires_hypothesis
@spec("HYP-015", "Unsupported annotations request an explicit strategy without evaluation")
def test_no_inference_through_arbitrary_annotation_expressions():
    def generated(source: unknown_annotation()):  # noqa: F821
        pass

    with pytest.raises(StrategyGenerationError, match="source.*provide strategies"):
        property_test("PROP-015")(generated)


@requires_hypothesis
@specs("HYP-020", "HYP-021", "HYP-022", "HYP-030", "HYP-031")
def test_contract_error_from_production_function_and_shrink():
    from hypothesis import strategies as st

    called = []

    @contract(requires=[lambda amount: amount >= 0], ensures=[lambda result: result < 5])
    def calculate(amount: int) -> int:
        called.append(amount)
        return amount

    @property_test(
        "PROP-021",
        strategies={"amount": st.integers(0, 60)},
        settings={"max_examples": 60, "derandomize": True},
    )
    def generated(amount):
        calculate(amount)

    with pytest.raises(ContractError) as error:
        generated()
    assert error.value.condition_type == "ensures"
    assert called[-1] == 5


@requires_hypothesis
@specs("HYP-032", "HYP-033")
def test_counterexample_is_reused_in_replay_only_session():
    from hypothesis import Phase, settings, strategies as st
    from hypothesis.database import InMemoryExampleDatabase

    def generator(database, phases, values):
        @property_test(
            "PROP-033",
            strategies={"value": st.integers(0, 60)},
            settings=settings(database=database, phases=phases, max_examples=60),
        )
        def generated(value):
            values.append(value)
            assert value < 5

        return generated

    database = InMemoryExampleDatabase()
    seen_first = []
    with pytest.raises(AssertionError):
        generator(database, [Phase.generate, Phase.shrink], seen_first)()
    assert seen_first[-1] == 5

    seen_replay = []
    with pytest.raises(AssertionError):
        generator(database, [Phase.reuse], seen_replay)()
    assert seen_replay[0] == 5


@spec("HYP-070", "Missing optional dependency reports the installation command")
def test_missing_hypothesis_extra_fails_with_help(monkeypatch):
    monkeypatch.setitem(sys.modules, "hypothesis", None)

    def generated(value: int):
        pass

    with pytest.raises(ImportError, match=r"pip install 'spec-test\[hypothesis\]'"):
        property_test("PROP-070")(generated)


@requires_hypothesis
@spec("HYP-071", "Misconfigured strategies and settings fail at definition")
@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"strategies": {"wrong": 4}}, "unknown parameters"),
        ({"strategies": {"value": 4}}, "must be a SearchStrategy"),
        ({"settings": {"max_examples": 0}}, "invalid Hypothesis configuration"),
        ({"settings": {"unknown": True}}, "invalid Hypothesis configuration"),
    ],
)
def test_bad_configuration(kwargs, message):
    def generated(value: int):
        pass

    with pytest.raises(PropertyConfigurationError, match=message):
        property_test("PROP-071", **kwargs)(generated)
