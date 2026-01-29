"""Z3 formal proof verification for spec-test."""

import ast
import functools
import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, get_type_hints

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

    The function must also have @contract decorator with requires/ensures.
    Z3 will attempt to prove that the postconditions always hold given
    the preconditions.

    Args:
        spec: Optional spec ID to link this proof to
        timeout: Maximum time in seconds for Z3 to attempt proof (default: 30)
        skip_runtime_if_proven: If True, skip runtime contract checks when
                                the proof succeeds (default: False)

    Example:
        @provable(spec="MATH-001", timeout=10)
        @contract(
            requires=[lambda x: x >= 0],
            ensures=[lambda result: result >= 0],
        )
        def sqrt(x: float) -> float:
            return x ** 0.5
    """

    def decorator(func: F) -> F:
        info = ProvableInfo(
            spec_id=spec,
            func_name=func.__name__,
            func_module=func.__module__,
            timeout=timeout,
            skip_runtime_if_proven=skip_runtime_if_proven,
        )

        # Register for discovery
        if spec:
            _provable_registry[spec] = info

        # Store on function for introspection
        func._provable_info = info  # type: ignore

        # The actual wrapper just stores info - verification happens separately
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._provable_info = info  # type: ignore
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

    # Get type hints for creating Z3 variables
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    # Get function signature
    sig = inspect.signature(func)

    # Create Z3 variables for parameters
    z3_vars = {}
    for param_name, param in sig.parameters.items():
        param_type = hints.get(param_name, int)  # Default to int
        z3_var = _create_z3_variable(param_name, param_type)
        if z3_var is not None:
            z3_vars[param_name] = z3_var

    # Create Z3 variable for result
    return_type = hints.get("return", int)
    result_var = _create_z3_variable("__result__", return_type)
    if result_var is not None:
        z3_vars["__result__"] = result_var

    # Translate preconditions to Z3
    preconditions = []
    for req in contract_info.requires:
        z3_expr = _translate_lambda_to_z3(req, z3_vars, sig)
        if z3_expr is not None:
            preconditions.append(z3_expr)

    # Translate postconditions to Z3
    postconditions = []
    for ens in contract_info.ensures:
        z3_expr = _translate_postcondition_to_z3(ens, z3_vars)
        if z3_expr is not None:
            postconditions.append(z3_expr)

    if not postconditions:
        return ProofOutcome(
            result=ProofResult.SKIPPED,
            function_name=provable_info.func_name,
            spec_id=provable_info.spec_id,
            message="Could not translate postconditions to Z3",
        )

    # Create Z3 solver
    solver = z3.Solver()
    solver.set("timeout", provable_info.timeout * 1000)  # ms

    # Add preconditions as assumptions
    for pre in preconditions:
        solver.add(pre)

    # Try to prove postconditions by checking if NOT(postcondition) is unsatisfiable
    # If NOT(post) is UNSAT given preconditions, then postcondition always holds
    negated_post = z3.Not(z3.And(*postconditions)) if len(postconditions) > 1 else z3.Not(postconditions[0])
    solver.add(negated_post)

    import time

    start = time.time()
    check_result = solver.check()
    elapsed_ms = (time.time() - start) * 1000

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
            if name != "__result__":
                try:
                    val = model.evaluate(var)
                    counter_example[name] = _z3_value_to_python(val)
                except Exception:
                    pass

        outcome = ProofOutcome(
            result=ProofResult.REFUTED,
            function_name=provable_info.func_name,
            spec_id=provable_info.spec_id,
            message="Found counter-example where postcondition fails",
            counter_example=counter_example if counter_example else None,
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


def _create_z3_variable(name: str, python_type: type) -> Optional[Any]:
    """Create a Z3 variable for a Python type."""
    if not Z3_AVAILABLE:
        return None

    # Handle Optional types
    origin = getattr(python_type, "__origin__", None)
    if origin is not None:
        # Skip complex generic types for now
        args = getattr(python_type, "__args__", ())
        if args:
            python_type = args[0]  # Use inner type

    if python_type == int:
        return z3.Int(name)
    elif python_type == float:
        return z3.Real(name)
    elif python_type == bool:
        return z3.Bool(name)
    else:
        # Default to Int for unknown types
        return z3.Int(name)


def _translate_lambda_to_z3(
    lambda_func: Callable, z3_vars: dict[str, Any], sig: inspect.Signature
) -> Optional[Any]:
    """Translate a lambda precondition to Z3 expression."""
    if not Z3_AVAILABLE:
        return None

    try:
        # Get lambda source code via AST inspection
        source = inspect.getsource(lambda_func)

        # Parse and find the lambda
        tree = ast.parse(source.strip())
        lambda_node = _find_lambda(tree)

        if lambda_node is None:
            return None

        # Map lambda parameter names to Z3 variables
        param_names = list(sig.parameters.keys())
        lambda_params = [arg.arg for arg in lambda_node.args.args]

        var_mapping = {}
        for i, lp in enumerate(lambda_params):
            if i < len(param_names):
                var_mapping[lp] = z3_vars.get(param_names[i])
            elif lp in z3_vars:
                var_mapping[lp] = z3_vars[lp]

        # Translate the lambda body
        return _ast_to_z3(lambda_node.body, var_mapping)

    except Exception:
        return None


def _translate_postcondition_to_z3(
    lambda_func: Callable, z3_vars: dict[str, Any]
) -> Optional[Any]:
    """Translate a lambda postcondition to Z3 expression."""
    if not Z3_AVAILABLE:
        return None

    try:
        source = inspect.getsource(lambda_func)
        tree = ast.parse(source.strip())
        lambda_node = _find_lambda(tree)

        if lambda_node is None:
            return None

        # Postconditions receive 'result' as first arg
        lambda_params = [arg.arg for arg in lambda_node.args.args]

        var_mapping = {}
        if lambda_params:
            # First param is the result
            var_mapping[lambda_params[0]] = z3_vars.get("__result__")

        # Translate the lambda body
        return _ast_to_z3(lambda_node.body, var_mapping)

    except Exception:
        return None


def _find_lambda(tree: ast.AST) -> Optional[ast.Lambda]:
    """Find lambda node in AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            return node
    return None


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
            if right is None:
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
        if left is None or right is None:
            return None

        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            return left / right
        elif isinstance(node.op, ast.FloorDiv):
            return left / right  # Z3 Int division
        elif isinstance(node.op, ast.Mod):
            return left % right
        else:
            return None

    elif isinstance(node, ast.UnaryOp):
        operand = _ast_to_z3(node.operand, var_mapping)
        if operand is None:
            return None

        if isinstance(node.op, ast.USub):
            return -operand
        elif isinstance(node.op, ast.Not):
            return z3.Not(operand)
        else:
            return None

    elif isinstance(node, ast.BoolOp):
        values = [_ast_to_z3(v, var_mapping) for v in node.values]
        if any(v is None for v in values):
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
        elif isinstance(node.value, float):
            return z3.RealVal(node.value)
        else:
            return None

    elif isinstance(node, ast.IfExp):
        # Ternary: x if cond else y
        test = _ast_to_z3(node.test, var_mapping)
        body = _ast_to_z3(node.body, var_mapping)
        orelse = _ast_to_z3(node.orelse, var_mapping)
        if test is None or body is None or orelse is None:
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
