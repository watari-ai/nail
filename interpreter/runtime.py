"""
NAIL Runtime — v0.1
Executes validated NAIL programs.
"""

from typing import Any
from .types import (
    IntType, FloatType, BoolType, StringType, UnitType, OptionType,
    NailRuntimeError, parse_type, types_equal,
)


UNIT = object()  # Sentinel for the unit value


class NailOverflowError(NailRuntimeError):
    pass


class Runtime:
    def __init__(self, spec: dict):
        self.spec = spec
        self.declared_effects = set(spec.get("effects", []))

    def run(self):
        kind = self.spec.get("kind")
        if kind == "fn":
            return self._run_fn(self.spec, {})
        raise NailRuntimeError(f"Cannot directly run kind: {kind}")

    def _run_fn(self, fn: dict, args: dict) -> Any:
        env = dict(args)
        # Bind params
        for param in fn.get("params", []):
            pid = param["id"]
            if pid not in env:
                raise NailRuntimeError(f"Missing argument: {pid}")
        return self._run_body(fn["body"], env)

    def _run_body(self, body: list, env: dict) -> Any:
        local_env = dict(env)
        for stmt in body:
            result = self._run_stmt(stmt, local_env)
            if result is not _CONTINUE:
                return result
        return UNIT

    def _run_stmt(self, stmt: dict, env: dict) -> Any:
        op = stmt["op"]

        if op == "return":
            return self._eval(stmt["val"], env)

        elif op == "let":
            val = self._eval(stmt["val"], env)
            env[stmt["id"]] = val
            return _CONTINUE

        elif op == "print":
            val = self._eval(stmt["val"], env)
            print(val)
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
            while i < to_val:
                loop_env = dict(env)
                loop_env[bind] = i
                result = self._run_body(stmt["body"], loop_env)
                if result is not _CONTINUE:
                    return result
                i += step_val
            return _CONTINUE

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

        # Arithmetic
        if op == "+":
            return self._int_op(self._eval(expr["l"], env), self._eval(expr["r"], env), lambda a, b: a + b, "+")
        elif op == "-":
            return self._int_op(self._eval(expr["l"], env), self._eval(expr["r"], env), lambda a, b: a - b, "-")
        elif op == "*":
            return self._int_op(self._eval(expr["l"], env), self._eval(expr["r"], env), lambda a, b: a * b, "*")
        elif op == "/":
            r = self._eval(expr["r"], env)
            if r == 0:
                raise NailRuntimeError("Division by zero")
            return self._eval(expr["l"], env) // r
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

        else:
            raise NailRuntimeError(f"Unknown op: {op}")

    def _int_op(self, l: Any, r: Any, fn, op_name: str) -> Any:
        result = fn(l, r)
        # Basic overflow check for 64-bit signed integers
        # In a full implementation, this would use the declared overflow behavior
        MAX64 = (1 << 63) - 1
        MIN64 = -(1 << 63)
        if isinstance(l, int) and isinstance(r, int):
            if result > MAX64 or result < MIN64:
                raise NailOverflowError(
                    f"Integer overflow in '{op_name}': {l} {op_name} {r} = {result} (out of int64 range)"
                )
        return result


class _Continue:
    """Sentinel: statement did not produce a return value."""
    pass

_CONTINUE = _Continue()
