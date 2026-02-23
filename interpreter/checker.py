"""
NAIL Checker — v0.1
L0: JSON schema validation
L1: Type checking
L2: Effect checking
"""

import json
from typing import Any
from .types import (
    NailType, NailTypeError, NailEffectError,
    parse_type, types_equal,
    IntType, FloatType, BoolType, StringType, UnitType, OptionType,
    VALID_EFFECTS,
)


class CheckError(Exception):
    pass


class Checker:
    def __init__(self, spec: dict, raw_text: str | None = None, strict: bool = False):
        self.spec = spec
        self.env: dict[str, NailType] = {}
        self.declared_effects: set[str] = set()
        self.fn_registry: dict[str, dict] = {}
        self.call_graph: dict[str, set[str]] = {}
        self.raw_text = raw_text
        self.strict = strict

    # -----------------------------------------------------------------------
    # L0: Schema validation
    # -----------------------------------------------------------------------

    def check_l0(self):
        """Validate basic required fields."""
        # Strict mode: verify canonical form (JCS / RFC 8785 subset)
        if self.strict and self.raw_text is not None:
            canonical = json.dumps(self.spec, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            if self.raw_text.strip() != canonical:
                raise CheckError("Input is not in canonical form. Run 'nail canonicalize' to fix.")

        if "nail" not in self.spec:
            raise CheckError("Missing 'nail' version field")
        if "kind" not in self.spec:
            raise CheckError("Missing 'kind' field")
        kind = self.spec["kind"]
        if kind not in ("fn", "module"):
            raise CheckError(f"Unknown kind: {kind}. Must be 'fn' or 'module'")
        if "id" not in self.spec:
            raise CheckError("Missing 'id' field")
        if kind == "fn":
            self._check_fn_schema(self.spec)
        elif kind == "module":
            if "defs" not in self.spec:
                raise CheckError("Module missing 'defs' field")

    def _check_fn_schema(self, fn: dict):
        for field in ("effects", "params", "returns", "body"):
            if field not in fn:
                raise CheckError(f"Function '{fn.get('id', '?')}' missing '{field}'")
        if not isinstance(fn["effects"], list):
            raise CheckError(f"'effects' must be a list")
        for eff in fn["effects"]:
            if eff not in VALID_EFFECTS:
                raise CheckError(f"Unknown effect: {eff}. Valid: {VALID_EFFECTS}")
        if not isinstance(fn["params"], list):
            raise CheckError(f"'params' must be a list")
        if not isinstance(fn["body"], list):
            raise CheckError(f"'body' must be a list")

    # -----------------------------------------------------------------------
    # L1 + L2: Type and effect checking
    # -----------------------------------------------------------------------

    def check(self):
        """Run L0, L1, L2 checks."""
        self.check_l0()
        kind = self.spec["kind"]
        if kind == "fn":
            self._check_fn(self.spec)
        elif kind == "module":
            self._check_module(self.spec)

    def _check_module(self, mod: dict):
        """Check all function definitions in a module."""
        defs = mod.get("defs", [])
        if not isinstance(defs, list):
            raise CheckError("Module 'defs' must be a list")
        self.fn_registry = {}
        self.call_graph = {}
        self._collect_fn_registry(defs)
        for fn in defs:
            if not isinstance(fn, dict):
                raise CheckError(f"Module def must be a dict, got {type(fn)}")
            self._check_fn(fn)
        self._detect_recursive_calls()
        # Validate exports
        exports = mod.get("exports", [])
        defined_ids = {fn["id"] for fn in defs if "id" in fn}
        for exp in exports:
            if exp not in defined_ids:
                raise CheckError(f"Exported function '{exp}' not defined in module")

    def _collect_fn_registry(self, defs: list[dict]):
        for fn in defs:
            if not isinstance(fn, dict):
                raise CheckError(f"Module def must be a dict, got {type(fn)}")
            self._check_fn_schema(fn)
            fn_id = fn.get("id")
            if not fn_id:
                raise CheckError("Function definition missing 'id'")
            if fn_id in self.fn_registry:
                raise CheckError(f"Duplicate function id in module: '{fn_id}'")
            self.fn_registry[fn_id] = fn
            self.call_graph[fn_id] = set()

    def _detect_recursive_calls(self):
        WHITE, GRAY, BLACK = 0, 1, 2
        state: dict[str, int] = {fn_id: WHITE for fn_id in self.call_graph}
        stack: list[str] = []

        def dfs(node: str):
            state[node] = GRAY
            stack.append(node)
            for nxt in self.call_graph.get(node, set()):
                nxt_state = state.get(nxt, WHITE)
                if nxt_state == WHITE:
                    dfs(nxt)
                elif nxt_state == GRAY:
                    cycle_start = stack.index(nxt)
                    cycle = stack[cycle_start:] + [nxt]
                    cycle_text = " -> ".join(cycle)
                    raise CheckError(f"Recursive call detected: {cycle_text}")
            stack.pop()
            state[node] = BLACK

        for fn_id in self.call_graph:
            if state[fn_id] == WHITE:
                dfs(fn_id)

    def _check_fn(self, fn: dict):
        fn_id = fn["id"]
        self.call_graph.setdefault(fn_id, set())

        # L2: collect declared effects
        self.declared_effects = set(fn["effects"])

        # L1: parse return type
        try:
            return_type = parse_type(fn["returns"])
        except Exception as e:
            raise CheckError(f"[{fn_id}] Invalid return type: {e}")

        # L1: parse param types and build env
        env = {}
        for param in fn["params"]:
            if "id" not in param or "type" not in param:
                raise CheckError(f"[{fn_id}] Param must have 'id' and 'type'")
            try:
                t = parse_type(param["type"])
            except Exception as e:
                raise CheckError(f"[{fn_id}] Param '{param['id']}' invalid type: {e}")
            env[param["id"]] = t

        # Check body
        actual_return = self._check_body(fn_id, fn["body"], env, set(), return_type)

    def _check_body(self, fn_id: str, body: list, env: dict, mut_set: set, expected_return: NailType) -> NailType:
        local_env = dict(env)
        local_mut = set(mut_set)
        has_return = False

        for stmt in body:
            if "op" not in stmt:
                raise CheckError(f"[{fn_id}] Statement missing 'op': {stmt}")
            op = stmt["op"]

            if op == "return":
                val_type = self._check_expr(fn_id, stmt.get("val"), local_env)
                if not types_equal(val_type, expected_return):
                    raise CheckError(
                        f"[{fn_id}] Return type mismatch: expected {expected_return}, got {val_type}"
                    )
                has_return = True

            elif op == "let":
                if "id" not in stmt or "val" not in stmt:
                    raise CheckError(f"[{fn_id}] 'let' requires 'id' and 'val'")
                val_type = self._check_expr(fn_id, stmt["val"], local_env)
                if "type" in stmt:
                    declared = parse_type(stmt["type"])
                    if not types_equal(val_type, declared):
                        raise CheckError(
                            f"[{fn_id}] Let '{stmt['id']}' type mismatch: declared {declared}, got {val_type}"
                        )
                local_env[stmt["id"]] = val_type
                # Track mutability: variables are immutable by default
                if stmt.get("mut", False):
                    local_mut.add(stmt["id"])

            elif op == "print":
                # L2: requires IO
                eff = stmt.get("effect")
                if eff != "IO":
                    raise CheckError(f"[{fn_id}] 'print' must declare effect: IO")
                if "IO" not in self.declared_effects:
                    raise NailEffectError(
                        f"[{fn_id}] 'print' uses IO effect, but function does not declare it"
                    )
                val_type = self._check_expr(fn_id, stmt.get("val"), local_env)
                # print accepts string only
                if not isinstance(val_type, StringType):
                    raise CheckError(f"[{fn_id}] 'print' expects string, got {val_type}")

            elif op == "call":
                # Call can be used as a statement (discard return value)
                self._check_op_expr(fn_id, stmt, local_env)

            elif op == "if":
                cond_type = self._check_expr(fn_id, stmt.get("cond"), local_env)
                if not isinstance(cond_type, BoolType):
                    raise CheckError(f"[{fn_id}] 'if' condition must be bool, got {cond_type}")
                if "then" not in stmt:
                    raise CheckError(f"[{fn_id}] 'if' missing 'then'")
                if "else" not in stmt:
                    raise CheckError(f"[{fn_id}] 'if' missing 'else' (required by NAIL spec)")
                self._check_body(fn_id, stmt["then"], local_env, local_mut, expected_return)
                self._check_body(fn_id, stmt["else"], local_env, local_mut, expected_return)

            elif op == "assign":
                if "id" not in stmt or "val" not in stmt:
                    raise CheckError(f"[{fn_id}] 'assign' requires 'id' and 'val'")
                # Verify variable exists in scope
                if stmt["id"] not in local_env:
                    raise CheckError(f"[{fn_id}] 'assign' to undeclared variable: '{stmt['id']}'")
                # Verify variable is mutable (declared with mut: true)
                if stmt["id"] not in local_mut:
                    raise CheckError(
                        f"[{fn_id}] 'assign' to immutable variable: '{stmt['id']}' "
                        f"(declare with \"mut\": true to make it mutable)"
                    )
                val_type = self._check_expr(fn_id, stmt["val"], local_env)
                declared = local_env[stmt["id"]]
                if not types_equal(val_type, declared):
                    raise CheckError(
                        f"[{fn_id}] 'assign' type mismatch for '{stmt['id']}': expected {declared}, got {val_type}"
                    )

            elif op == "loop":
                for field in ("bind", "from", "to", "step", "body"):
                    if field not in stmt:
                        raise CheckError(f"[{fn_id}] 'loop' missing '{field}'")
                from_type = self._check_expr(fn_id, stmt["from"], local_env)
                to_type = self._check_expr(fn_id, stmt["to"], local_env)
                step_type = self._check_expr(fn_id, stmt["step"], local_env)
                if not (isinstance(from_type, IntType) and isinstance(to_type, IntType) and isinstance(step_type, IntType)):
                    raise CheckError(f"[{fn_id}] 'loop' from/to/step must be int")
                loop_env = dict(local_env)
                loop_env[stmt["bind"]] = from_type
                # loop bind variable is immutable; propagate outer mut_set
                self._check_body(fn_id, stmt["body"], loop_env, local_mut, expected_return)

            else:
                raise CheckError(f"[{fn_id}] Unknown op: '{op}'")

        return expected_return

    def _check_expr(self, fn_id: str, expr: Any, env: dict) -> NailType:
        if expr is None:
            raise CheckError(f"[{fn_id}] Expression is None")

        if not isinstance(expr, dict):
            raise CheckError(f"[{fn_id}] Expression must be a dict, got: {type(expr)}")

        # Literal
        if "lit" in expr:
            return self._infer_literal(fn_id, expr)

        # Variable reference
        if "ref" in expr:
            name = expr["ref"]
            if name not in env:
                raise CheckError(f"[{fn_id}] Undefined variable: '{name}'")
            return env[name]

        # Binary / unary operators
        if "op" in expr:
            return self._check_op_expr(fn_id, expr, env)

        raise CheckError(f"[{fn_id}] Unrecognized expression: {expr}")

    def _infer_literal(self, fn_id: str, expr: dict) -> NailType:
        val = expr["lit"]
        if val is None:
            # Typed null — must have type annotation
            if "type" not in expr:
                raise CheckError(f"[{fn_id}] null literal requires 'type' annotation")
            t = parse_type(expr["type"])
            if not isinstance(t, (UnitType, OptionType)):
                raise CheckError(f"[{fn_id}] null can only be unit or option type")
            return t
        elif isinstance(val, bool):
            return BoolType()
        elif isinstance(val, int):
            return IntType(bits=64, overflow="panic")
        elif isinstance(val, float):
            return FloatType(bits=64)
        elif isinstance(val, str):
            return StringType()
        else:
            raise CheckError(f"[{fn_id}] Unknown literal value type: {type(val)}")

    def _check_op_expr(self, fn_id: str, expr: dict, env: dict) -> NailType:
        op = expr["op"]

        ARITH_OPS = {"+", "-", "*", "/", "%"}
        COMPARE_OPS = {"eq", "neq", "lt", "lte", "gt", "gte"}
        BOOL_OPS = {"and", "or"}

        if op in ARITH_OPS:
            l_type = self._check_expr(fn_id, expr.get("l"), env)
            r_type = self._check_expr(fn_id, expr.get("r"), env)
            if not types_equal(l_type, r_type):
                raise CheckError(f"[{fn_id}] Op '{op}' type mismatch: {l_type} vs {r_type}")
            if not isinstance(l_type, (IntType, FloatType)):
                raise CheckError(f"[{fn_id}] Op '{op}' requires numeric type, got {l_type}")
            return l_type

        elif op in COMPARE_OPS:
            l_type = self._check_expr(fn_id, expr.get("l"), env)
            r_type = self._check_expr(fn_id, expr.get("r"), env)
            if not types_equal(l_type, r_type):
                raise CheckError(f"[{fn_id}] Compare '{op}' type mismatch: {l_type} vs {r_type}")
            return BoolType()

        elif op in BOOL_OPS:
            l_type = self._check_expr(fn_id, expr.get("l"), env)
            r_type = self._check_expr(fn_id, expr.get("r"), env)
            if not isinstance(l_type, BoolType) or not isinstance(r_type, BoolType):
                raise CheckError(f"[{fn_id}] Op '{op}' requires bool operands")
            return BoolType()

        elif op == "not":
            v_type = self._check_expr(fn_id, expr.get("v"), env)
            if not isinstance(v_type, BoolType):
                raise CheckError(f"[{fn_id}] 'not' requires bool, got {v_type}")
            return BoolType()

        # Type conversion ops (explicit — no implicit coercions in NAIL)
        elif op == "int_to_str":
            v_type = self._check_expr(fn_id, expr.get("v"), env)
            if not isinstance(v_type, IntType):
                raise CheckError(f"[{fn_id}] 'int_to_str' requires int, got {v_type}")
            return StringType()

        elif op == "float_to_str":
            v_type = self._check_expr(fn_id, expr.get("v"), env)
            if not isinstance(v_type, FloatType):
                raise CheckError(f"[{fn_id}] 'float_to_str' requires float, got {v_type}")
            return StringType()

        elif op == "bool_to_str":
            v_type = self._check_expr(fn_id, expr.get("v"), env)
            if not isinstance(v_type, BoolType):
                raise CheckError(f"[{fn_id}] 'bool_to_str' requires bool, got {v_type}")
            return StringType()

        # String ops
        elif op == "concat":
            l_type = self._check_expr(fn_id, expr.get("l"), env)
            r_type = self._check_expr(fn_id, expr.get("r"), env)
            if not isinstance(l_type, StringType) or not isinstance(r_type, StringType):
                raise CheckError(f"[{fn_id}] 'concat' requires two strings, got {l_type} and {r_type}")
            return StringType()

        elif op == "call":
            return self._check_call_expr(fn_id, expr, env)

        else:
            raise CheckError(f"[{fn_id}] Unknown op in expression: '{op}'")

    def _check_call_expr(self, fn_id: str, expr: dict, env: dict) -> NailType:
        if self.spec.get("kind") != "module":
            raise CheckError(f"[{fn_id}] Function call is only allowed in kind:'module'")

        callee_id = expr.get("fn")
        if not isinstance(callee_id, str) or not callee_id:
            raise CheckError(f"[{fn_id}] 'call' requires string field 'fn'")

        if callee_id not in self.fn_registry:
            raise CheckError(f"[{fn_id}] Unknown function: '{callee_id}'")

        callee = self.fn_registry[callee_id]
        self.call_graph.setdefault(fn_id, set()).add(callee_id)

        callee_effects = set(callee.get("effects", []))
        missing_effects = callee_effects - self.declared_effects
        if missing_effects:
            missing_text = ", ".join(sorted(missing_effects))
            declared_text = ", ".join(sorted(self.declared_effects))
            raise CheckError(
                f"[{fn_id}] Calling '{callee_id}' requires effects {{{missing_text}}}, "
                f"but '{fn_id}' declares {{{declared_text}}}"
            )

        args = expr.get("args", [])
        if not isinstance(args, list):
            raise CheckError(f"[{fn_id}] 'call.args' must be a list")

        params = callee.get("params", [])
        if len(args) != len(params):
            raise CheckError(
                f"[{fn_id}] '{callee_id}' expects {len(params)} args, got {len(args)}"
            )

        for i, (arg_expr, param) in enumerate(zip(args, params)):
            arg_type = self._check_expr(fn_id, arg_expr, env)
            param_type = parse_type(param["type"])
            if not types_equal(arg_type, param_type):
                raise CheckError(
                    f"[{fn_id}] Arg {i} to '{callee_id}' type mismatch: expected {param_type}, got {arg_type}"
                )

        return parse_type(callee["returns"])
