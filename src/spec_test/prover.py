"""Z3 formal proof verification for spec-test."""

import ast
import functools
import inspect
import time
from dataclasses import dataclass, field
from enum import Enum
from types import CodeType
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
    expression for the supported int/bool subset and declared preconditions. The proof
    also checks that no reachable arithmetic expression divides by zero.

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
        expected = _create_z3_variable("expected_return_sort", sig.return_annotation)
        result = _translate_return(original, z3_vars, expected.sort())

        preconditions = [
            _translate_predicate(cond, z3_vars, match_names=True)
            for cond in contract_info.requires
        ]
        if not contract_info.ensures:
            raise ValueError("No postconditions to prove")
        postconditions = [
            _translate_predicate(cond, {"result": result.value})
            for cond in contract_info.ensures
        ]
    except (TypeError, ValueError, OSError, SyntaxError, RecursionError, z3.Z3Exception) as exc:
        return skipped(f"Unsupported proof: {exc}")

    # Preconditions run in order: a false condition rejects the call, while
    # an undefined condition is a runtime error even if a later one is false.
    reachable = z3.BoolVal(True)
    failures = []
    for index, condition in enumerate(preconditions, 1):
        failures.append((
            f"Precondition {index} can divide by zero",
            z3.And(reachable, z3.Not(condition.defined)),
        ))
        reachable = z3.And(reachable, condition.defined, condition.value)
    domain = reachable

    failures.append((
        "Function body can divide by zero",
        z3.And(reachable, z3.Not(result.defined)),
    ))
    reachable = z3.And(reachable, result.defined)
    for index, condition in enumerate(postconditions, 1):
        failures.extend((
            (f"Postcondition {index} can divide by zero",
             z3.And(reachable, z3.Not(condition.defined))),
            (f"Postcondition {index} fails",
             z3.And(reachable, condition.defined, z3.Not(condition.value))),
        ))
        reachable = z3.And(reachable, condition.defined, condition.value)

    solver = z3.Solver()
    start = time.monotonic()
    unknown_reason = ""

    def check(goal: Any) -> Any:
        nonlocal unknown_reason
        remaining = provable_info.timeout * 1000 - (time.monotonic() - start) * 1000
        if remaining < 1:
            unknown_reason = "shared proof timeout expired"
            return z3.unknown
        solver.set("timeout", int(remaining))
        checked = solver.check(goal)
        if checked == z3.unknown:
            unknown_reason = solver.reason_unknown()
        return checked

    def outcome(
        status: ProofResult, message: str, witness: Optional[dict[str, Any]] = None
    ) -> ProofOutcome:
        result = ProofOutcome(
            result=status,
            function_name=provable_info.func_name,
            spec_id=provable_info.spec_id,
            message=message,
            counter_example=witness,
            proof_time_ms=(time.monotonic() - start) * 1000,
        )
        provable_info.proof_outcome = result
        return result

    failure_check = check(z3.Or(*(reason for _, reason in failures)))
    if failure_check == z3.sat:
        model = solver.model()
        witness = {
            name: _z3_value_to_python(model.evaluate(var, model_completion=True))
            for name, var in z3_vars.items()
        }
        for message, reason in failures:
            if z3.is_true(model.evaluate(reason, model_completion=True)):
                return outcome(ProofResult.REFUTED, message, witness)
        return outcome(ProofResult.UNKNOWN, "Could not classify the solver counterexample")

    if failure_check == z3.unsat:
        domain_check = check(domain)
        if domain_check == z3.sat:
            return outcome(ProofResult.PROVEN, "Postconditions proven to hold for all valid inputs")
        if domain_check == z3.unsat:
            return outcome(ProofResult.SKIPPED, "Preconditions are unsatisfiable; no valid inputs")

    return outcome(
        ProofResult.UNKNOWN,
        f"Z3 could not determine: {unknown_reason or 'solver returned unknown'}",
    )


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


@dataclass(frozen=True)
class _Expression:
    """A symbolic value paired with the condition under which Python computes it."""

    value: Any
    defined: Any


def _strict(value: Any, *args: _Expression) -> _Expression:
    return _Expression(value, z3.And(*(arg.defined for arg in args)) if args else z3.BoolVal(True))


def _conditional(test: _Expression, yes: _Expression, no: _Expression) -> _Expression:
    return _Expression(
        z3.If(test.value, yes.value, no.value),
        z3.And(test.defined, z3.If(test.value, yes.defined, no.defined)),
    )


def _same_loaded_code(candidate: CodeType, loaded: CodeType) -> bool:
    # Names, argument binding and typed constants matter even when the raw
    # instruction bytes are equal (e.g. return 1 versus return True).
    fields = (
        "co_code", "co_names", "co_varnames", "co_argcount", "co_posonlyargcount",
        "co_kwonlyargcount", "co_flags", "co_freevars", "co_cellvars", "co_exceptiontable",
    )
    return (
        all(getattr(candidate, field) == getattr(loaded, field) for field in fields)
        and len(candidate.co_consts) == len(loaded.co_consts)
        and all(
            type(a) is type(b) and a == b
            for a, b in zip(candidate.co_consts, loaded.co_consts)
        )
    )


def _loaded_ast(func: Callable) -> ast.Module:
    """Parse source only if it still describes the live function or lambda."""
    source, _ = inspect.findsource(func)
    loaded = func.__code__
    tree = ast.parse("".join(source), filename=loaded.co_filename)
    compiled = compile(tree, loaded.co_filename, "exec", dont_inherit=True)
    todo = [compiled]
    matches = 0
    while todo:
        code = todo.pop()
        if (
            code.co_qualname == loaded.co_qualname
            and code.co_firstlineno == loaded.co_firstlineno
            and tuple(code.co_positions()) == tuple(loaded.co_positions())
            and _same_loaded_code(code, loaded)
        ):
            matches += 1
        todo.extend(c for c in code.co_consts if isinstance(c, CodeType))
    if matches != 1:
        raise ValueError("Inspected source does not uniquely match the loaded Python code")
    return tree


def _translate_return(
    func: Callable, variables: dict[str, Any], expected_sort: Any
) -> _Expression:
    if func.__code__.co_freevars:
        raise ValueError("Closures are not supported")
    tree = _loaded_ast(func)
    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == func.__name__
        and min([node.lineno, *(d.lineno for d in node.decorator_list)])
        == func.__code__.co_firstlineno
    ]
    if len(functions) != 1:
        raise ValueError("Cannot identify the exact implementation definition")
    body = functions[0].body[:]
    if (
        body and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
    result = _translate_block(body, variables, expected_sort, continuation=None)
    if result is None:
        raise ValueError("A control path falls through without a return")
    return result


def _translate_block(
    body: list[ast.stmt],
    variables: dict[str, Any],
    expected_sort: Any,
    continuation: Optional[_Expression],
) -> Optional[_Expression]:
    """Fold a pure block over what runs if it does not return itself."""
    result = continuation
    for statement in reversed(body):
        if isinstance(statement, ast.Return):
            result = _ast_to_z3(statement.value, variables)
            if result is None:
                raise ValueError("Cannot model the return expression")
            if not result.value.sort().eq(expected_sort):
                raise ValueError("Return expression does not match declared type")
        elif isinstance(statement, ast.If):
            test = _ast_to_z3(statement.test, variables)
            if test is None or not z3.is_bool(test.value):
                raise ValueError("Only supported boolean branch conditions can be modeled")
            yes = _translate_block(statement.body, variables, expected_sort, result)
            no = _translate_block(statement.orelse, variables, expected_sort, result)
            if yes is None or no is None:
                raise ValueError("A control path falls through without a return")
            result = _conditional(test, yes, no)
        else:
            raise ValueError(f"Cannot model statement: {type(statement).__name__}")
    return result


def _translate_predicate(
    func: Callable, variables: dict[str, Any], *, match_names: bool = False
) -> _Expression:
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
    tree = _loaded_ast(func)
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
    if predicate is None or not z3.is_bool(predicate.value):
        raise ValueError("Predicate must be a supported Boolean expression")
    return predicate


def _ast_to_z3(node: ast.AST, variables: dict[str, Any]) -> Optional[_Expression]:
    """Translate the pure subset without assuming Z3's total arithmetic is Python's."""
    if isinstance(node, ast.Compare):
        current = _ast_to_z3(node.left, variables)
        if current is None:
            return None

        value = z3.BoolVal(True)
        defined = current.defined
        for op, comparator in zip(node.ops, node.comparators):
            next_operand = _ast_to_z3(comparator, variables)
            if next_operand is None or not current.value.sort().eq(next_operand.value.sort()):
                return None
            left, right = current.value, next_operand.value
            if not isinstance(op, (ast.Eq, ast.NotEq)) and not z3.is_int(left):
                return None

            if isinstance(op, ast.Gt):
                compared = left > right
            elif isinstance(op, ast.GtE):
                compared = left >= right
            elif isinstance(op, ast.Lt):
                compared = left < right
            elif isinstance(op, ast.LtE):
                compared = left <= right
            elif isinstance(op, ast.Eq):
                compared = left == right
            elif isinstance(op, ast.NotEq):
                compared = left != right
            else:
                return None

            # In a chain the next operand is evaluated only if earlier comparisons held.
            defined = z3.And(defined, z3.Implies(value, next_operand.defined))
            value = z3.And(value, compared)
            current = next_operand
        return _Expression(value, defined)

    if isinstance(node, ast.BinOp):
        lhs = _ast_to_z3(node.left, variables)
        rhs = _ast_to_z3(node.right, variables)
        if lhs is None or rhs is None or not z3.is_int(lhs.value) or not z3.is_int(rhs.value):
            return None
        left, right = lhs.value, rhs.value
        if isinstance(node.op, ast.Add):
            return _strict(left + right, lhs, rhs)
        if isinstance(node.op, ast.Sub):
            return _strict(left - right, lhs, rhs)
        if isinstance(node.op, ast.Mult):
            return _strict(left * right, lhs, rhs)
        if isinstance(node.op, (ast.FloorDiv, ast.Mod)):
            # With a positive divisor SMT Int div rounds down, as Python does.
            # Negate both operands for a negative divisor to preserve that floor.
            quotient = z3.If(right > 0, left / right, (-left) / (-right))
            value = quotient if isinstance(node.op, ast.FloorDiv) else left - right * quotient
            return _Expression(value, z3.And(lhs.defined, rhs.defined, right != 0))
        return None

    if isinstance(node, ast.UnaryOp):
        operand = _ast_to_z3(node.operand, variables)
        if operand is None:
            return None
        if isinstance(node.op, ast.USub) and z3.is_int(operand.value):
            return _strict(-operand.value, operand)
        if isinstance(node.op, ast.UAdd) and z3.is_int(operand.value):
            return operand
        if isinstance(node.op, ast.Not) and z3.is_bool(operand.value):
            return _strict(z3.Not(operand.value), operand)
        return None

    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, (ast.And, ast.Or)):
            return None
        is_and = isinstance(node.op, ast.And)
        value = z3.BoolVal(is_and)
        defined = z3.BoolVal(True)
        for inner in node.values:
            operand = _ast_to_z3(inner, variables)
            if operand is None or not z3.is_bool(operand.value):
                return None
            evaluate = value if is_and else z3.Not(value)
            defined = z3.And(defined, z3.Implies(evaluate, operand.defined))
            value = z3.And(value, operand.value) if is_and else z3.Or(value, operand.value)
        return _Expression(value, defined)

    if isinstance(node, ast.Name):
        value = variables.get(node.id)
        return None if value is None else _strict(value)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return _strict(z3.BoolVal(node.value))
        if isinstance(node.value, int):
            return _strict(z3.IntVal(node.value))
        return None

    if isinstance(node, ast.IfExp):
        test = _ast_to_z3(node.test, variables)
        yes = _ast_to_z3(node.body, variables)
        no = _ast_to_z3(node.orelse, variables)
        if (
            test is None or not z3.is_bool(test.value)
            or yes is None or no is None or not yes.value.sort().eq(no.value.sort())
        ):
            return None
        return _conditional(test, yes, no)

    return None


def _z3_value_to_python(val: Any) -> Any:
    """Convert Z3 value to Python value."""
    if not Z3_AVAILABLE:
        return None

    try:
        if z3.is_int_value(val):
            return val.as_long()
        elif z3.is_true(val):
            return True
        elif z3.is_false(val):
            return False
        else:
            return str(val)
    except Exception:
        return str(val)
