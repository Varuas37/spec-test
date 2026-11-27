"""Z3 formal proof verification for spec-test."""

import ast
import functools
import inspect
import textwrap
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

# Try to import z3, provide helpful error if not installed
try:
    import z3

    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False
    z3 = None  # type: ignore


class ProofResult(Enum):
    """Result of Z3 proof verification."""

    PROVEN = "proven"  # Z3 proved the property holds for all inputs
    REFUTED = "refuted"  # Z3 found a counter-example
    UNKNOWN = "unknown"  # Z3 could not determine (timeout, complexity)
    SKIPPED = "skipped"  # Verification was skipped (no Z3, unsupported)


@dataclass
class ProofOutcome:
    """Detailed outcome of a proof attempt."""

    result: ProofResult
    spec_id: Optional[str] = None
    function_name: str = ""
    message: str = ""
    counter_example: Optional[dict[str, Any]] = None
    proof_time_ms: float = 0.0


@dataclass
class ProvableInfo:
    """Information about a provable function."""

    spec_id: Optional[str]
    func_name: str
    func_module: str
    timeout: int
    skip_runtime_if_proven: bool
    proof_outcome: Optional[ProofOutcome] = None
    function: Optional[Callable] = field(default=None, repr=False, compare=False)

    @property
    def full_name(self) -> str:
        return f"{self.func_module}.{self.func_name}"


# Global registry for provable functions
_provable_registry: dict[str, ProvableInfo] = {}

F = TypeVar("F", bound=Callable[..., Any])


def provable(
    spec: Optional[str] = None,
    timeout: int = 30,
    skip_runtime_if_proven: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to mark a function for Z3 formal verification.

    Place this outside @contract. Z3 checks postconditions on the return
    expression for the supported int/bool subset and declared preconditions.

    Args:
        spec: Optional spec ID to link this proof to
        timeout: Maximum time in seconds for Z3 to attempt proof (default: 30)
        skip_runtime_if_proven: Reserved; proofs never disable runtime checks.

    Example:
        @provable(spec="MATH-001", timeout=10)
        @contract(
            requires=[lambda x: x >= 0],
            ensures=[lambda result: result >= 0],
        )
        def successor(x: int) -> int:
            return x + 1
    """

    if type(timeout) is not int or timeout < 1 or timeout > (2**32 - 1) // 1000:
        raise ValueError("timeout must be a positive integer within the solver's limit")

    def decorator(func: F) -> F:
        info = ProvableInfo(
            spec_id=spec,
            func_name=func.__name__,
            func_module=func.__module__,
            timeout=timeout,
            skip_runtime_if_proven=skip_runtime_if_proven,
        )

        # Store on function for introspection
        func._provable_info = info  # type: ignore

        # The actual wrapper just stores info - verification happens separately
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._provable_info = info  # type: ignore
        info.function = wrapper
        if spec:
            if spec in _provable_registry:
                raise ValueError(f"Duplicate proof spec ID: {spec}")
            _provable_registry[spec] = info
        return wrapper  # type: ignore

    return decorator


def get_provable_registry() -> dict[str, ProvableInfo]:
    """Get a copy of the provable function registry."""
    return _provable_registry.copy()


def get_provable_for_spec(spec_id: str) -> Optional[ProvableInfo]:
    """Get provable info for a specific spec ID."""
    return _provable_registry.get(spec_id)


def clear_provable_registry() -> None:
    """Clear the provable registry (useful for testing)."""
    _provable_registry.clear()


def verify_function(func: Callable) -> ProofOutcome:
    """
    Attempt to formally verify a function using Z3.

    Args:
        func: A function decorated with @provable and @contract

    Returns:
        ProofOutcome with the verification result
    """
    if not Z3_AVAILABLE:
        return ProofOutcome(
            result=ProofResult.SKIPPED,
            function_name=getattr(func, "__name__", "unknown"),
            message="Z3 not installed. Install with: pip install spec-test[z3]",
        )

    # Get provable info
    provable_info = getattr(func, "_provable_info", None)
    if provable_info is None:
        return ProofOutcome(
            result=ProofResult.SKIPPED,
            function_name=getattr(func, "__name__", "unknown"),
            message="Function not marked with @provable",
        )

    # Get contract info
    contract_info = getattr(func, "_contract_info", None)
    if contract_info is None:
        return ProofOutcome(
            result=ProofResult.SKIPPED,
            function_name=provable_info.func_name,
            spec_id=provable_info.spec_id,
            message="Function has no @contract - nothing to prove",
        )

    def skipped(message: str) -> ProofOutcome:
        outcome = ProofOutcome(
            ProofResult.SKIPPED, provable_info.spec_id, provable_info.func_name, message
        )
        provable_info.proof_outcome = outcome
        return outcome

    if contract_info.invariants or contract_info.capture_old:
        return skipped("Invariants and old-state contracts are not supported by proofs")

    try:
        original = _proof_body(func)
        sig = inspect.signature(original)
        z3_vars = {}
        for name, param in sig.parameters.items():
            if param.kind not in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
                raise ValueError("Only positional parameters are supported")
            z3_vars[name] = _create_z3_variable(name, param.annotation)
        result = _translate_return(original, z3_vars)
        expected = _create_z3_variable("expected_return_sort", sig.return_annotation)
        if not result.sort().eq(expected.sort()):
            raise ValueError("Return expression does not match declared type")

        preconditions = [
            _translate_predicate(cond, z3_vars, match_names=True)
            for cond in contract_info.requires
        ]
        if not contract_info.ensures:
            raise ValueError("No postconditions to prove")
        postconditions = [
            _translate_predicate(cond, {"result": result})
            for cond in contract_info.ensures
        ]
    except (TypeError, ValueError, OSError, SyntaxError, z3.Z3Exception) as exc:
        return skipped(f"Unsupported proof: {exc}")

    # Create Z3 solver
    solver = z3.Solver()
    solver.set("timeout", provable_info.timeout * 1000)  # ms

    solver.add(*preconditions)
    start = time.monotonic()
    domain = solver.check()
    if domain == z3.unsat:
        return skipped("Preconditions are unsatisfiable; no valid inputs")
    if domain == z3.sat:
        # The solver timeout is shared between the two checks.
        remaining = provable_info.timeout * 1000 - (time.monotonic() - start) * 1000
        if remaining >= 1:
            solver.set("timeout", int(remaining))
            solver.add(z3.Not(z3.And(*postconditions)))
            check_result = solver.check()
        else:
            check_result = z3.unknown
    else:
        check_result = z3.unknown
    elapsed_ms = (time.monotonic() - start) * 1000

    if check_result == z3.unsat:
        # NOT(postcondition) is unsatisfiable - proof succeeded!
        outcome = ProofOutcome(
            result=ProofResult.PROVEN,
            function_name=provable_info.func_name,
            spec_id=provable_info.spec_id,
            message="Postconditions proven to hold for all valid inputs",
            proof_time_ms=elapsed_ms,
        )
        provable_info.proof_outcome = outcome
        return outcome

    elif check_result == z3.sat:
        # Found a counter-example where postcondition fails
        model = solver.model()
        counter_example = {}
        for name, var in z3_vars.items():
            counter_example[name] = _z3_value_to_python(
                model.evaluate(var, model_completion=True)
            )

        outcome = ProofOutcome(
            result=ProofResult.REFUTED,
            function_name=provable_info.func_name,
            spec_id=provable_info.spec_id,
            message="Found counter-example where postcondition fails",
            counter_example=counter_example,
            proof_time_ms=elapsed_ms,
        )
        provable_info.proof_outcome = outcome
        return outcome

    else:
        # Unknown (timeout or too complex)
        outcome = ProofOutcome(
            result=ProofResult.UNKNOWN,
            function_name=provable_info.func_name,
            spec_id=provable_info.spec_id,
            message="Z3 could not determine - try increasing timeout or simplifying constraints",
            proof_time_ms=elapsed_ms,
        )
        provable_info.proof_outcome = outcome
        return outcome


def _create_z3_variable(name: str, python_type: Any) -> Any:
    """Model only exact Python int/bool values."""
    if python_type is int or python_type == "int":
        return z3.Int(name)
    if python_type is bool or python_type == "bool":
        return z3.Bool(name)
    raise ValueError("Explicit int or bool annotations are required")


def _proof_body(func: Callable) -> Callable:
    # Prove the implementation under our two decorators, not one hidden
    # behind another decorator that might change its behavior.
    from .contracts import contract

    runtime = getattr(func, "__wrapped__", None)
    original = getattr(runtime, "__wrapped__", None)
    if (
        getattr(func, "__globals__", None) is not globals()
        or getattr(getattr(func, "__code__", None), "co_qualname", "")
        != "provable.<locals>.decorator.<locals>.wrapper"
        or getattr(runtime, "__globals__", None) is not contract.__globals__
        or getattr(getattr(runtime, "__code__", None), "co_qualname", "")
        != "contract.<locals>.decorator.<locals>.sync_wrapper"
        or not inspect.isfunction(original)
        or hasattr(original, "__wrapped__")
    ):
        raise ValueError("Expected @provable outside a synchronous @contract")
    return original


def _translate_return(func: Callable, variables: dict[str, Any]) -> Any:
    if func.__code__.co_freevars:
        raise ValueError("Closures are not supported")
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ValueError("Expected a top-level function in the inspected source")
    body = tree.body[0].body[:]
    if (
        body and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
    if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
        raise ValueError("Expected a single return expression")
    result = _ast_to_z3(body[0].value, variables)
    if result is None:
        raise ValueError("Cannot model the return expression")
    return result


def _translate_predicate(
    func: Callable, variables: dict[str, Any], *, match_names: bool = False
) -> Any:
    if not inspect.isfunction(func) or func.__name__ != "<lambda>" or func.__code__.co_freevars:
        raise ValueError("Expected a lambda without captured values")
    params = list(inspect.signature(func).parameters.values())
    if len(params) != len(variables) or any(
        p.kind != p.POSITIONAL_OR_KEYWORD or p.default is not p.empty for p in params
    ):
        raise ValueError("Predicate parameters do not match the contract")
    if match_names and [p.name for p in params] != list(variables):
        raise ValueError("Precondition parameter names must match the function")

    # Full module source handles multiple lambdas on one line and multiline
    # predicates. Match the actual code-object span, never the first lambda.
    source, _ = inspect.findsource(func)
    tree = ast.parse("".join(source))
    spans = set(func.__code__.co_positions())
    matches = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Lambda) and node.lineno == func.__code__.co_firstlineno
        and (node.body.lineno, node.body.end_lineno,
             node.body.col_offset, node.body.end_col_offset) in spans
    ]
    if len(matches) != 1:
        raise ValueError("Cannot identify the exact predicate lambda")
    mapping = {p.name: value for p, value in zip(params, variables.values())}
    predicate = _ast_to_z3(matches[0].body, mapping)
    if not z3.is_bool(predicate):
        raise ValueError("Predicate must be a supported Boolean expression")
    return predicate


def _ast_to_z3(node: ast.AST, var_mapping: dict[str, Any]) -> Optional[Any]:
    """Convert Python AST to Z3 expression."""
    if not Z3_AVAILABLE:
        return None

    if isinstance(node, ast.Compare):
        # Handle comparisons: x > 0, x == y, etc.
        left = _ast_to_z3(node.left, var_mapping)
        if left is None:
            return None

        results = []
        current = left
        for op, comparator in zip(node.ops, node.comparators):
            right = _ast_to_z3(comparator, var_mapping)
            if right is None or not current.sort().eq(right.sort()):
                return None
            if not isinstance(op, (ast.Eq, ast.NotEq)) and not z3.is_int(current):
                return None

            if isinstance(op, ast.Gt):
                results.append(current > right)
            elif isinstance(op, ast.GtE):
                results.append(current >= right)
            elif isinstance(op, ast.Lt):
                results.append(current < right)
            elif isinstance(op, ast.LtE):
                results.append(current <= right)
            elif isinstance(op, ast.Eq):
                results.append(current == right)
            elif isinstance(op, ast.NotEq):
                results.append(current != right)
            else:
                return None

            current = right

        return z3.And(*results) if len(results) > 1 else results[0]

    elif isinstance(node, ast.BinOp):
        # Handle binary operations: +, -, *, /, etc.
        left = _ast_to_z3(node.left, var_mapping)
        right = _ast_to_z3(node.right, var_mapping)
        if not z3.is_int(left) or not z3.is_int(right):
            return None

        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        else:
            return None

    elif isinstance(node, ast.UnaryOp):
        operand = _ast_to_z3(node.operand, var_mapping)
        if operand is None:
            return None

        if isinstance(node.op, ast.USub) and z3.is_int(operand):
            return -operand
        elif isinstance(node.op, ast.Not) and z3.is_bool(operand):
            return z3.Not(operand)
        else:
            return None

    elif isinstance(node, ast.BoolOp):
        values = [_ast_to_z3(v, var_mapping) for v in node.values]
        if not all(z3.is_bool(v) for v in values):
            return None

        if isinstance(node.op, ast.And):
            return z3.And(*values)
        elif isinstance(node.op, ast.Or):
            return z3.Or(*values)
        else:
            return None

    elif isinstance(node, ast.Name):
        # Variable reference
        return var_mapping.get(node.id)

    elif isinstance(node, ast.Constant):
        # Literal value
        if isinstance(node.value, bool):
            return z3.BoolVal(node.value)
        elif isinstance(node.value, int):
            return z3.IntVal(node.value)
        else:
            return None

    elif isinstance(node, ast.IfExp):
        # Ternary: x if cond else y
        test = _ast_to_z3(node.test, var_mapping)
        body = _ast_to_z3(node.body, var_mapping)
        orelse = _ast_to_z3(node.orelse, var_mapping)
        if (not z3.is_bool(test) or body is None or orelse is None
            or not body.sort().eq(orelse.sort())):
            return None
        return z3.If(test, body, orelse)

    else:
        return None


def _z3_value_to_python(val: Any) -> Any:
    """Convert Z3 value to Python value."""
    if not Z3_AVAILABLE:
        return None

    try:
        if z3.is_int_value(val):
            return val.as_long()
        elif z3.is_rational_value(val):
            return float(val.as_fraction())
        elif z3.is_true(val):
            return True
        elif z3.is_false(val):
            return False
        else:
            return str(val)
    except Exception:
        return str(val)
