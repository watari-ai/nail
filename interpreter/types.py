"""
NAIL Type System — v0.1
Represents and validates NAIL's type hierarchy.
"""

from dataclasses import dataclass
from typing import Optional, Any


VALID_OVERFLOWS = {"panic"}  # v0.2: only "panic" supported; "wrap"/"sat" planned for v0.3
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
                f"v0.2 only supports 'panic'; 'wrap'/'sat' are planned for v0.3."
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


NailType = IntType | FloatType | BoolType | StringType | BytesType | UnitType | OptionType | ListType | MapType


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
    else:
        raise NailTypeError(f"Unknown type: {t}")


def types_equal(a: NailType, b: NailType) -> bool:
    return a == b
