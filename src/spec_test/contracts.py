"""Runtime contract enforcement for spec-test."""

import asyncio
import functools
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar, Union

# Type for contract conditions
Condition = Callable[..., bool]

# Global registry for contracts by spec ID
_contract_registry: dict[str, "ContractInfo"] = {}


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
    func_name: str
    func_module: str

    @property
    def full_name(self) -> str:
        return f"{self.func_module}.{self.func_name}"


F = TypeVar("F", bound=Callable[..., Any])


def contract(
    spec: Optional[str] = None,
    requires: Optional[list[Condition]] = None,
    ensures: Optional[list[Condition]] = None,
) -> Callable[[F], F]:
    """
    Decorator to add runtime contract checking to a function.

    Args:
        spec: Optional spec ID to link this contract to
        requires: List of precondition callables, each receives function args
        ensures: List of postcondition callables, each receives function result

    Example:
        @contract(
            spec="AUTH-001",
            requires=[lambda email, password: "@" in email],
            ensures=[lambda result: result is not None],
        )
        def login(email: str, password: str) -> Token:
            ...
    """
    requires = requires or []
    ensures = ensures or []

    def decorator(func: F) -> F:
        # Store contract info
        info = ContractInfo(
            spec_id=spec,
            requires=requires,
            ensures=ensures,
            func_name=func.__name__,
            func_module=func.__module__,
        )

        # Register if spec ID provided
        if spec:
            _contract_registry[spec] = info

        # Store on function for introspection
        func._contract_info = info  # type: ignore

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Check preconditions
                _check_requires(info, args, kwargs)

                # Call function
                result = await func(*args, **kwargs)

                # Check postconditions
                _check_ensures(info, result)

                return result

            return async_wrapper  # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Check preconditions
                _check_requires(info, args, kwargs)

                # Call function
                result = func(*args, **kwargs)

                # Check postconditions
                _check_ensures(info, result)

                return result

            return sync_wrapper  # type: ignore

    return decorator


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


def _check_ensures(info: ContractInfo, result: Any) -> None:
    """Check all postconditions."""
    for i, condition in enumerate(info.ensures):
        try:
            check = condition(result)
            if not check:
                raise ContractError(
                    f"Postcondition {i} failed for {info.full_name}",
                    spec_id=info.spec_id,
                    condition_type="ensures",
                    condition_index=i,
                )
        except TypeError as e:
            raise ContractError(
                f"Postcondition {i} raised error for {info.full_name}: {e}",
                spec_id=info.spec_id,
                condition_type="ensures",
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
