"""Runtime contract enforcement for spec-test."""

import asyncio
import copy
import functools
import inspect
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar, Union

# Type for contract conditions
Condition = Callable[..., bool]

# Global registry for contracts by spec ID
_contract_registry: dict[str, "ContractInfo"] = {}

# Context variable to store old values for postcondition checking
_old_values: ContextVar[dict[str, Any]] = ContextVar("old_values", default={})


class Old:
    """
    Captures pre-state values for use in postconditions.

    Usage in postconditions:
        @contract(
            ensures=[lambda result, old: old.x < result]
        )
        def increment(x: int) -> int:
            return x + 1

    The `old` parameter in postconditions provides access to captured argument values.
    """

    def __init__(self, captured: dict[str, Any]):
        self._captured = captured

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        if name not in self._captured:
            raise AttributeError(f"'{name}' was not captured. Available: {list(self._captured.keys())}")
        return self._captured[name]

    def get(self, name: str, default: Any = None) -> Any:
        """Get a captured value with optional default."""
        return self._captured.get(name, default)


class ContractError(Exception):
    """Raised when a contract condition fails."""

    def __init__(
        self,
        message: str,
        spec_id: Optional[str] = None,
        condition_type: str = "unknown",
        condition_index: int = 0,
    ):
        self.spec_id = spec_id
        self.condition_type = condition_type
        self.condition_index = condition_index
        super().__init__(message)


@dataclass
class ContractInfo:
    """Information about a contract attached to a function."""

    spec_id: Optional[str]
    requires: list[Condition]
    ensures: list[Condition]
    invariants: list[Condition]
    func_name: str
    func_module: str
    capture_old: bool = False  # Whether to capture args for old() in postconditions

    @property
    def full_name(self) -> str:
        return f"{self.func_module}.{self.func_name}"


F = TypeVar("F", bound=Callable[..., Any])


def contract(
    spec: Optional[str] = None,
    requires: Optional[list[Condition]] = None,
    ensures: Optional[list[Condition]] = None,
    invariants: Optional[list[Condition]] = None,
    capture_old: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to add runtime contract checking to a function.

    Args:
        spec: Optional spec ID to link this contract to
        requires: List of precondition callables, each receives function args
        ensures: List of postcondition callables, each receives function result
                 If capture_old=True, receives (result, old) where old has captured args
        invariants: List of invariant callables, checked before AND after execution
                    Each receives function args
        capture_old: If True, captures deep copies of args before execution for use in
                     postconditions via the `old` parameter

    Example:
        @contract(
            spec="AUTH-001",
            requires=[lambda email, password: "@" in email],
            ensures=[lambda result: result is not None],
            invariants=[lambda email, password: len(password) >= 8],
        )
        def login(email: str, password: str) -> Token:
            ...

    Example with old() for comparing pre/post state:
        @contract(
            spec="LIST-001",
            capture_old=True,
            ensures=[lambda result, old: len(result) == len(old.items) + 1],
        )
        def append_item(items: list, item) -> list:
            return items + [item]
    """
    requires = requires or []
    ensures = ensures or []
    invariants = invariants or []

    def decorator(func: F) -> F:
        # Store contract info
        info = ContractInfo(
            spec_id=spec,
            requires=requires,
            ensures=ensures,
            invariants=invariants,
            func_name=func.__name__,
            func_module=func.__module__,
            capture_old=capture_old,
        )

        # Register if spec ID provided
        if spec:
            _contract_registry[spec] = info

        # Store on function for introspection
        func._contract_info = info  # type: ignore

        # Get function signature for capturing old values
        sig = inspect.signature(func)

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Capture old values if needed
                old = _capture_old_values(info, sig, args, kwargs) if info.capture_old else None

                # Check preconditions
                _check_requires(info, args, kwargs)

                # Check invariants before
                _check_invariants(info, args, kwargs, "before")

                # Call function
                result = await func(*args, **kwargs)

                # Check invariants after
                _check_invariants(info, args, kwargs, "after")

                # Check postconditions
                _check_ensures(info, result, old)

                return result

            return async_wrapper  # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Capture old values if needed
                old = _capture_old_values(info, sig, args, kwargs) if info.capture_old else None

                # Check preconditions
                _check_requires(info, args, kwargs)

                # Check invariants before
                _check_invariants(info, args, kwargs, "before")

                # Call function
                result = func(*args, **kwargs)

                # Check invariants after
                _check_invariants(info, args, kwargs, "after")

                # Check postconditions
                _check_ensures(info, result, old)

                return result

            return sync_wrapper  # type: ignore

    return decorator


def _capture_old_values(
    info: ContractInfo, sig: inspect.Signature, args: tuple, kwargs: dict
) -> Old:
    """Capture deep copies of arguments for old() access in postconditions."""
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()

    captured = {}
    for name, value in bound.arguments.items():
        try:
            captured[name] = copy.deepcopy(value)
        except Exception:
            # If we can't deepcopy, store the original (may be mutated)
            captured[name] = value

    return Old(captured)


def _check_requires(info: ContractInfo, args: tuple, kwargs: dict) -> None:
    """Check all preconditions."""
    for i, condition in enumerate(info.requires):
        try:
            # Get function signature to bind args properly
            result = condition(*args, **kwargs)
            if not result:
                raise ContractError(
                    f"Precondition {i} failed for {info.full_name}",
                    spec_id=info.spec_id,
                    condition_type="requires",
                    condition_index=i,
                )
        except TypeError as e:
            # Condition signature doesn't match - try with just args
            try:
                result = condition(*args)
                if not result:
                    raise ContractError(
                        f"Precondition {i} failed for {info.full_name}",
                        spec_id=info.spec_id,
                        condition_type="requires",
                        condition_index=i,
                    )
            except Exception:
                raise ContractError(
                    f"Precondition {i} raised error for {info.full_name}: {e}",
                    spec_id=info.spec_id,
                    condition_type="requires",
                    condition_index=i,
                ) from e


def _check_ensures(info: ContractInfo, result: Any, old: Optional[Old] = None) -> None:
    """Check all postconditions."""
    for i, condition in enumerate(info.ensures):
        try:
            # Try with (result, old) first if old is provided
            if old is not None:
                try:
                    check = condition(result, old)
                except TypeError:
                    # Fall back to just result
                    check = condition(result)
            else:
                check = condition(result)

            if not check:
                raise ContractError(
                    f"Postcondition {i} failed for {info.full_name}",
                    spec_id=info.spec_id,
                    condition_type="ensures",
                    condition_index=i,
                )
        except ContractError:
            raise
        except TypeError as e:
            raise ContractError(
                f"Postcondition {i} raised error for {info.full_name}: {e}",
                spec_id=info.spec_id,
                condition_type="ensures",
                condition_index=i,
            ) from e


def _check_invariants(info: ContractInfo, args: tuple, kwargs: dict, when: str) -> None:
    """Check all invariants (before or after execution)."""
    for i, condition in enumerate(info.invariants):
        try:
            result = condition(*args, **kwargs)
            if not result:
                raise ContractError(
                    f"Invariant {i} failed {when} execution for {info.full_name}",
                    spec_id=info.spec_id,
                    condition_type="invariant",
                    condition_index=i,
                )
        except ContractError:
            raise
        except TypeError:
            # Try with just args
            try:
                result = condition(*args)
                if not result:
                    raise ContractError(
                        f"Invariant {i} failed {when} execution for {info.full_name}",
                        spec_id=info.spec_id,
                        condition_type="invariant",
                        condition_index=i,
                    )
            except ContractError:
                raise
            except Exception as e:
                raise ContractError(
                    f"Invariant {i} raised error {when} execution for {info.full_name}: {e}",
                    spec_id=info.spec_id,
                    condition_type="invariant",
                    condition_index=i,
                ) from e


def get_contract_registry() -> dict[str, ContractInfo]:
    """Get a copy of the contract registry."""
    return _contract_registry.copy()


def get_contract_for_spec(spec_id: str) -> Optional[ContractInfo]:
    """Get contract info for a specific spec ID."""
    return _contract_registry.get(spec_id)


def clear_contract_registry() -> None:
    """Clear the contract registry (useful for testing)."""
    _contract_registry.clear()
