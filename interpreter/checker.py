"""
NAIL Checker — v0.4
L0: JSON schema validation (jsonschema + hand-rolled)
L1: Type checking
L2: Effect checking
"""

import json
from pathlib import Path
from typing import Any
from .types import (
    NailType, NailTypeError, NailEffectError,
    parse_type, types_equal,
    IntType, FloatType, BoolType, StringType, UnitType, OptionType, ResultType,
    VALID_EFFECTS,
)


class CheckError(Exception):
    pass


# Intermediate types used during Result construction (ok/err ops)
class _ResultOkIntermediate:
    def __init__(self, ok_type): self.ok_type = ok_type
    def __repr__(self): return f"<ok({self.ok_type})>"

class _ResultErrIntermediate:
    def __init__(self, err_type): self.err_type = err_type
    def __repr__(self): return f"<err({self.err_type})>"


class Checker:
    def __init__(
        self,
        spec: dict,
        raw_text: str | None = None,
        strict: bool = False,
        modules: dict | None = None,   # {module_id: module_spec} for cross-module imports
    ):
        self.spec = spec
        self.env: dict[str, NailType] = {}
        self.declared_effects: set[str] = set()
        self.fn_registry: dict[str, dict] = {}
        self.call_graph: dict[str, set[str]] = {}
        self.raw_text = raw_text
        self.strict = strict
        self.modules: dict[str, dict] = dict(modules or {})
        # Ensure the entry module itself is registered for circular import detection
        _entry_id = spec.get("id")
        if _entry_id and _entry_id not in self.modules:
            self.modules[_entry_id] = spec
        # module_fn_registry: {module_id: {fn_id: fn_spec}}
        self.module_fn_registry: dict[str, dict[str, dict]] = {}
        # Type aliases for the current module and imported modules
        self.type_aliases: dict[str, dict] = {}
        self._alias_spec_cache: dict[str, dict] = {}
        self.module_type_aliases: dict[str, dict[str, dict]] = {}
        self._module_alias_spec_cache: dict[str, dict[str, dict]] = {}
        # Track which imported modules have already been body-checked (Bug 2 fix)
        self._checked_module_ids: set[str] = set()

    # -----------------------------------------------------------------------
    # L0: Schema validation
    # -----------------------------------------------------------------------

    def check_l0(self):
        """Validate basic required fields (jsonschema L0 + strict canonical check)."""
        # Strict mode: verify canonical form (JCS / RFC 8785 subset)
        if self.strict and self.raw_text is not None:
            canonical = json.dumps(self.spec, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
            if self.raw_text.strip() != canonical:
                raise CheckError("Input is not in canonical form. Run 'nail canonicalize' to fix.")

        # Real L0: JSON Schema validation via jsonschema
        _schema_path = Path(__file__).resolve().parents[1] / "schema" / "nail-l0.json"
        if _schema_path.exists():
            try:
                from jsonschema import validate as _jv, ValidationError as _VE
                with open(_schema_path) as _f:
                    _schema = json.load(_f)
                try:
                    _jv(instance=self.spec, schema=_schema)
                except _VE as e:
                    raise CheckError(f"L0 schema violation: {e.message}") from e
            except ImportError:
                pass  # jsonschema not installed; fall through to hand-rolled checks

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

    def _set_module_type_aliases(self, mod: dict):
        raw_types = mod.get("types", {})
        if raw_types is None:
            raw_types = {}
        if not isinstance(raw_types, dict):
            raise CheckError("Module 'types' must be a dict")
        for alias_name, alias_spec in raw_types.items():
            if not isinstance(alias_name, str) or not alias_name:
                raise CheckError("Type alias names must be non-empty strings")
            if not isinstance(alias_spec, dict):
                raise CheckError(f"Type alias '{alias_name}' must map to a type dict")
        self.type_aliases = raw_types
        self._alias_spec_cache = {}
        module_id = mod.get("id", "<module>")
        for alias_name in self.type_aliases:
            self._resolve_alias_spec(
                alias_name,
                aliases=self.type_aliases,
                cache=self._alias_spec_cache,
                stack=[],
                module_id=module_id,
            )

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
            raise CheckError(f"Circular type alias detected in module '{module_id}': {cycle}")
        if alias_name not in aliases:
            raise CheckError(f"Unknown type alias '{alias_name}' in module '{module_id}'")
        alias_spec = aliases[alias_name]
        if not isinstance(alias_spec, dict):
            raise CheckError(f"Type alias '{alias_name}' must map to a type dict")
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
            raise CheckError(f"Type spec must be a dict, got {type(type_spec)}")
        t = type_spec.get("type")
        if t == "alias":
            alias_name = type_spec.get("name")
            if not isinstance(alias_name, str) or not alias_name:
                raise CheckError("Alias type requires non-empty string field 'name'")
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
        return dict(type_spec)

    def _parse_type(self, type_spec: dict, module_id: str | None = None) -> NailType:
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
        self._set_module_type_aliases(mod)

        # Process imports: validate and build module_fn_registry
        self._process_imports(mod)

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

    def _process_imports(self, mod: dict):
        """Validate import declarations and populate module_fn_registry."""
        imports = mod.get("imports", [])
        if not imports:
            return
        # Circular import detection: track visiting set
        this_id = mod.get("id", "<entrypoint>")
        self._detect_circular_imports(this_id, set())

        for imp in imports:
            module_id = imp.get("module")
            fns = imp.get("fns", [])
            if not module_id:
                raise CheckError("Import declaration missing 'module' field")
            if module_id not in self.modules:
                raise CheckError(
                    f"Imported module '{module_id}' not found. "
                    f"Pass it via modules={{'{module_id}': ...}} or --modules CLI flag."
                )
            imported_mod = self.modules[module_id]
            imported_aliases = imported_mod.get("types", {})
            if imported_aliases is None:
                imported_aliases = {}
            if not isinstance(imported_aliases, dict):
                raise CheckError(f"Module '{module_id}' has invalid 'types' field (must be dict)")
            self.module_type_aliases[module_id] = imported_aliases
            self._module_alias_spec_cache[module_id] = {}
            for alias_name, alias_spec in imported_aliases.items():
                if not isinstance(alias_name, str) or not alias_name:
                    raise CheckError(f"Module '{module_id}' has invalid type alias name")
                if not isinstance(alias_spec, dict):
                    raise CheckError(f"Module '{module_id}' type alias '{alias_name}' must be a type dict")
                self._resolve_alias_spec(
                    alias_name,
                    aliases=imported_aliases,
                    cache=self._module_alias_spec_cache[module_id],
                    stack=[],
                    module_id=module_id,
                )
            # Build fn lookup for the imported module
            imported_fns = {fn["id"]: fn for fn in imported_mod.get("defs", []) if "id" in fn}
            for fn_id in fns:
                if fn_id not in imported_fns:
                    raise CheckError(
                        f"Function '{fn_id}' not found in module '{module_id}'"
                    )
            self.module_fn_registry[module_id] = imported_fns
            # Bug 2 fix: also validate the body of the imported module, not just its signatures
            self._check_imported_module_body(module_id)

    def _check_imported_module_body(self, module_id: str):
        """Recursively validate the body of an imported module (Bug 2 fix).

        Uses _checked_module_ids to prevent infinite recursion on circular
        structures (circular imports are caught first by _detect_circular_imports).
        """
        if module_id in self._checked_module_ids:
            return
        self._checked_module_ids.add(module_id)
        imported_mod = self.modules.get(module_id)
        if imported_mod is None:
            return
        sub = Checker(imported_mod, modules=self.modules)
        sub._checked_module_ids = self._checked_module_ids  # share the visited set
        sub.check()

    def _detect_circular_imports(self, module_id: str, visiting: set[str]):
        """DFS to detect import cycles."""
        if module_id in visiting:
            path = " → ".join(sorted(visiting)) + f" → {module_id}"
            raise CheckError(f"Circular import detected: {path}")
        if module_id not in self.modules:
            return
        mod = self.modules[module_id]
        visiting = visiting | {module_id}
        for imp in mod.get("imports", []):
            dep = imp.get("module")
            if dep:
                self._detect_circular_imports(dep, visiting)

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
            return_type = self._parse_type(fn["returns"])
        except Exception as e:
            raise CheckError(f"[{fn_id}] Invalid return type: {e}")

        # L1: parse param types and build env
        env = {}
        for param in fn["params"]:
            if "id" not in param or "type" not in param:
                raise CheckError(f"[{fn_id}] Param must have 'id' and 'type'")
            try:
                t = self._parse_type(param["type"])
            except Exception as e:
                raise CheckError(f"[{fn_id}] Param '{param['id']}' invalid type: {e}")
            env[param["id"]] = t

        # Check body
        guaranteed = self._check_body(fn_id, fn["body"], env, set(), return_type)
        if not guaranteed and not isinstance(return_type, UnitType):
            raise CheckError(
                f"[{fn_id}] Not all code paths return a value (return type: {return_type})"
            )

    def _check_body(self, fn_id: str, body: list, env: dict, mut_set: set, expected_return: NailType) -> bool:
        """Check body statements; return True if all paths are guaranteed to return."""
        local_env = dict(env)
        local_mut = set(mut_set)
        guaranteed_return = False

        for stmt in body:
            if "op" not in stmt:
                raise CheckError(f"[{fn_id}] Statement missing 'op': {stmt}")
            op = stmt["op"]

            if op == "return":
                val_type = self._check_expr(fn_id, stmt.get("val"), local_env)
                # Handle Result construction (ok/err ops)
                if isinstance(expected_return, ResultType):
                    if isinstance(val_type, _ResultOkIntermediate):
                        if not types_equal(val_type.ok_type, expected_return.ok):
                            raise CheckError(
                                f"[{fn_id}] ok() value type {val_type.ok_type} does not match "
                                f"result<ok={expected_return.ok}, err={expected_return.err}>"
                            )
                    elif isinstance(val_type, _ResultErrIntermediate):
                        if not types_equal(val_type.err_type, expected_return.err):
                            raise CheckError(
                                f"[{fn_id}] err() value type {val_type.err_type} does not match "
                                f"result<ok={expected_return.ok}, err={expected_return.err}>"
                            )
                    elif not types_equal(val_type, expected_return):
                        raise CheckError(
                            f"[{fn_id}] Return type mismatch: expected {expected_return}, got {val_type}"
                        )
                elif not types_equal(val_type, expected_return):
                    raise CheckError(
                        f"[{fn_id}] Return type mismatch: expected {expected_return}, got {val_type}"
                    )
                guaranteed_return = True

            elif op == "let":
                if "id" not in stmt or "val" not in stmt:
                    raise CheckError(f"[{fn_id}] 'let' requires 'id' and 'val'")
                val_type = self._check_expr(fn_id, stmt["val"], local_env)
                if "type" in stmt:
                    declared = self._parse_type(stmt["type"])
                    # Handle Result construction in let bindings
                    if isinstance(declared, ResultType) and isinstance(val_type, _ResultOkIntermediate):
                        if not types_equal(val_type.ok_type, declared.ok):
                            raise CheckError(
                                f"[{fn_id}] Let '{stmt['id']}': ok() value {val_type.ok_type} != result.ok {declared.ok}"
                            )
                        val_type = declared
                    elif isinstance(declared, ResultType) and isinstance(val_type, _ResultErrIntermediate):
                        if not types_equal(val_type.err_type, declared.err):
                            raise CheckError(
                                f"[{fn_id}] Let '{stmt['id']}': err() value {val_type.err_type} != result.err {declared.err}"
                            )
                        val_type = declared
                    elif not types_equal(val_type, declared):
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

            elif op == "read_file":
                # L2: requires FS effect; "path" must be string; result stored via let
                if "FS" not in self.declared_effects:
                    raise NailEffectError(
                        f"[{fn_id}] 'read_file' uses FS effect, but function does not declare it"
                    )
                if "path" not in stmt:
                    raise CheckError(f"[{fn_id}] 'read_file' requires 'path'")
                path_type = self._check_expr(fn_id, stmt["path"], local_env)
                if not isinstance(path_type, StringType):
                    raise CheckError(f"[{fn_id}] 'read_file' path must be string, got {path_type}")
                # If result bound via 'into', add to env
                if "into" in stmt:
                    local_env[stmt["into"]] = StringType()

            elif op == "http_get":
                # L2: requires NET effect; "url" must be string; result stored via 'into'
                if "NET" not in self.declared_effects:
                    raise NailEffectError(
                        f"[{fn_id}] 'http_get' uses NET effect, but function does not declare it"
                    )
                if "url" not in stmt:
                    raise CheckError(f"[{fn_id}] 'http_get' requires 'url'")
                url_type = self._check_expr(fn_id, stmt["url"], local_env)
                if not isinstance(url_type, StringType):
                    raise CheckError(f"[{fn_id}] 'http_get' url must be string, got {url_type}")
                if "into" in stmt:
                    local_env[stmt["into"]] = StringType()

            elif op == "match_result":
                # L1: exhaustive pattern match on result<Ok, Err>
                val_type = self._check_expr(fn_id, stmt.get("val"), local_env)
                if not isinstance(val_type, ResultType):
                    raise CheckError(
                        f"[{fn_id}] 'match_result' expects result<Ok, Err>, got {val_type}"
                    )
                ok_bind = stmt.get("ok_bind")
                err_bind = stmt.get("err_bind")
                # ok branch
                ok_env = dict(local_env)
                if ok_bind:
                    ok_env[ok_bind] = val_type.ok
                ok_guaranteed = self._check_body(fn_id, stmt.get("ok_body", []), ok_env, local_mut, expected_return)
                # err branch
                err_env = dict(local_env)
                if err_bind:
                    err_env[err_bind] = val_type.err
                err_guaranteed = self._check_body(fn_id, stmt.get("err_body", []), err_env, local_mut, expected_return)
                if ok_guaranteed and err_guaranteed:
                    guaranteed_return = True

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
                then_guaranteed = self._check_body(fn_id, stmt["then"], local_env, local_mut, expected_return)
                else_guaranteed = self._check_body(fn_id, stmt["else"], local_env, local_mut, expected_return)
                if then_guaranteed and else_guaranteed:
                    guaranteed_return = True

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

        return guaranteed_return

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
            t = self._parse_type(expr["type"])
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
            # v0.3: expression-level overflow override
            expr_overflow = expr.get("overflow")
            if expr_overflow is not None:
                VALID_EXPR_OVERFLOWS = {"panic", "wrap", "sat"}
                if expr_overflow not in VALID_EXPR_OVERFLOWS:
                    raise CheckError(
                        f"[{fn_id}] Invalid overflow mode '{expr_overflow}' on op '{op}'. "
                        f"Must be one of: {sorted(VALID_EXPR_OVERFLOWS)}"
                    )
                if not isinstance(l_type, IntType):
                    raise CheckError(
                        f"[{fn_id}] overflow mode '{expr_overflow}' is only valid for integer types, got {l_type}"
                    )
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

        elif op == "ok":
            # Result::Ok constructor — returns _ResultOkIntermediate for return-site checking
            val_type = self._check_expr(fn_id, expr.get("val"), env)
            return _ResultOkIntermediate(val_type)

        elif op == "err":
            # Result::Err constructor — returns _ResultErrIntermediate for return-site checking
            val_type = self._check_expr(fn_id, expr.get("val"), env)
            return _ResultErrIntermediate(val_type)

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

        # Cross-module call: resolve from module_fn_registry
        cross_module = expr.get("module")
        if cross_module:
            if cross_module not in self.module_fn_registry:
                raise CheckError(
                    f"[{fn_id}] Module '{cross_module}' not imported. "
                    f"Add it to imports[] and pass modules={{'{cross_module}': ...}}."
                )
            mod_fns = self.module_fn_registry[cross_module]
            if callee_id not in mod_fns:
                raise CheckError(f"[{fn_id}] Function '{callee_id}' not found in module '{cross_module}'")
            callee = mod_fns[callee_id]
            # Effect propagation across module boundary
            callee_effects = set(callee.get("effects", []))
            missing_effects = callee_effects - self.declared_effects
            if missing_effects:
                raise CheckError(
                    f"[{fn_id}] Cross-module call to '{cross_module}.{callee_id}' requires "
                    f"effects {{{', '.join(sorted(missing_effects))}}}, but '{fn_id}' only has "
                    f"{{{', '.join(sorted(self.declared_effects))}}}"
                )
            args = expr.get("args", [])
            params = callee.get("params", [])
            if len(args) != len(params):
                raise CheckError(
                    f"[{fn_id}] '{cross_module}.{callee_id}' expects {len(params)} args, got {len(args)}"
                )
            for i, (arg_expr, param) in enumerate(zip(args, params)):
                arg_type = self._check_expr(fn_id, arg_expr, env)
                param_type = self._parse_type(param["type"], module_id=cross_module)
                if not types_equal(arg_type, param_type):
                    raise CheckError(
                        f"[{fn_id}] Arg {i} to '{cross_module}.{callee_id}': expected {param_type}, got {arg_type}"
                    )
            return self._parse_type(callee["returns"], module_id=cross_module)

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
            param_type = self._parse_type(param["type"])
            if not types_equal(arg_type, param_type):
                raise CheckError(
                    f"[{fn_id}] Arg {i} to '{callee_id}' type mismatch: expected {param_type}, got {arg_type}"
                )

        return self._parse_type(callee["returns"])
