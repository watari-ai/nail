"""NAIL Interpreter"""
from .types import parse_type, NailTypeError, NailEffectError, NailRuntimeError, ResultType, EnumType
from .checker import Checker, CheckError
from .runtime import Runtime, NailResult

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("nail-lang")
except Exception:
    __version__ = "0.9.1"  # fallback
__all__ = [
    "Checker", "Runtime", "CheckError",
    "NailTypeError", "NailEffectError", "NailRuntimeError",
    "ResultType", "EnumType", "NailResult",
]
