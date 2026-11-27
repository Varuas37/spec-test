"""Optional, spec-linked Hypothesis property tests."""

import inspect
import re
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from .decorators import spec

if TYPE_CHECKING:
    from hypothesis import settings as HypothesisSettings
    from hypothesis.strategies import SearchStrategy


class StrategyGenerationError(ValueError):
    """No strategy could be inferred for a parameter."""


class PropertyConfigurationError(ValueError):
    """A property test has an invalid declaration."""


def property_test(
    spec_id: str,
    description: str | None = None,
    *,
    strategies: Mapping[str, "SearchStrategy[Any]"] | None = None,
    settings: "HypothesisSettings | Mapping[str, Any] | None" = None,
) -> Callable[[Callable[..., None]], Callable[[], None]]:
    """Link a generated test to a spec, preserving Hypothesis's replay behavior.

    Explicit strategies override inference for named parameters. Without an
    override, each parameter needs a supported primitive annotation (int, bool,
    finite float, str or bytes). Pass native Hypothesis settings, or a mapping
    of its settings kwargs. This adapter supports synchronous tests with named,
    required generated parameters. Write the property as a test that calls
    the implementation, not as a decorator on the implementation itself.
    """
    if not isinstance(spec_id, str) or not re.fullmatch(r"[A-Z]+-[0-9]+", spec_id):
        raise PropertyConfigurationError("spec_id must look like QUEUE-001")
    if description is not None and (
        not isinstance(description, str) or not description.strip()
    ):
        raise PropertyConfigurationError("description must be a nonblank string")
    if strategies is not None and not isinstance(strategies, Mapping):
        raise PropertyConfigurationError("strategies must map parameter names to strategies")
    overrides = dict(strategies) if strategies is not None else {}
    configuration = dict(settings) if isinstance(settings, Mapping) else settings

    def decorate(func: Callable[..., None]) -> Callable[[], None]:
        try:
            from hypothesis import given, settings as hypothesis_settings
            from hypothesis import strategies as st
            from hypothesis.errors import InvalidArgument
        except ModuleNotFoundError as exc:
            if exc.name != "hypothesis":
                raise
            raise ImportError(
                "Property tests require Hypothesis. Install with: "
                "pip install 'spec-test[hypothesis]'"
            ) from exc

        if inspect.iscoroutinefunction(inspect.unwrap(func)):
            raise PropertyConfigurationError("property_test does not support async tests")
        if getattr(func, "is_hypothesis_test", False):
            raise PropertyConfigurationError(
                "property_test supplies @given; put explicit strategies in strategies="
            )
        parameters = inspect.signature(func).parameters
        if not parameters:
            raise PropertyConfigurationError("property_test needs at least one input parameter")

        unknown = overrides.keys() - parameters.keys()
        if unknown:
            names = ", ".join(sorted(map(repr, unknown)))
            raise PropertyConfigurationError(f"strategies name unknown parameters: {names}")

        # Compare raw annotations, including postponed builtin names, so inference
        # never evaluates arbitrary annotation expressions.
        primitives = (
            (int, st.integers),
            (bool, st.booleans),
            (float, lambda: st.floats(allow_nan=False, allow_infinity=False)),
            (str, st.text),
            (bytes, st.binary),
        )
        generated = {}
        for name, parameter in parameters.items():
            if (
                parameter.kind not in (parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
                or parameter.default is not parameter.empty
            ):
                raise PropertyConfigurationError(
                    f"property_test needs required named inputs; unsupported parameter {name!r}"
                )
            if name in overrides:
                override = overrides[name]
                if not isinstance(override, st.SearchStrategy):
                    raise PropertyConfigurationError(
                        f"strategy for {name!r} must be a SearchStrategy"
                    )
                generated[name] = override
                continue
            annotation = parameter.annotation
            for primitive, factory in primitives:
                if annotation is primitive or (
                    isinstance(annotation, str) and annotation == primitive.__name__
                ):
                    generated[name] = factory()
                    break
            else:
                raise StrategyGenerationError(
                    f"cannot infer a strategy for {name!r}; provide strategies={{'{name}': ...}}"
                )

        try:
            if configuration is None:
                active_settings = None
            elif isinstance(configuration, hypothesis_settings):
                active_settings = configuration
            elif isinstance(configuration, Mapping):
                active_settings = hypothesis_settings(**configuration)
            else:
                raise PropertyConfigurationError(
                    "settings must be a Hypothesis settings object or mapping"
                )

            # Keep the Hypothesis-generated callable outermost: Hypothesis's
            # @example, @seed and @reproduce_failure mutate that same callable.
            linked = spec(spec_id, description if description is not None else func.__name__)(func)
            test = given(**generated)(linked)
            if active_settings is not None:
                test = active_settings(test)
        except (InvalidArgument, TypeError) as exc:
            raise PropertyConfigurationError(f"invalid Hypothesis configuration: {exc}") from exc

        test.__qualname__ = func.__qualname__
        test._spec_id = linked._spec_id
        test._spec_description = linked._spec_description
        test._spec_notes = linked._spec_notes
        marks = list(getattr(test, "pytestmark", ()))
        test.pytestmark = marks + [mark for mark in linked.pytestmark if mark not in marks]
        test._spec_evidence_kind = "property"
        return test

    return decorate
