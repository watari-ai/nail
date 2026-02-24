"""
NAIL Type System — v0.4
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
VALID_EFFECTS = {"IO", "FS", "NET", "TIME", "RAND", "MUT"}


class NailTypeError(Exception):
    pass


class NailEffectError(Exception):
    pass


class NailRuntimeError(Exception):
    pass


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
        assert self.bits in (32, 64), f"Invalid float bits: {self.bits}"

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


NailType = IntType | FloatType | BoolType | StringType | BytesType | UnitType | OptionType | ListType | MapType | ResultType | EnumType | FnType


def parse_type(spec: dict) -> NailType:
    """Parse a JSON type spec into a NailType."""
    t = spec.get("type")
    if t is None:
        raise NailTypeError(f"Missing 'type' field in: {spec}")

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
        return OptionType(inner=parse_type(inner_spec))
    elif t == "list":
        inner_spec = spec.get("inner")
        if inner_spec is None:
            raise NailTypeError("list type requires 'inner'")
        length = spec.get("len", "dynamic")
        return ListType(inner=parse_type(inner_spec), length=length)
    elif t == "map":
        key_spec = spec.get("key")
        val_spec = spec.get("value")
        if key_spec is None or val_spec is None:
            raise NailTypeError("map type requires 'key' and 'value'")
        return MapType(key=parse_type(key_spec), value=parse_type(val_spec))
    elif t == "result":
        ok_spec = spec.get("ok")
        err_spec = spec.get("err")
        if ok_spec is None or err_spec is None:
            raise NailTypeError("result type requires both 'ok' and 'err' sub-types")
        return ResultType(ok=parse_type(ok_spec), err=parse_type(err_spec))
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
                fields.append(EnumField(name=field_name, type=parse_type(field_type_spec)))
            variants.append(EnumVariant(tag=tag, fields=tuple(fields)))
        return EnumType(variants=tuple(variants))
    else:
        raise NailTypeError(f"Unknown type: {t}")


def types_equal(a: NailType, b: NailType) -> bool:
    return a == b
