"""
NAIL TypeResolver — shared type-alias resolution logic (DRY helper, Issue #95).

Both ``Checker`` and ``Runtime`` perform identical alias-resolution passes.
This module provides a single ``TypeResolver`` class parameterised by the
error class to raise, so the logic lives in exactly one place.
"""

from __future__ import annotations


class TypeResolver:
    """Resolve type alias specs with cycle detection and generic instantiation.

    Parameters
    ----------
    error_cls:
        Exception class to raise on errors.  Checker passes ``CheckError``;
        Runtime passes ``NailRuntimeError``.  Both share the same constructor
        signature ``(message: str, code: str = ..., **extra)``.
    """

    def __init__(self, error_cls: type[Exception]) -> None:
        self.error_cls = error_cls

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def substitute_params_in_spec(spec: dict, subst: dict[str, dict]) -> dict:
        """Substitute type-param placeholders in a raw type spec dict.

        Replaces any ``{"type": "param", "name": "T"}`` nodes with the
        concrete type dict from ``subst[T]``.  Used when instantiating
        generic type aliases (Issue #62 / #74).
        """
        if not isinstance(spec, dict):
            return spec
        if spec.get("type") == "param":
            name = spec.get("name", "")
            if name in subst:
                return subst[name]
        result: dict = {}
        for k, v in spec.items():
            if isinstance(v, dict):
                result[k] = TypeResolver.substitute_params_in_spec(v, subst)
            elif isinstance(v, list):
                result[k] = [
                    TypeResolver.substitute_params_in_spec(i, subst) if isinstance(i, dict) else i
                    for i in v
                ]
            else:
                result[k] = v
        return result

    def resolve_alias_spec(
        self,
        alias_name: str,
        *,
        aliases: dict[str, dict],
        cache: dict[str, dict],
        stack: list[str],
        module_id: str,
        type_args: list[dict] | None = None,
    ) -> dict:
        """Resolve a type alias by name.

        For generic aliases (those with ``type_params``), ``type_args`` must
        be provided (a list of already-resolved concrete type specs).  Generic
        aliases are never cached because each instantiation produces a
        different type.

        For non-generic aliases the result is memoised in ``cache``.
        """
        if alias_name not in aliases:
            raise self.error_cls(
                f"Unknown type alias '{alias_name}' in module '{module_id}'"
            )
        alias_spec = aliases[alias_name]
        if not isinstance(alias_spec, dict):
            raise self.error_cls(
                f"Type alias '{alias_name}' in module '{module_id}' must be a type dict"
            )

        type_params: list[str] = alias_spec.get("type_params") or []
        is_generic = bool(type_params)

        if is_generic:
            # Generic alias — requires concrete type args; never cached.
            provided = type_args or []
            if len(provided) != len(type_params):
                raise self.error_cls(
                    f"Generic alias '{alias_name}' requires {len(type_params)} type argument(s), "
                    f"got {len(provided)}",
                    code="GENERIC_ALIAS_ARITY",
                )
            subst = {type_params[i]: provided[i] for i in range(len(type_params))}
            # Strip type_params from body spec before substitution/resolution
            body_spec = {k: v for k, v in alias_spec.items() if k != "type_params"}
            body_spec = TypeResolver.substitute_params_in_spec(body_spec, subst)
            return self.resolve_type_spec(
                body_spec,
                aliases=aliases,
                cache=cache,
                stack=stack + [alias_name],
                module_id=module_id,
            )

        # Non-generic path — use cache and cycle detection.
        if alias_name in cache:
            return cache[alias_name]
        if alias_name in stack:
            cycle = " -> ".join(stack + [alias_name])
            raise self.error_cls(
                f"Circular type alias detected in module '{module_id}': {cycle}"
            )
        resolved = self.resolve_type_spec(
            alias_spec,
            aliases=aliases,
            cache=cache,
            stack=stack + [alias_name],
            module_id=module_id,
        )
        cache[alias_name] = resolved
        return resolved

    def resolve_type_spec(
        self,
        type_spec: dict,
        *,
        aliases: dict[str, dict],
        cache: dict[str, dict],
        stack: list[str],
        module_id: str,
    ) -> dict:
        """Recursively resolve a raw type spec dict, expanding alias references."""
        if not isinstance(type_spec, dict):
            raise self.error_cls(
                f"Type spec must be a dict, got {type(type_spec)}"
            )
        t = type_spec.get("type")
        if t == "alias":
            alias_name = type_spec.get("name")
            if not isinstance(alias_name, str) or not alias_name:
                raise self.error_cls(
                    "Alias type requires non-empty string field 'name'"
                )
            # Resolve type args (if any) for generic alias instantiation
            raw_args = type_spec.get("args") or []
            resolved_args = [
                self.resolve_type_spec(
                    a, aliases=aliases, cache=cache, stack=stack, module_id=module_id
                )
                for a in raw_args
            ] if raw_args else None
            return self.resolve_alias_spec(
                alias_name,
                aliases=aliases,
                cache=cache,
                stack=stack,
                module_id=module_id,
                type_args=resolved_args,
            )
        if t == "option" and "inner" in type_spec:
            resolved = dict(type_spec)
            resolved["inner"] = self.resolve_type_spec(
                type_spec["inner"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            return resolved
        if t == "list" and "inner" in type_spec:
            resolved = dict(type_spec)
            resolved["inner"] = self.resolve_type_spec(
                type_spec["inner"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            return resolved
        if t == "map" and "key" in type_spec and "value" in type_spec:
            resolved = dict(type_spec)
            resolved["key"] = self.resolve_type_spec(
                type_spec["key"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            resolved["value"] = self.resolve_type_spec(
                type_spec["value"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            return resolved
        if t == "result" and "ok" in type_spec and "err" in type_spec:
            resolved = dict(type_spec)
            resolved["ok"] = self.resolve_type_spec(
                type_spec["ok"], aliases=aliases, cache=cache, stack=stack, module_id=module_id
            )
            resolved["err"] = self.resolve_type_spec(
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
                            rf["type"] = self.resolve_type_spec(
                                field["type"],
                                aliases=aliases,
                                cache=cache,
                                stack=stack,
                                module_id=module_id,
                            )
                        resolved_fields.append(rf)
                    rv["fields"] = resolved_fields
                resolved_variants.append(rv)
            resolved["variants"] = resolved_variants
            return resolved
        return dict(type_spec)
