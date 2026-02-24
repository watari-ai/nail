"""
NAIL Transpiler — Python (typed subset) → NAIL IR

Converts type-annotated Python functions to NAIL JSON for type/effect verification.
"""

from .python_to_nail import transpile_function, transpile_to_json, TranspilerError

__all__ = ["transpile_function", "transpile_to_json", "TranspilerError"]
