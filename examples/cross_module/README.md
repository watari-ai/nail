# Cross-Module Import Example (NAIL v0.3)

This example demonstrates **cross-module imports** — calling functions defined in a separate NAIL module.

## Files

| File | Role |
|------|------|
| `math_utils.nail` | Library module: `add(a, b)` and `square(x)` |
| `sum_of_squares.nail` | Main module: imports and uses both functions |

## Usage

```bash
# Type-check (all 3 levels: schema / types / effects)
nail check sum_of_squares.nail --modules math_utils.nail

# Run: 3² + 4² = 25
nail run sum_of_squares.nail --modules math_utils.nail --arg a=3 --arg b=4
```

## Key Concepts

### 1. Import Declaration
The consumer module declares what it imports at the top level:
```json
"imports": [{"module": "math_utils", "fns": ["add", "square"]}]
```

### 2. Cross-Module Call Op
Instead of a local `call`, specify the source module:
```json
{"op": "call", "module": "math_utils", "fn": "square", "args": [{"ref": "a"}]}
```

### 3. Effect Propagation
If a library function declares `"effects": ["IO"]`, any caller must also declare `IO`.
NAIL's checker enforces this across module boundaries.

### 4. Zero Ambiguity
- Import lists are explicit — no wildcard imports
- Module `"id"` must match filename stem (`math_utils.nail` → `"id": "math_utils"`)
- Circular imports raise `CheckError`
