"""
NAIL Type System — v0.8
Represents and validates NAIL's type hierarchy.

v0.4 additions:
  - FnType: internal representation of function signatures used by higher-order
    collection operations (list_map / list_filter / list_fold).
    FnType is NOT a first-class NAIL value type; functions are referenced by
    string ID in NAIL JSON. FnType exists only so the checker can describe and
    report expected function signatures in error messages.
"""

from dataclasses import dataclass
from typing import Optional, Any


VALID_OVERFLOWS = {"panic"}  # Type-level default. Expression-level overrides (wrap/sat) are in checker/runtime.
VALID_EFFECTS = {"IO", "FS", "NET", "TIME", "RAND", "MUT", "REPO"}


class NailTypeError(Exception):
    """Type error with optional structured JSON representation."""
    def __init__(self, message: str, code: str = "TYPE_ERROR", location: dict = None, **extra):
        super().__init__(message)
        self.message = message
        self.code = code
        self.location: dict = location or {}
        self._extra = extra

    def to_json(self) -> dict:
        result = {
            "error": "NailTypeError",
            "code": self.code,
            "message": self.message,
            "location": self.location,
        }
        result.update(self._extra)
        return result


class NailEffectError(Exception):
    """Effect violation error with optional structured JSON representation."""
    def __init__(self, message: str, code: str = "EFFECT_ERROR", location: dict = None, **extra):
        super().__init__(message)
        self.message = message
        self.code = code
        self.location: dict = location or {}
        self._extra = extra

    def to_json(self) -> dict:
        result = {
            "error": "NailEffectError",
            "code": self.code,
            "message": self.message,
            "location": self.location,
        }
        result.update(self._extra)
        return result


class NailRuntimeError(Exception):
    """Runtime error with optional structured JSON representation."""
    def __init__(self, message: str, code: str = "RUNTIME_ERROR", location: dict = None, **extra):
        super().__init__(message)
        self.message = message
        self.code = code
        self.location: dict = location or {}
        self._extra = extra

    def to_json(self) -> dict:
        result = {
            "error": "NailRuntimeError",
            "code": self.code,
            "message": self.message,
            "location": self.location,
        }
        result.update(self._extra)
        return result


# ---------------------------------------------------------------------------
# Type representations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IntType:
    bits: int
    overflow: str  # panic | wrap | sat

    def __post_init__(self):
        if self.bits not in (8, 16, 32, 64):
            raise NailTypeError(f"Invalid int bits: {self.bits}")
        if self.overflow not in VALID_OVERFLOWS:
            raise NailTypeError(
                f"Invalid overflow mode: '{self.overflow}'. "
                f"Type-level overflow must be 'panic'. Use expression-level overflow (v0.3+) for 'wrap'/'sat'."
            )

    def __str__(self):
        return f"int{self.bits}({self.overflow})"


@dataclass(frozen=True)
class FloatType:
    bits: int

    def __post_init__(self):
        if self.bits not in (32, 64):
            raise NailTypeError(f"Invalid float bits: {self.bits}")

    def __str__(self):
        return f"float{self.bits}"


@dataclass(frozen=True)
class BoolType:
    def __str__(self): return "bool"


@dataclass(frozen=True)
class StringType:
    encoding: str = "utf8"
    def __str__(self): return "string"


@dataclass(frozen=True)
class BytesType:
    def __str__(self): return "bytes"


@dataclass(frozen=True)
class UnitType:
    def __str__(self): return "unit"


@dataclass(frozen=True)
class OptionType:
    inner: Any  # NailType

    def __str__(self): return f"option<{self.inner}>"


@dataclass(frozen=True)
class ListType:
    inner: Any  # NailType
    length: Any  # int or "dynamic"

    def __str__(self):
        l = "dynamic" if self.length == "dynamic" else str(self.length)
        return f"list<{self.inner}, len={l}>"


@dataclass(frozen=True)
class MapType:
    key: Any    # NailType
    value: Any  # NailType

    def __str__(self): return f"map<{self.key}, {self.value}>"


@dataclass(frozen=True)
class ResultType:
    """Result<Ok, Err> — explicit success/failure type. Added in v0.3."""
    ok: Any   # NailType for the success path
    err: Any  # NailType for the error path

    def __str__(self): return f"result<{self.ok}, {self.err}>"


@dataclass(frozen=True)
class EnumField:
    name: str
    type: Any  # NailType


@dataclass(frozen=True)
class EnumVariant:
    tag: str
    fields: tuple[EnumField, ...] = ()


@dataclass(frozen=True)
class EnumType:
    variants: tuple[EnumVariant, ...]

    def variant_for(self, tag: str) -> EnumVariant | None:
        for variant in self.variants:
            if variant.tag == tag:
                return variant
        return None

    def __str__(self):
        tags = ", ".join(v.tag for v in self.variants)
        return f"enum<{tags}>"


@dataclass(frozen=True)
class FnType:
    """Internal: represents the expected signature of a function reference used
    in higher-order collection operations (list_map, list_filter, list_fold).

    This is NOT a first-class NAIL value type — NAIL has no closures or
    function-value types.  FnType exists solely so the checker can produce
    readable error messages like:

        expected fn(int64(panic)) -> bool
        got     fn(int64(panic)) -> int64(panic)

    when a wrong function is passed to list_filter.
    """

    param_types: tuple  # tuple[NailType, ...]
    return_type: Any    # NailType

    def __str__(self) -> str:
        params = ", ".join(str(p) for p in self.param_types)
        return f"fn({params}) -> {self.return_type}"


@dataclass(frozen=True)
class TypeParam:
    """A type variable introduced by a generic function declaration.

    Example JSON: {"type": "param", "name": "T"}

    TypeParam is resolved at call sites via type inference (unify_types).
    It is a first-class NailType so that function signatures can be
    expressed generically before substitution is applied.
    """
    name: str

    def __str__(self) -> str:
        return self.name


NailType = IntType | FloatType | BoolType | StringType | BytesType | UnitType | OptionType | ListType | MapType | ResultType | EnumType | TypeParam
# NOTE: FnType is intentionally excluded from NailType — it is an internal
# checker representation only, not a first-class NAIL value type.


def parse_type(spec: dict, type_params: "frozenset[str] | None" = None) -> NailType:
    """Parse a JSON type spec into a NailType.

    Args:
        spec: The JSON type specification dict.
        type_params: Optional set of in-scope type parameter names (e.g. {"T", "U"}).
            When provided, {"type": "param", "name": "T"} resolves to TypeParam("T").
            When None (default), type params are not allowed (backward compatible).
    """
    t = spec.get("type")
    if t is None:
        raise NailTypeError(f"Missing 'type' field in: {spec}")

    if t == "param":
        name = spec.get("name")
        if not isinstance(name, str) or not name:
            raise NailTypeError("type param requires non-empty string 'name'")
        if type_params is None or name not in type_params:
            scope_hint = f" (in scope: {sorted(type_params)})" if type_params else " (no type params in scope)"
            raise NailTypeError(
                f"Unknown type parameter '{name}'{scope_hint}. "
                f"Declare it in the function's 'type_params' array."
            )
        return TypeParam(name=name)

    if t == "int":
        return IntType(
            bits=spec.get("bits", 64),
            overflow=spec.get("overflow", "panic"),
        )
    elif t == "float":
        return FloatType(bits=spec.get("bits", 64))
    elif t == "bool":
        return BoolType()
    elif t == "string":
        return StringType(encoding=spec.get("encoding", "utf8"))
    elif t == "bytes":
        return BytesType()
    elif t == "unit":
        return UnitType()
    elif t == "option":
        inner_spec = spec.get("inner")
        if inner_spec is None:
            raise NailTypeError("option type requires 'inner'")
        return OptionType(inner=parse_type(inner_spec, type_params))
    elif t == "list":
        inner_spec = spec.get("inner")
        if inner_spec is None:
            raise NailTypeError("list type requires 'inner'")
        length = spec.get("len", "dynamic")
        return ListType(inner=parse_type(inner_spec, type_params), length=length)
    elif t == "map":
        key_spec = spec.get("key")
        val_spec = spec.get("value")
        if key_spec is None or val_spec is None:
            raise NailTypeError("map type requires 'key' and 'value'")
        return MapType(key=parse_type(key_spec, type_params), value=parse_type(val_spec, type_params))
    elif t == "result":
        ok_spec = spec.get("ok")
        err_spec = spec.get("err")
        if ok_spec is None or err_spec is None:
            raise NailTypeError("result type requires both 'ok' and 'err' sub-types")
        return ResultType(ok=parse_type(ok_spec, type_params), err=parse_type(err_spec, type_params))
    elif t == "enum":
        variants_spec = spec.get("variants")
        if not isinstance(variants_spec, list) or not variants_spec:
            raise NailTypeError("enum type requires non-empty 'variants' list")
        variants: list[EnumVariant] = []
        seen_tags: set[str] = set()
        for i, variant_spec in enumerate(variants_spec):
            if not isinstance(variant_spec, dict):
                raise NailTypeError(f"enum variant at index {i} must be an object")
            tag = variant_spec.get("tag")
            if not isinstance(tag, str) or not tag:
                raise NailTypeError(f"enum variant at index {i} requires non-empty string 'tag'")
            if tag in seen_tags:
                raise NailTypeError(f"duplicate enum variant tag: {tag}")
            seen_tags.add(tag)

            fields_spec = variant_spec.get("fields", [])
            if fields_spec is None:
                fields_spec = []
            if not isinstance(fields_spec, list):
                raise NailTypeError(f"enum variant '{tag}' fields must be a list")
            fields: list[EnumField] = []
            seen_field_names: set[str] = set()
            for field_i, field_spec in enumerate(fields_spec):
                if not isinstance(field_spec, dict):
                    raise NailTypeError(f"enum variant '{tag}' field at index {field_i} must be an object")
                field_name = field_spec.get("name")
                field_type_spec = field_spec.get("type")
                if not isinstance(field_name, str) or not field_name:
                    raise NailTypeError(f"enum variant '{tag}' field at index {field_i} requires non-empty string 'name'")
                if field_name in seen_field_names:
                    raise NailTypeError(f"enum variant '{tag}' has duplicate field '{field_name}'")
                if not isinstance(field_type_spec, dict):
                    raise NailTypeError(f"enum variant '{tag}' field '{field_name}' requires object 'type'")
                seen_field_names.add(field_name)
                fields.append(EnumField(name=field_name, type=parse_type(field_type_spec, type_params)))
            variants.append(EnumVariant(tag=tag, fields=tuple(fields)))
        return EnumType(variants=tuple(variants))
    else:
        raise NailTypeError(f"Unknown type: {t}")


def types_equal(a: NailType, b: NailType) -> bool:
    return a == b


def substitute_type(t: "NailType", subst: "dict[str, NailType]") -> "NailType":
    """Apply a type substitution to a NailType, replacing TypeParams with concrete types.

    Args:
        t: The type to substitute into (may contain TypeParam nodes).
        subst: Mapping from type-param name to concrete NailType.

    Returns:
        A new NailType with all TypeParams in subst replaced.
    """
    if isinstance(t, TypeParam):
        return subst.get(t.name, t)
    elif isinstance(t, OptionType):
        return OptionType(inner=substitute_type(t.inner, subst))
    elif isinstance(t, ListType):
        return ListType(inner=substitute_type(t.inner, subst), length=t.length)
    elif isinstance(t, MapType):
        return MapType(
            key=substitute_type(t.key, subst),
            value=substitute_type(t.value, subst),
        )
    elif isinstance(t, ResultType):
        return ResultType(
            ok=substitute_type(t.ok, subst),
            err=substitute_type(t.err, subst),
        )
    elif isinstance(t, EnumType):
        # Enums with generic fields are unusual; substitute through them
        new_variants = []
        for variant in t.variants:
            new_fields = tuple(
                EnumField(name=f.name, type=substitute_type(f.type, subst))
                for f in variant.fields
            )
            new_variants.append(EnumVariant(tag=variant.tag, fields=new_fields))
        return EnumType(variants=tuple(new_variants))
    else:
        # Leaf types (int, float, bool, string, bytes, unit) — no type params
        return t


def unify_types(
    generic: "NailType",
    concrete: "NailType",
    subst: "dict[str, NailType]",
) -> "dict[str, NailType]":
    """Unify *generic* (possibly containing TypeParams) against *concrete*.

    Mutates and returns *subst* with new bindings.  Raises NailTypeError on
    conflicts (e.g. T already bound to int64 but encountering T ~ float64).

    Args:
        generic: The type from the callee signature (may have TypeParams).
        concrete: The type inferred from the call-site argument.
        subst: Current substitution (modified in-place).

    Returns:
        The (potentially extended) substitution.
    """
    if isinstance(generic, TypeParam):
        name = generic.name
        if name in subst:
            # Already bound — check consistency
            if not types_equal(subst[name], concrete):
                raise NailTypeError(
                    f"Type parameter '{name}' inferred as both {subst[name]} and {concrete}",
                    code="TYPE_PARAM_CONFLICT",
                )
        else:
            subst[name] = concrete
        return subst

    # Both sides must be structurally equal; recurse into containers
    if isinstance(generic, OptionType) and isinstance(concrete, OptionType):
        return unify_types(generic.inner, concrete.inner, subst)
    if isinstance(generic, ListType) and isinstance(concrete, ListType):
        return unify_types(generic.inner, concrete.inner, subst)
    if isinstance(generic, MapType) and isinstance(concrete, MapType):
        unify_types(generic.key, concrete.key, subst)
        return unify_types(generic.value, concrete.value, subst)
    if isinstance(generic, ResultType) and isinstance(concrete, ResultType):
        unify_types(generic.ok, concrete.ok, subst)
        return unify_types(generic.err, concrete.err, subst)

    # Leaf types (or structural mismatch) — just check equality
    if not types_equal(generic, concrete):
        raise NailTypeError(
            f"Type mismatch during generic instantiation: expected {generic}, got {concrete}",
            code="TYPE_MISMATCH",
        )
    return subst
