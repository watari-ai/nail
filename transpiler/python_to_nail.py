"""
Python (typed subset) → NAIL IR Transpiler

Converts type-annotated Python function definitions to NAIL JSON IR,
enabling type and effect verification without writing NAIL directly.

Supported subset:
  - Functions with full type annotations (all params + return)
  - Basic types: int, float, bool, str, None
  - Statements: return, let (annotated/plain assign), assign, if/else, for-range loop
  - Effects: open() → FS, requests.* → NET, print() → IO
  - Expressions: literals, variables, arithmetic, comparisons, boolean ops, function calls

Not supported (TranspilerError raised):
  - Classes, lambdas, decorators, while loops, try/except
  - Unannotated parameters or return types
  - Generic types (Optional[T], List[T], etc.)
  - import statements
"""

import ast
import json
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TranspilerError(Exception):
    """Raised when Python code cannot be transpiled to NAIL IR."""
    pass


# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------

# Python type annotation name → NAIL type dict
_SIMPLE_TYPE_MAP: dict[str, dict] = {
    "int":   {"type": "int",   "bits": 64, "overflow": "panic"},
    "float": {"type": "float", "bits": 64},
    "bool":  {"type": "bool"},
    "str":   {"type": "string"},
    "None":  {"type": "unit"},
}

_INT64  = {"type": "int",   "bits": 64, "overflow": "panic"}
_FLOAT64 = {"type": "float", "bits": 64}
_BOOL   = {"type": "bool"}
_STRING = {"type": "string"}
_UNIT   = {"type": "unit"}


def py_annotation_to_nail(annotation: ast.expr | None) -> dict:
    """Convert a Python type annotation AST node to a NAIL type dict.

    Raises:
        TranspilerError: if the annotation is missing or unsupported.
    """
    if annotation is None:
        raise TranspilerError("Missing type annotation (all parameters and return type must be annotated)")

    # Simple name: int, float, bool, str, None
    if isinstance(annotation, ast.Name):
        name = annotation.id
        if name in _SIMPLE_TYPE_MAP:
            return dict(_SIMPLE_TYPE_MAP[name])
        raise TranspilerError(
            f"Unsupported type annotation '{name}'. "
            f"Supported: {', '.join(_SIMPLE_TYPE_MAP.keys())}. "
            f"Generic types (Optional, List, etc.) not yet supported."
        )

    # Constant None used as return annotation
    if isinstance(annotation, ast.Constant) and annotation.value is None:
        return dict(_UNIT)

    raise TranspilerError(
        f"Unsupported annotation type: {type(annotation).__name__}. "
        f"Only simple types (int, float, bool, str, None) are supported."
    )


# ---------------------------------------------------------------------------
# Effect inference
# ---------------------------------------------------------------------------

def detect_effects(fn_node: ast.FunctionDef) -> list[str]:
    """Walk a function's AST and infer NAIL effects from call patterns.

    Detection rules:
      - open(...)         → FS
      - print(...)        → IO
      - requests.<any>(…) → NET
    """
    effects: set[str] = set()

    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Call):
            continue

        func = node.func

        # Simple names: open(), print()
        if isinstance(func, ast.Name):
            if func.id == "open":
                effects.add("FS")
            elif func.id == "print":
                effects.add("IO")

        # Attribute calls: requests.get(), requests.post(), etc.
        elif isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id == "requests":
                effects.add("NET")

    # Return sorted for canonical, reproducible output
    return sorted(effects)


# ---------------------------------------------------------------------------
# Binary / comparison operator maps
# ---------------------------------------------------------------------------

_BINOP_MAP: dict[type, str] = {
    ast.Add:  "+",
    ast.Sub:  "-",
    ast.Mult: "*",
    ast.Div:  "/",
    ast.Mod:  "%",
}

_AUG_OP_MAP: dict[type, str] = {
    ast.Add:  "+",
    ast.Sub:  "-",
    ast.Mult: "*",
    ast.Div:  "/",
    ast.Mod:  "%",
}

_CMP_MAP: dict[type, str] = {
    ast.Eq:    "eq",
    ast.NotEq: "neq",
    ast.Lt:    "lt",
    ast.LtE:   "lte",
    ast.Gt:    "gt",
    ast.GtE:   "gte",
}

# NAIL builtins with single-value argument: op_name → NAIL op string
_BUILTIN_SINGLE_ARG: dict[str, str] = {
    "int_to_str":   "int_to_str",
    "float_to_str": "float_to_str",
    "bool_to_str":  "bool_to_str",
    "str_len":      "str_len",
    "str_trim":     "str_trim",
    "str_upper":    "str_upper",
    "str_lower":    "str_lower",
    "abs":          "abs",
}


# ---------------------------------------------------------------------------
# Function transpiler
# ---------------------------------------------------------------------------

class _FunctionTranspiler:
    """Stateful transpiler for a single Python function definition."""

    def __init__(self, fn_node: ast.FunctionDef):
        self.fn = fn_node
        # Tracks declared local variables: name → True (always mutable in our output)
        self._local_vars: set[str] = set()

    def transpile(self) -> dict:
        """Produce a NAIL IR dict for this function."""
        fn = self.fn

        # --- Parameters ---
        params = []
        for arg in fn.args.args:
            if arg.annotation is None:
                raise TranspilerError(
                    f"Parameter '{arg.arg}' in function '{fn.name}' has no type annotation. "
                    f"All parameters must be fully annotated."
                )
            params.append({
                "id":   arg.arg,
                "type": py_annotation_to_nail(arg.annotation),
            })

        # Unsupported parameter kinds
        if fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs:
            raise TranspilerError(
                f"Function '{fn.name}': *args, **kwargs, and keyword-only args are not supported"
            )
        if fn.args.defaults or fn.args.kw_defaults:
            raise TranspilerError(
                f"Function '{fn.name}': default argument values are not supported"
            )

        # --- Return type ---
        if fn.returns is None:
            raise TranspilerError(
                f"Function '{fn.name}' has no return type annotation. "
                f"All functions must declare a return type."
            )
        returns = py_annotation_to_nail(fn.returns)

        # --- Effects (auto-inferred) ---
        effects = detect_effects(fn)

        # Pre-load params as known variables (not local lets)
        for p in params:
            self._local_vars.add(p["id"])

        # --- Body ---
        body = self._transpile_stmts(fn.body)

        return {
            "nail":    "0.1.0",
            "kind":    "fn",
            "id":      fn.name,
            "effects": effects,
            "params":  params,
            "returns": returns,
            "body":    body,
        }

    # ------------------------------------------------------------------
    # Statement transpilation
    # ------------------------------------------------------------------

    def _transpile_stmts(self, stmts: list[ast.stmt]) -> list[dict]:
        result: list[dict] = []
        for stmt in stmts:
            result.extend(self._transpile_stmt(stmt))
        return result

    def _transpile_stmt(self, stmt: ast.stmt) -> list[dict]:
        if isinstance(stmt, ast.Return):
            return self._transpile_return(stmt)
        elif isinstance(stmt, ast.AnnAssign):
            return self._transpile_ann_assign(stmt)
        elif isinstance(stmt, ast.Assign):
            return self._transpile_assign(stmt)
        elif isinstance(stmt, ast.AugAssign):
            return self._transpile_aug_assign(stmt)
        elif isinstance(stmt, ast.If):
            return self._transpile_if(stmt)
        elif isinstance(stmt, ast.For):
            return self._transpile_for(stmt)
        elif isinstance(stmt, ast.While):
            raise TranspilerError(
                "while loops are not supported (NAIL requires bounded loops). "
                "Use 'for i in range(n)' instead."
            )
        elif isinstance(stmt, ast.Expr):
            return self._transpile_expr_stmt(stmt)
        elif isinstance(stmt, ast.Pass):
            return []
        else:
            raise TranspilerError(
                f"Unsupported statement: {type(stmt).__name__}. "
                f"Supported: return, assignment, if/else, for-range, print()"
            )

    def _transpile_return(self, stmt: ast.Return) -> list[dict]:
        if stmt.value is None:
            # `return` with no value → unit
            return [{"op": "return", "val": {"lit": None, "type": _UNIT}}]
        return [{"op": "return", "val": self._transpile_expr(stmt.value)}]

    def _transpile_ann_assign(self, stmt: ast.AnnAssign) -> list[dict]:
        """Handle `x: int = expr` annotated assignment."""
        if not isinstance(stmt.target, ast.Name):
            raise TranspilerError(
                "Only simple variable annotated assignments supported (e.g. 'x: int = 5')"
            )
        var_name = stmt.target.id
        nail_type = py_annotation_to_nail(stmt.annotation)

        if stmt.value is None:
            raise TranspilerError(
                f"Annotated assignment '{var_name}: ...' without a value is not supported. "
                f"Provide an initial value."
            )
        val = self._transpile_expr(stmt.value)

        if var_name not in self._local_vars:
            self._local_vars.add(var_name)
            return [{"op": "let", "id": var_name, "type": nail_type, "val": val, "mut": True}]
        else:
            return [{"op": "assign", "id": var_name, "val": val}]

    def _transpile_assign(self, stmt: ast.Assign) -> list[dict]:
        """Handle plain `x = expr` assignment."""
        if len(stmt.targets) != 1:
            raise TranspilerError(
                "Only single-target assignments are supported (no tuple unpacking)"
            )
        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            raise TranspilerError(
                "Only simple variable assignments are supported (no subscript, attribute, etc.)"
            )
        var_name = target.id
        val = self._transpile_expr(stmt.value)

        if var_name not in self._local_vars:
            self._local_vars.add(var_name)
            # No explicit type: NAIL will infer from the value literal
            return [{"op": "let", "id": var_name, "val": val, "mut": True}]
        else:
            return [{"op": "assign", "id": var_name, "val": val}]

    def _transpile_aug_assign(self, stmt: ast.AugAssign) -> list[dict]:
        """Handle `x += expr`, `x -= expr`, etc."""
        if not isinstance(stmt.target, ast.Name):
            raise TranspilerError(
                "Only simple variable augmented assignments are supported (e.g. 'x += 1')"
            )
        var_name = stmt.target.id
        op_type = type(stmt.op)
        if op_type not in _AUG_OP_MAP:
            raise TranspilerError(
                f"Unsupported augmented assignment operator: {type(stmt.op).__name__}. "
                f"Supported: +=, -=, *=, /=, %="
            )
        nail_op = _AUG_OP_MAP[op_type]
        rhs = self._transpile_expr(stmt.value)
        combined = {"op": nail_op, "l": {"ref": var_name}, "r": rhs}
        return [{"op": "assign", "id": var_name, "val": combined}]

    def _transpile_if(self, stmt: ast.If) -> list[dict]:
        """Handle `if cond: ... else: ...` (else is mandatory in NAIL)."""
        cond = self._transpile_expr(stmt.test)
        then_body = self._transpile_stmts(stmt.body)
        else_body = self._transpile_stmts(stmt.orelse) if stmt.orelse else []
        return [{"op": "if", "cond": cond, "then": then_body, "else": else_body}]

    def _transpile_for(self, stmt: ast.For) -> list[dict]:
        """Handle `for i in range(...)` → NAIL bounded loop.

        Supported forms:
          for i in range(n)              → loop bind=i, from=0, to=n,     step=1
          for i in range(start, end)     → loop bind=i, from=start, to=end, step=1
          for i in range(start, end, s)  → loop bind=i, from=start, to=end, step=s
        """
        if not isinstance(stmt.target, ast.Name):
            raise TranspilerError(
                "Only simple loop variables are supported (e.g. 'for i in range(n)')"
            )
        bind = stmt.target.id

        # Verify it's a range() call
        if not (
            isinstance(stmt.iter, ast.Call)
            and isinstance(stmt.iter.func, ast.Name)
            and stmt.iter.func.id == "range"
        ):
            raise TranspilerError(
                "Only 'for i in range(...)' loops are supported. "
                "Iterating over lists/dicts/etc. is not supported."
            )

        args = stmt.iter.args
        if len(args) == 1:
            from_val = {"lit": 0}
            to_val   = self._transpile_expr(args[0])
            step_val = {"lit": 1}
        elif len(args) == 2:
            from_val = self._transpile_expr(args[0])
            to_val   = self._transpile_expr(args[1])
            step_val = {"lit": 1}
        elif len(args) == 3:
            from_val = self._transpile_expr(args[0])
            to_val   = self._transpile_expr(args[1])
            step_val = self._transpile_expr(args[2])
        else:
            raise TranspilerError("range() requires 1 to 3 arguments")

        # Handle optional else clause (rare; not meaningful for loop transpilation)
        if stmt.orelse:
            raise TranspilerError(
                "for/else loops are not supported. Remove the 'else' clause."
            )

        body = self._transpile_stmts(stmt.body)
        return [{
            "op":   "loop",
            "bind": bind,
            "from": from_val,
            "to":   to_val,
            "step": step_val,
            "body": body,
        }]

    def _transpile_expr_stmt(self, stmt: ast.Expr) -> list[dict]:
        """Handle expression statements (mainly print() calls)."""
        val = stmt.value
        if isinstance(val, ast.Call):
            func = val.func
            # print(expr) → NAIL print op
            if isinstance(func, ast.Name) and func.id == "print":
                if len(val.args) == 0:
                    # print() with no args: print empty string
                    return [{"op": "print", "val": {"lit": ""}, "effect": "IO"}]
                if len(val.args) == 1:
                    return [{"op": "print", "val": self._transpile_expr(val.args[0]), "effect": "IO"}]
                raise TranspilerError(
                    "print() with multiple arguments is not supported. "
                    "Concatenate strings manually: print(a + b)"
                )
            # Other call expressions: transpile and discard result
            # (e.g. open(), requests.get() called for side effects)
            # We still need to produce a statement, but NAIL has no call-as-stmt at fn level
            # So we skip them (effects already detected at function level)
            return []
        # Non-call expression statements are silently dropped
        return []

    # ------------------------------------------------------------------
    # Expression transpilation
    # ------------------------------------------------------------------

    def _transpile_expr(self, expr: ast.expr) -> dict:
        # Literal constants
        if isinstance(expr, ast.Constant):
            return self._transpile_constant(expr)

        # Variable reference
        if isinstance(expr, ast.Name):
            # Handle bare True/False/None names (Python 3.8+ uses ast.Constant)
            if expr.id == "True":
                return {"lit": True}
            if expr.id == "False":
                return {"lit": False}
            if expr.id == "None":
                return {"lit": None, "type": _UNIT}
            return {"ref": expr.id}

        # Binary operations
        if isinstance(expr, ast.BinOp):
            return self._transpile_binop(expr)

        # Unary operations
        if isinstance(expr, ast.UnaryOp):
            return self._transpile_unaryop(expr)

        # Comparisons
        if isinstance(expr, ast.Compare):
            return self._transpile_compare(expr)

        # Boolean operations (and / or)
        if isinstance(expr, ast.BoolOp):
            return self._transpile_boolop(expr)

        # Function calls (as expressions)
        if isinstance(expr, ast.Call):
            return self._transpile_call(expr)

        raise TranspilerError(
            f"Unsupported expression: {type(expr).__name__}. "
            f"Supported: literals, variables, arithmetic, comparisons, boolean ops, function calls."
        )

    def _transpile_constant(self, expr: ast.Constant) -> dict:
        val = expr.value
        if val is None:
            return {"lit": None, "type": _UNIT}
        if isinstance(val, bool):
            # Must check bool before int (bool is subclass of int in Python)
            return {"lit": val}
        if isinstance(val, int):
            return {"lit": val}
        if isinstance(val, float):
            return {"lit": val}
        if isinstance(val, str):
            return {"lit": val}
        raise TranspilerError(
            f"Unsupported literal type: {type(val).__name__} (value: {val!r}). "
            f"Supported: int, float, bool, str, None."
        )

    def _transpile_binop(self, expr: ast.BinOp) -> dict:
        op_type = type(expr.op)
        if op_type not in _BINOP_MAP:
            raise TranspilerError(
                f"Unsupported binary operator: {type(expr.op).__name__}. "
                f"Supported: +, -, *, /, %"
            )
        return {
            "op": _BINOP_MAP[op_type],
            "l":  self._transpile_expr(expr.left),
            "r":  self._transpile_expr(expr.right),
        }

    def _transpile_unaryop(self, expr: ast.UnaryOp) -> dict:
        if isinstance(expr.op, ast.Not):
            return {"op": "not", "v": self._transpile_expr(expr.operand)}
        if isinstance(expr.op, ast.USub):
            # -x → 0 - x
            return {"op": "-", "l": {"lit": 0}, "r": self._transpile_expr(expr.operand)}
        if isinstance(expr.op, ast.UAdd):
            return self._transpile_expr(expr.operand)
        raise TranspilerError(
            f"Unsupported unary operator: {type(expr.op).__name__}. "
            f"Supported: not, - (negation)"
        )

    def _transpile_compare(self, expr: ast.Compare) -> dict:
        if len(expr.ops) != 1 or len(expr.comparators) != 1:
            raise TranspilerError(
                "Chained comparisons (e.g. 'a < b < c') are not supported. "
                "Use separate comparisons with 'and'."
            )
        op_type = type(expr.ops[0])
        if op_type not in _CMP_MAP:
            raise TranspilerError(
                f"Unsupported comparison operator: {type(expr.ops[0]).__name__}. "
                f"Supported: ==, !=, <, <=, >, >="
            )
        return {
            "op": _CMP_MAP[op_type],
            "l":  self._transpile_expr(expr.left),
            "r":  self._transpile_expr(expr.comparators[0]),
        }

    def _transpile_boolop(self, expr: ast.BoolOp) -> dict:
        """Fold left-associative: (a and b and c) → and(and(a, b), c)."""
        nail_op = "and" if isinstance(expr.op, ast.And) else "or"
        result = self._transpile_expr(expr.values[0])
        for val in expr.values[1:]:
            result = {"op": nail_op, "l": result, "r": self._transpile_expr(val)}
        return result

    def _transpile_call(self, call: ast.Call) -> dict:
        """Convert a Python function call to NAIL call/builtin op."""
        func = call.func

        if isinstance(func, ast.Name):
            name = func.id

            # NAIL single-arg builtins (int_to_str, abs, str_len, etc.)
            if name in _BUILTIN_SINGLE_ARG and len(call.args) == 1:
                return {
                    "op": _BUILTIN_SINGLE_ARG[name],
                    "v":  self._transpile_expr(call.args[0]),
                }

            # Generic function call → NAIL call op
            args = [self._transpile_expr(a) for a in call.args]
            return {"op": "call", "fn": name, "args": args}

        # Attribute calls (e.g. requests.get(url)) - unsupported as expressions
        # (effects are captured at function level, but result use isn't translatable)
        if isinstance(func, ast.Attribute):
            raise TranspilerError(
                f"Method/attribute calls ('{ast.dump(func)}') are not supported as expressions. "
                f"Effect-only calls (requests.get, etc.) are detected for effect inference "
                f"but their return values cannot be used in expressions."
            )

        raise TranspilerError(
            f"Unsupported call target: {type(func).__name__}. "
            f"Only simple function names are supported."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transpile_function(
    source: str,
    fn_name: str | None = None,
) -> dict:
    """Transpile a Python function definition to a NAIL IR dict.

    Args:
        source:  Python source code containing one or more function definitions.
        fn_name: Name of the function to transpile. If None, transpiles the
                 first function definition found.

    Returns:
        A NAIL IR dict ready for Checker() and Runtime().

    Raises:
        TranspilerError: If the function cannot be transpiled.
        SyntaxError:     If the Python source has syntax errors.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        raise TranspilerError(f"Python syntax error: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if fn_name is None or node.name == fn_name:
                return _FunctionTranspiler(node).transpile()

    if fn_name:
        raise TranspilerError(f"Function '{fn_name}' not found in source")
    raise TranspilerError("No function definitions found in source")


def transpile_to_json(
    source: str,
    fn_name: str | None = None,
) -> str:
    """Transpile Python to canonical NAIL JSON string.

    Produces JCS (RFC 8785 subset) canonical form:
    sort_keys=True, no spaces.

    Args:
        source:  Python source code.
        fn_name: Specific function to transpile (or first if None).

    Returns:
        Canonical NAIL JSON string.
    """
    spec = transpile_function(source, fn_name)
    return json.dumps(spec, sort_keys=True, separators=(",", ":"))


def transpile_and_check(
    source: str,
    fn_name: str | None = None,
) -> dict:
    """Transpile Python to NAIL IR and run the full NAIL checker.

    Convenience function for one-shot verification.

    Returns:
        The NAIL IR dict (already verified).

    Raises:
        TranspilerError: Transpilation failed.
        CheckError:      NAIL type/effect check failed.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from interpreter import Checker, CheckError  # noqa: F401

    spec = transpile_function(source, fn_name)
    Checker(spec).check()
    return spec
