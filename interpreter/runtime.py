"""
NAIL Runtime — v0.1
Executes validated NAIL programs.
"""

from typing import Any
from .types import (
    IntType, FloatType, BoolType, StringType, UnitType, OptionType,
    NailRuntimeError, parse_type, types_equal,
)


UNIT = object()     # Sentinel for the unit value
_MISSING = object() # Sentinel for "variable did not exist"


class NailOverflowError(NailRuntimeError):
    pass


class Runtime:
    def __init__(self, spec: dict, modules: dict | None = None):
        """
        spec    — the NAIL module/fn spec to execute
        modules — optional {module_id: module_spec} for cross-module calls
        """
        self.spec = spec
        self.declared_effects = set(spec.get("effects", []))
        self.fn_registry: dict[str, dict] = {}
        if spec.get("kind") == "module":
            self.fn_registry = {fn["id"]: fn for fn in spec.get("defs", [])}
        # Build module_fn_registry for cross-module calls
        self.module_fn_registry: dict[str, dict[str, dict]] = {}
        for mod_id, mod_spec in (modules or {}).items():
            self.module_fn_registry[mod_id] = {
                fn["id"]: fn for fn in mod_spec.get("defs", []) if "id" in fn
            }

    def run(self, args: dict | None = None):
        """Run the program. For kind:fn, executes it directly.
        For kind:module, looks for a 'main' function.
        """
        kind = self.spec.get("kind")
        if kind == "fn":
            return self._run_fn(self.spec, args or {})
        if kind == "module":
            return self.run_fn("main", args or {})
        raise NailRuntimeError(f"Cannot directly run kind: {kind}")

    def run_fn(self, fn_id: str, args: dict | None = None) -> Any:
        """Run a named function from a module."""
        kind = self.spec.get("kind")
        if kind != "module":
            raise NailRuntimeError("run_fn() requires kind:module")
        if fn_id not in self.fn_registry:
            available = list(self.fn_registry.keys())
            raise NailRuntimeError(f"Function '{fn_id}' not found in module. Available: {available}")
        return self._run_fn(self.fn_registry[fn_id], args or {})

    def _run_fn(self, fn: dict, args: dict) -> Any:
        env = dict(args)
        # Bind params
        for param in fn.get("params", []):
            pid = param["id"]
            if pid not in env:
                raise NailRuntimeError(f"Missing argument: {pid}")
        result = self._run_body(fn["body"], env)
        # At the top-level function boundary, _CONTINUE means implicit unit return
        return UNIT if result is _CONTINUE else result

    def _run_body(self, body: list, env: dict) -> Any:
        """Execute a list of statements, mutating env in place.

        Returns:
          _CONTINUE  — body completed without an explicit 'return'
          <value>    — explicit 'return' was hit; propagate the value up

        Note: env is mutated directly so that 'assign' and 'let' ops in nested
        bodies (loops, if-branches) propagate back to the enclosing scope.
        Function call boundaries use a fresh env (see _run_fn).
        """
        for stmt in body:
            result = self._run_stmt(stmt, env)
            if result is not _CONTINUE:
                return result
        return _CONTINUE  # no explicit return in this block

    def _run_stmt(self, stmt: dict, env: dict) -> Any:
        op = stmt["op"]

        if op == "return":
            return self._eval(stmt["val"], env)

        elif op == "let":
            val = self._eval(stmt["val"], env)
            env[stmt["id"]] = val
            return _CONTINUE

        elif op == "assign":
            # Mutable update — modifies existing binding in place
            name = stmt["id"]
            if name not in env:
                raise NailRuntimeError(f"'assign' to undeclared variable: {name!r}")
            env[name] = self._eval(stmt["val"], env)
            return _CONTINUE

        elif op == "print":
            val = self._eval(stmt["val"], env)
            print(val)
            return _CONTINUE

        elif op == "match_result":
            result_val = self._eval(stmt["val"], env)
            if not isinstance(result_val, NailResult):
                raise NailRuntimeError(f"'match_result' expects NailResult, got {type(result_val).__name__}")
            if result_val.is_ok:
                ok_bind = stmt.get("ok_bind")
                if ok_bind:
                    env[ok_bind] = result_val._val
                ret = self._run_body(stmt.get("ok_body", []), env)
            else:
                err_bind = stmt.get("err_bind")
                if err_bind:
                    env[err_bind] = result_val._val
                ret = self._run_body(stmt.get("err_body", []), env)
            if ret is not _CONTINUE:
                return ret
            return _CONTINUE

        elif op == "read_file":
            # v0.2 reference interpreter: FS ops not yet executed
            raise NailRuntimeError(
                "'read_file' is recognized by the checker but not yet executed "
                "in the v0.2 reference interpreter (planned for v0.3+)"
            )

        elif op == "http_get":
            # v0.2 reference interpreter: NET ops not yet executed
            raise NailRuntimeError(
                "'http_get' is recognized by the checker but not yet executed "
                "in the v0.2 reference interpreter (planned for v0.3+)"
            )

        elif op == "call":
            self._eval_op(stmt, env)
            return _CONTINUE

        elif op == "if":
            cond = self._eval(stmt["cond"], env)
            branch = stmt["then"] if cond else stmt["else"]
            result = self._run_body(branch, env)
            if result is not _CONTINUE:
                return result
            return _CONTINUE

        elif op == "loop":
            bind = stmt["bind"]
            from_val = self._eval(stmt["from"], env)
            to_val = self._eval(stmt["to"], env)
            step_val = self._eval(stmt["step"], env)
            i = from_val
            prev_bind = env.get(bind, _MISSING)
            try:
                while i < to_val:
                    # Share the outer env so mutable `assign` ops propagate back.
                    # The loop bind variable is injected directly.
                    env[bind] = i
                    result = self._run_body(stmt["body"], env)
                    if result is not _CONTINUE:
                        return result
                    i += step_val
            finally:
                # Restore or remove the bind variable
                if prev_bind is _MISSING:
                    env.pop(bind, None)
                else:
                    env[bind] = prev_bind
            return _CONTINUE

        elif op == "return_void":
            return UNIT

        else:
            raise NailRuntimeError(f"Unknown statement op: {op}")

    def _eval(self, expr: dict, env: dict) -> Any:
        if expr is None:
            raise NailRuntimeError("Expression is None")

        # Literal
        if "lit" in expr:
            val = expr["lit"]
            if val is None:
                t = parse_type(expr.get("type", {"type": "unit"}))
                return None if isinstance(t, OptionType) else UNIT
            return val

        # Variable reference
        if "ref" in expr:
            name = expr["ref"]
            if name not in env:
                raise NailRuntimeError(f"Undefined variable: {name}")
            return env[name]

        # Operator expressions
        if "op" in expr:
            return self._eval_op(expr, env)

        raise NailRuntimeError(f"Unrecognized expression: {expr}")

    def _eval_op(self, expr: dict, env: dict) -> Any:
        op = expr["op"]

        # Arithmetic (supports expression-level overflow override via "overflow" key)
        if op == "+":
            return self._int_op(self._eval(expr["l"], env), self._eval(expr["r"], env), lambda a, b: a + b, "+", expr.get("overflow"))
        elif op == "-":
            return self._int_op(self._eval(expr["l"], env), self._eval(expr["r"], env), lambda a, b: a - b, "-", expr.get("overflow"))
        elif op == "*":
            return self._int_op(self._eval(expr["l"], env), self._eval(expr["r"], env), lambda a, b: a * b, "*", expr.get("overflow"))
        elif op == "/":
            r = self._eval(expr["r"], env)
            if r == 0:
                raise NailRuntimeError("Division by zero")
            l = self._eval(expr["l"], env)
            # Use true division for floats, floor division for integers
            if isinstance(l, float) or isinstance(r, float):
                return l / r
            return l // r
        elif op == "%":
            r = self._eval(expr["r"], env)
            if r == 0:
                raise NailRuntimeError("Modulo by zero")
            return self._eval(expr["l"], env) % r

        # Comparison
        elif op == "eq":  return self._eval(expr["l"], env) == self._eval(expr["r"], env)
        elif op == "neq": return self._eval(expr["l"], env) != self._eval(expr["r"], env)
        elif op == "lt":  return self._eval(expr["l"], env) <  self._eval(expr["r"], env)
        elif op == "lte": return self._eval(expr["l"], env) <= self._eval(expr["r"], env)
        elif op == "gt":  return self._eval(expr["l"], env) >  self._eval(expr["r"], env)
        elif op == "gte": return self._eval(expr["l"], env) >= self._eval(expr["r"], env)

        # Boolean
        elif op == "and": return self._eval(expr["l"], env) and self._eval(expr["r"], env)
        elif op == "or":  return self._eval(expr["l"], env) or  self._eval(expr["r"], env)
        elif op == "not": return not self._eval(expr["v"], env)

        # Type conversions (explicit — NAIL has no implicit coercions)
        elif op == "int_to_str":
            v = self._eval(expr["v"], env)
            return str(v)
        elif op == "float_to_str":
            v = self._eval(expr["v"], env)
            return str(v)
        elif op == "bool_to_str":
            v = self._eval(expr["v"], env)
            return "true" if v else "false"

        # String operations
        elif op == "concat":
            l = self._eval(expr["l"], env)
            r = self._eval(expr["r"], env)
            if not isinstance(l, str) or not isinstance(r, str):
                raise NailRuntimeError(f"'concat' requires two strings, got {type(l)}, {type(r)}")
            return l + r

        elif op == "ok":
            return NailResult("ok", self._eval(expr["val"], env))

        elif op == "err":
            return NailResult("err", self._eval(expr["val"], env))

        elif op == "call":
            if self.spec.get("kind") != "module":
                raise NailRuntimeError("Function call is only supported for kind:module")
            callee_id = expr.get("fn")
            cross_module = expr.get("module")

            if cross_module:
                # Cross-module call
                if cross_module not in self.module_fn_registry:
                    raise NailRuntimeError(
                        f"Module '{cross_module}' not loaded. "
                        f"Pass modules={{'{cross_module}': ...}} to Runtime()."
                    )
                mod_fns = self.module_fn_registry[cross_module]
                if callee_id not in mod_fns:
                    raise NailRuntimeError(f"Function '{callee_id}' not found in module '{cross_module}'")
                callee = mod_fns[callee_id]
            else:
                if callee_id not in self.fn_registry:
                    raise NailRuntimeError(f"Unknown function: {callee_id!r}")
                callee = self.fn_registry[callee_id]

            args_expr = expr.get("args", [])
            params = callee.get("params", [])
            if len(args_expr) != len(params):
                raise NailRuntimeError(
                    f"Function '{callee_id}' expects {len(params)} args, got {len(args_expr)}"
                )
            call_args = {}
            for param, arg_expr in zip(params, args_expr):
                call_args[param["id"]] = self._eval(arg_expr, env)
            return self._run_fn(callee, call_args)

        else:
            raise NailRuntimeError(f"Unknown op: {op}")

    def _int_op(self, l: Any, r: Any, fn, op_name: str, overflow: str | None = None) -> Any:
        """Perform integer arithmetic with explicit overflow handling.

        overflow=None or "panic": raise on overflow (default)
        overflow="wrap":          two's-complement wrapping (signed int64)
        overflow="sat":           clamp to [INT64_MIN, INT64_MAX]
        """
        result = fn(l, r)
        if not (isinstance(l, int) and isinstance(r, int)):
            return result  # float arithmetic — no overflow semantics

        MAX64 = (1 << 63) - 1
        MIN64 = -(1 << 63)
        RANGE = 1 << 64

        mode = overflow or "panic"
        if mode == "wrap":
            # Signed 64-bit two's-complement wrapping
            result = ((result - MIN64) % RANGE) + MIN64
        elif mode == "sat":
            # Saturating: clamp to [INT64_MIN, INT64_MAX]
            result = max(MIN64, min(MAX64, result))
        else:  # "panic"
            if result > MAX64 or result < MIN64:
                raise NailOverflowError(
                    f"Integer overflow in '{op_name}': result {result} out of int64 range. "
                    f"Use overflow:\"wrap\" or overflow:\"sat\" to suppress."
                )
        return result


class _Continue:
    """Sentinel: statement did not produce a return value."""
    pass

_CONTINUE = _Continue()


# ---------------------------------------------------------------------------
# Result type runtime representation
# ---------------------------------------------------------------------------

class NailResult:
    """Runtime value for result<Ok, Err>."""
    def __init__(self, tag: str, val):
        assert tag in ("ok", "err"), f"Invalid result tag: {tag}"
        self._tag = tag
        self._val = val

    @property
    def is_ok(self): return self._tag == "ok"

    @property
    def is_err(self): return self._tag == "err"

    def __repr__(self):
        return f"NailResult({self._tag!r}, {self._val!r})"

    def __eq__(self, other):
        return isinstance(other, NailResult) and self._tag == other._tag and self._val == other._val
