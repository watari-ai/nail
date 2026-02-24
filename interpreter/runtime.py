"""
NAIL Runtime — v0.4
Executes validated NAIL programs.
"""

from typing import Any
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from .types import (
    IntType, FloatType, BoolType, StringType, UnitType, OptionType,
    NailRuntimeError, NailTypeError, parse_type, types_equal,
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
        self.declared_effects = set()
        self.declared_effect_caps: dict[str, list[dict]] = {}
        self.fn_registry: dict[str, dict] = {}
        self.type_aliases: dict[str, dict] = {}
        self._alias_spec_cache: dict[str, dict] = {}
        if spec.get("kind") == "module":
            self.fn_registry = {fn["id"]: fn for fn in spec.get("defs", [])}
            self.type_aliases = spec.get("types", {}) or {}
        # Build module_fn_registry for cross-module calls
        self.module_fn_registry: dict[str, dict[str, dict]] = {}
        self.module_type_aliases: dict[str, dict[str, dict]] = {}
        self._module_alias_spec_cache: dict[str, dict[str, dict]] = {}
        for mod_id, mod_spec in (modules or {}).items():
            self.module_fn_registry[mod_id] = {
                fn["id"]: fn for fn in mod_spec.get("defs", []) if "id" in fn
            }
            self.module_type_aliases[mod_id] = mod_spec.get("types", {}) or {}
        # Bug 3 fix: stack of currently-executing module IDs for local call resolution
        self._module_id_stack: list[str | None] = []
        self._effect_policy_stack: list[tuple[set[str], dict[str, list[dict]]]] = []

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

    def _run_fn(self, fn: dict, args: dict, module_id: str | None = None) -> Any:
        fn_effects, fn_caps = self._collect_declared_effects(fn.get("effects", []))
        self._module_id_stack.append(module_id)
        self._effect_policy_stack.append((fn_effects, fn_caps))
        try:
            env = dict(args)
            # Bind params
            for param in fn.get("params", []):
                pid = param["id"]
                if pid not in env:
                    raise NailRuntimeError(f"Missing argument: {pid}")
            result = self._run_body(fn["body"], env)
            # At the top-level function boundary, _CONTINUE means implicit unit return
            return UNIT if result is _CONTINUE else result
        finally:
            self._effect_policy_stack.pop()
            self._module_id_stack.pop()

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

        elif op == "enum_make":
            tag = stmt.get("tag")
            if not isinstance(tag, str) or not tag:
                raise NailRuntimeError("'enum_make' requires non-empty string field 'tag'")
            fields_expr = stmt.get("fields", {})
            if fields_expr is None:
                fields_expr = {}
            if not isinstance(fields_expr, dict):
                raise NailRuntimeError("'enum_make.fields' must be an object")
            value = {"__tag__": tag}
            for field_name, field_expr in fields_expr.items():
                value[field_name] = self._eval(field_expr, env)
            into = stmt.get("into")
            if not isinstance(into, str) or not into:
                raise NailRuntimeError("'enum_make' requires non-empty string field 'into'")
            env[into] = value
            return _CONTINUE

        elif op == "match_enum":
            enum_val = self._eval(stmt.get("val"), env)
            if not isinstance(enum_val, dict) or "__tag__" not in enum_val:
                raise NailRuntimeError("'match_enum' expects enum object with '__tag__'")
            tag = enum_val["__tag__"]
            if not isinstance(tag, str):
                raise NailRuntimeError("'match_enum' enum tag must be string")
            matched_case = None
            for case in stmt.get("cases", []):
                if isinstance(case, dict) and case.get("tag") == tag:
                    matched_case = case
                    break
            if matched_case is not None:
                binds = matched_case.get("binds", {})
                if binds is None:
                    binds = {}
                if not isinstance(binds, dict):
                    raise NailRuntimeError(f"'match_enum' binds for tag '{tag}' must be an object")
                for field_name, bind_name in binds.items():
                    if field_name not in enum_val:
                        raise NailRuntimeError(f"'match_enum' field '{field_name}' not found for tag '{tag}'")
                    env[bind_name] = enum_val[field_name]
                ret = self._run_body(matched_case.get("body", []), env)
            else:
                if "default" not in stmt:
                    raise NailRuntimeError(f"'match_enum' has no case for tag '{tag}' and no default")
                ret = self._run_body(stmt.get("default", []), env)
            if ret is not _CONTINUE:
                return ret
            return _CONTINUE

        elif op == "read_file":
            effect = self._normalize_effect_kind(stmt.get("effect"))
            if effect != "FS":
                raise NailRuntimeError("'read_file' must declare effect: FS")
            self._require_effect("FS", "'read_file' uses FS effect, but function does not declare it")
            path = self._eval(stmt["path"], env)
            if not isinstance(path, str):
                raise NailRuntimeError(f"'read_file' path must evaluate to string, got {type(path).__name__}")
            self._enforce_fs_boundary(path)
            try:
                content = Path(path).read_text(encoding="utf-8")
            except OSError as e:
                raise NailRuntimeError(f"read_file failed for {path!r}: {e}") from e
            if "into" in stmt:
                env[stmt["into"]] = content
            return _CONTINUE

        elif op == "http_get":
            effect = self._normalize_effect_kind(stmt.get("effect"))
            if effect != "NET":
                raise NailRuntimeError("'http_get' must declare effect: NET")
            self._require_effect("NET", "'http_get' uses NET effect, but function does not declare it")
            url = self._eval(stmt["url"], env)
            if not isinstance(url, str):
                raise NailRuntimeError(f"'http_get' url must evaluate to string, got {type(url).__name__}")
            self._enforce_net_boundary(url)
            try:
                with urlopen(url, timeout=10) as resp:
                    body = resp.read()
            except OSError as e:
                raise NailRuntimeError(f"http_get failed for {url!r}: {e}") from e
            text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
            if "into" in stmt:
                env[stmt["into"]] = text
            return _CONTINUE

        elif op == "call":
            self._eval_op(stmt, env)
            return _CONTINUE

        elif op == "list_push":
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
                current_module_id = self._module_id_stack[-1] if self._module_id_stack else None
                t = self._parse_type(expr.get("type", {"type": "unit"}), module_id=current_module_id)
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

        # Collection ops (v0.4)
        elif op == "list_get":
            list_expr = expr.get("list")
            if not isinstance(list_expr, dict) or "ref" not in list_expr:
                raise NailTypeError("'list_get.list' must be a variable reference")
            list_val = self._eval(list_expr, env)
            index = self._eval(expr.get("index"), env)
            if not isinstance(list_val, list):
                raise NailTypeError(f"'list_get' requires list value, got {type(list_val).__name__}")
            if not isinstance(index, int) or isinstance(index, bool):
                raise NailTypeError(f"'list_get.index' must be int, got {type(index).__name__}")
            if index < 0 or index >= len(list_val):
                raise NailRuntimeError(f"'list_get' index out of bounds: {index} (len={len(list_val)})")
            return list_val[index]

        elif op == "list_push":
            list_expr = expr.get("list")
            if not isinstance(list_expr, dict) or "ref" not in list_expr:
                raise NailTypeError("'list_push.list' must be a variable reference")
            list_name = list_expr["ref"]
            if list_name not in env:
                raise NailRuntimeError(f"Undefined variable: {list_name}")
            list_val = env[list_name]
            if not isinstance(list_val, list):
                raise NailTypeError(f"'list_push' requires list value, got {type(list_val).__name__}")
            value = self._eval(expr.get("value"), env)
            if list_val and type(value) is not type(list_val[0]):
                raise NailTypeError(
                    f"'list_push.value' type mismatch: expected {type(list_val[0]).__name__}, got {type(value).__name__}"
                )
            list_val.append(value)
            return UNIT

        elif op == "list_len":
            list_expr = expr.get("list")
            if not isinstance(list_expr, dict) or "ref" not in list_expr:
                raise NailTypeError("'list_len.list' must be a variable reference")
            list_val = self._eval(list_expr, env)
            if not isinstance(list_val, list):
                raise NailTypeError(f"'list_len' requires list value, got {type(list_val).__name__}")
            return len(list_val)

        elif op == "map_get":
            map_expr = expr.get("map")
            if not isinstance(map_expr, dict) or "ref" not in map_expr:
                raise NailTypeError("'map_get.map' must be a variable reference")
            map_val = self._eval(map_expr, env)
            key = self._eval(expr.get("key"), env)
            if not isinstance(map_val, dict):
                raise NailTypeError(f"'map_get' requires map value, got {type(map_val).__name__}")
            if map_val:
                sample_key = next(iter(map_val.keys()))
                if type(key) is not type(sample_key):
                    raise NailTypeError(
                        f"'map_get.key' type mismatch: expected {type(sample_key).__name__}, got {type(key).__name__}"
                    )
            if key not in map_val:
                raise NailRuntimeError(f"'map_get' key not found: {key!r}")
            return map_val[key]

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
                call_module_id = cross_module
            else:
                # Bug 3 fix: resolve local calls in the currently-executing module first,
                # then fall back to the entry module's fn_registry.
                current_mod = self._module_id_stack[-1] if self._module_id_stack else None
                if current_mod and current_mod in self.module_fn_registry:
                    mod_fns = self.module_fn_registry[current_mod]
                    if callee_id in mod_fns:
                        callee = mod_fns[callee_id]
                        call_module_id = current_mod
                    elif callee_id in self.fn_registry:
                        callee = self.fn_registry[callee_id]
                        call_module_id = None
                    else:
                        raise NailRuntimeError(f"Unknown function: {callee_id!r}")
                else:
                    if callee_id not in self.fn_registry:
                        raise NailRuntimeError(f"Unknown function: {callee_id!r}")
                    callee = self.fn_registry[callee_id]
                    call_module_id = None

            args_expr = expr.get("args", [])
            params = callee.get("params", [])
            if len(args_expr) != len(params):
                raise NailRuntimeError(
                    f"Function '{callee_id}' expects {len(params)} args, got {len(args_expr)}"
                )
            call_args = {}
            for param, arg_expr in zip(params, args_expr):
                call_args[param["id"]] = self._eval(arg_expr, env)
            return self._run_fn(callee, call_args, module_id=call_module_id)

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

    def _resolve_alias_spec(
        self,
        alias_name: str,
        *,
        aliases: dict[str, dict],
        cache: dict[str, dict],
        stack: list[str],
        module_id: str,
    ) -> dict:
        if alias_name in cache:
            return cache[alias_name]
        if alias_name in stack:
            cycle = " -> ".join(stack + [alias_name])
            raise NailRuntimeError(f"Circular type alias detected in module '{module_id}': {cycle}")
        if alias_name not in aliases:
            raise NailRuntimeError(f"Unknown type alias '{alias_name}' in module '{module_id}'")
        alias_spec = aliases[alias_name]
        if not isinstance(alias_spec, dict):
            raise NailRuntimeError(f"Type alias '{alias_name}' in module '{module_id}' must be a type dict")
        resolved = self._resolve_type_spec(
            alias_spec,
            aliases=aliases,
            cache=cache,
            stack=stack + [alias_name],
            module_id=module_id,
        )
        cache[alias_name] = resolved
        return resolved

    def _resolve_type_spec(
        self,
        type_spec: dict,
        *,
        aliases: dict[str, dict],
        cache: dict[str, dict],
        stack: list[str],
        module_id: str,
    ) -> dict:
        if not isinstance(type_spec, dict):
            raise NailRuntimeError(f"Type spec must be a dict, got {type(type_spec)}")
        t = type_spec.get("type")
        if t == "alias":
            alias_name = type_spec.get("name")
            if not isinstance(alias_name, str) or not alias_name:
                raise NailRuntimeError("Alias type requires non-empty string field 'name'")
            return self._resolve_alias_spec(
                alias_name,
                aliases=aliases,
                cache=cache,
                stack=stack,
                module_id=module_id,
            )
        if t == "option" and "inner" in type_spec:
            resolved = dict(type_spec)
            resolved["inner"] = self._resolve_type_spec(
                type_spec["inner"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            return resolved
        if t == "list" and "inner" in type_spec:
            resolved = dict(type_spec)
            resolved["inner"] = self._resolve_type_spec(
                type_spec["inner"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            return resolved
        if t == "map" and "key" in type_spec and "value" in type_spec:
            resolved = dict(type_spec)
            resolved["key"] = self._resolve_type_spec(
                type_spec["key"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            resolved["value"] = self._resolve_type_spec(
                type_spec["value"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            return resolved
        if t == "result" and "ok" in type_spec and "err" in type_spec:
            resolved = dict(type_spec)
            resolved["ok"] = self._resolve_type_spec(
                type_spec["ok"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            resolved["err"] = self._resolve_type_spec(
                type_spec["err"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            return resolved
        if t == "enum":
            variants = type_spec.get("variants")
            if not isinstance(variants, list):
                return dict(type_spec)
            resolved = dict(type_spec)
            resolved_variants = []
            for variant in variants:
                if not isinstance(variant, dict):
                    resolved_variants.append(variant)
                    continue
                rv = dict(variant)
                fields = variant.get("fields")
                if isinstance(fields, list):
                    resolved_fields = []
                    for field in fields:
                        if not isinstance(field, dict):
                            resolved_fields.append(field)
                            continue
                        rf = dict(field)
                        if "type" in field:
                            rf["type"] = self._resolve_type_spec(
                                field["type"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
                            )
                        resolved_fields.append(rf)
                    rv["fields"] = resolved_fields
                resolved_variants.append(rv)
            resolved["variants"] = resolved_variants
            return resolved
        return dict(type_spec)

    def _parse_type(self, type_spec: dict, module_id: str | None = None):
        if module_id is None:
            aliases = self.type_aliases
            cache = self._alias_spec_cache
            target_module_id = self.spec.get("id", "<module>")
        else:
            aliases = self.module_type_aliases.get(module_id, {})
            cache = self._module_alias_spec_cache.setdefault(module_id, {})
            target_module_id = module_id
        resolved = self._resolve_type_spec(
            type_spec,
            aliases=aliases,
            cache=cache,
            stack=[],
            module_id=target_module_id,
        )
        return parse_type(resolved)

    def _normalize_effect_kind(self, kind: Any) -> str:
        if not isinstance(kind, str):
            return ""
        if kind == "Net":
            return "NET"
        return kind

    def _collect_declared_effects(self, effect_decls: list[Any]) -> tuple[set[str], dict[str, list[dict]]]:
        kinds: set[str] = set()
        caps: dict[str, list[dict]] = {}
        for effect_decl in effect_decls:
            if isinstance(effect_decl, str):
                kind = self._normalize_effect_kind(effect_decl)
                kinds.add(kind)
                continue
            if isinstance(effect_decl, dict):
                kind = self._normalize_effect_kind(effect_decl.get("kind"))
                if not kind:
                    raise NailRuntimeError("Structured effect requires string field 'kind'")
                kinds.add(kind)
                cap = dict(effect_decl)
                cap["kind"] = kind
                caps.setdefault(kind, []).append(cap)
                continue
            raise NailRuntimeError(f"Effect declarations must be string or object, got {type(effect_decl)}")
        return kinds, caps

    def _current_effect_policy(self) -> tuple[set[str], dict[str, list[dict]]]:
        if not self._effect_policy_stack:
            return set(), {}
        return self._effect_policy_stack[-1]

    def _require_effect(self, effect_kind: str, message: str) -> None:
        kinds, _ = self._current_effect_policy()
        if effect_kind not in kinds:
            raise NailRuntimeError(message)

    def _enforce_fs_boundary(self, path: str) -> None:
        _, caps = self._current_effect_policy()
        fs_caps = caps.get("FS", [])
        if not fs_caps:
            return
        for cap in fs_caps:
            if self._fs_capability_allows(cap, path):
                return
        raise NailRuntimeError(f"read_file blocked by FS capability policy: {path!r}")

    def _enforce_net_boundary(self, url: str) -> None:
        # Scheme validation: only http/https are permitted regardless of capability policy.
        parsed_scheme = urlparse(url)
        if parsed_scheme.scheme not in ("http", "https"):
            raise NailRuntimeError(
                f"http_get blocked: scheme {parsed_scheme.scheme!r} not allowed (only 'http' and 'https' are permitted)"
            )
        _, caps = self._current_effect_policy()
        net_caps = caps.get("NET", [])
        if not net_caps:
            return
        for cap in net_caps:
            if self._net_capability_allows(cap, url):
                return
        raise NailRuntimeError(f"http_get blocked by NET capability policy: {url!r}")

    def _fs_capability_allows(self, cap: dict, path_value: str) -> bool:
        ops = cap.get("ops")
        if isinstance(ops, list) and "read" not in ops:
            return False
        allow_entries = cap.get("allow", [])
        target_path = Path(path_value)
        target = (Path.cwd() / target_path).resolve(strict=False) if not target_path.is_absolute() else target_path.resolve(strict=False)
        for allowed in allow_entries:
            base_path = Path(str(allowed))
            base = (Path.cwd() / base_path).resolve(strict=False) if not base_path.is_absolute() else base_path.resolve(strict=False)
            try:
                target.relative_to(base)
                return True
            except ValueError:
                continue
        return False

    def _net_capability_allows(self, cap: dict, url_value: str) -> bool:
        parsed = urlparse(url_value)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        ops = cap.get("ops")
        if isinstance(ops, list) and "get" not in ops:
            return False
        allow_domains = cap.get("allow", [])
        return host in {str(domain).lower() for domain in allow_domains}


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
