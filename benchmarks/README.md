# NAIL Token Efficiency Benchmarks

> Quantitative comparison of NAIL vs Python, TypeScript, and OpenAI Function Calling JSON.
> Validates the "AI-native" claim with real tokenizer data.

**Tokenizer:** `tiktoken:cl100k_base` (GPT-4 / GPT-3.5-turbo compatible, OpenAI standard)

---

## Summary

| Scenario | NAIL | Python | TypeScript | OpenAI FC |
|----------|-----:|-------:|-----------:|----------:|
| S1: Simple typed function (`add`) | 98 | 18 | 19 | 70 |
| S2: Effect-annotated function (`read_file [FS]`) | **72** | 96 | 90 | 73 |
| S3: Result type (`safe_div → Result<int,str>`) | 170 | 89 | 119 | 83 |
| S4: FC Standard module (3 tools with effects) | **248** | 196 | 194 | 208 |

### Key Findings

| Comparison | NAIL advantage |
|-----------|---------------|
| **Effect-declared functions (S2)** | NAIL saves **25% vs Python**, **20% vs TypeScript** |
| **FC Standard module (S4)** | NAIL within **19% of OpenAI FC** while adding verifiable effect annotations |
| Simple pure functions (S1) | NAIL is more verbose (+444% vs Python) — expected; NAIL is not designed for simple arithmetic |
| Result type functions (S3) | NAIL is more verbose (+91% vs Python) due to JSON structure encoding the full type info |

---

## Detailed Results

### S1: Simple typed function — `add(a: int64, b: int64) → int64`

The simplest case. NAIL encodes full type information (int64 overflow semantics) in JSON, which is verbose for a trivial function. Python and TypeScript win on raw token count here.

**NAIL (canonical JSON, 98 tokens):**
```json
{"body":[{"op":"return","val":{"l":{"ref":"a"},"op":"+","r":{"ref":"b"}}}],"effects":[],"id":"add","kind":"fn","nail":"0.9","params":[{"id":"a","type":{"bits":64,"overflow":"panic","type":"int"}},{"id":"b","type":{"bits":64,"overflow":"panic","type":"int"}}],"returns":{"bits":64,"overflow":"panic","type":"int"}}
```

**Python (18 tokens):**
```python
def add(a: int, b: int) -> int:
    return a + b
```

**TypeScript (19 tokens):**
```typescript
function add(a: number, b: number): number {
    return a + b;
}
```

**OpenAI FC JSON (70 tokens):**
```json
{"type":"function","function":{"name":"add","description":"Add two 64-bit integers and return the result.","parameters":{"type":"object","properties":{"a":{"type":"integer","description":"First operand (int64)"},"b":{"type":"integer","description":"Second operand (int64)"}},"required":["a","b"]}}}
```

> **Note:** Simple pure functions are not NAIL's primary use case. NAIL is designed for effect-annotated AI tool definitions, not human-readable arithmetic.

---

### S2: Effect-annotated function — `read_file(path, encoding) → str [FS]` ⭐ NAIL wins

This is NAIL's home domain: functions with declared side effects. To express the same information in Python or TypeScript, you need docstrings/JSDoc that mention the effect — and those are wordier than NAIL's compact JSON.

**NAIL (72 tokens) — effects encoded in structure:**
```json
{"effects":["FS"],"id":"read_file","kind":"fn","nail":"0.9","params":[{"id":"path","type":{"encoding":"utf8","type":"string"}},{"id":"encoding","default":"utf-8","type":{"encoding":"utf8","type":"string"}}],"returns":{"encoding":"utf8","type":"string"}}
```

**Python (96 tokens) — requires docstring to declare effects:**
```python
def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read file contents from the local filesystem.

    Effects:
        FS: reads from the local filesystem
    ...
    """
```

**TypeScript (90 tokens) — requires JSDoc @effects annotation:**
```typescript
/**
 * @effects FS - reads from the local filesystem
 * @param path - Absolute or relative path to the file
 */
function readFile(path: string, encoding: string = "utf-8"): string { ... }
```

**Result: NAIL saves 25% vs Python, 20% vs TypeScript for effect-annotated functions.**

---

### S3: Result type — `safe_div(a, b) → Result<int64, str>`

NAIL encodes the Result type directly in the JSON schema (with `"type":"result"` field). Python needs `Union[int, str]` and TypeScript needs a full `type Result<T, E>` definition. NAIL is more verbose overall but encodes more structural information.

---

### S4: FC Standard multi-tool module (3 tools) ⭐ Most relevant for AI agents

The primary production use case: defining tool modules for AI function calling. NAIL FC Standard adds effect annotations (`"effects":["FS"]`, `"effects":["NET"]`) and a module wrapper on top of OpenAI FC format.

**Token counts:** NAIL 248 | Python 196 | TypeScript 194 | OpenAI FC 208

**Key insight:** NAIL FC is only **19% more than OpenAI FC** while adding:
- Verifiable effect declarations (`FS`, `NET`, `TIME`, `RAND`) per tool
- Module-level metadata (`doc`, `id`)
- Cross-provider compatibility (same format works for OpenAI, Anthropic, Gemini via `convert_tools()`)

Python and TypeScript are shorter here because they use `...` (stub bodies), but they cannot formally declare effects — the AI or runtime has no way to verify that `read_file` actually only does FS and not NET.

---

## Interpretation

NAIL is not designed to replace Python for writing `add(a, b)`. It is designed for AI agents that need to:

1. **Declare function contracts** with verifiable effects (`[FS]`, `[NET]`) — NAIL saves 25% vs Python
2. **Define tool modules** for multi-provider function calling — NAIL within 19% of OpenAI FC while adding effect verifiability
3. **Generate provably correct code** — zero-ambiguity canonical JSON that an AI writes and a checker validates

The token efficiency argument is strongest for effect-annotated function declarations (S2) — exactly the scenario where NAIL's type system adds the most value.

---

## Reproducing Results

```bash
# From the nail/ repo root:
python benchmarks/token_efficiency.py

# Save to benchmarks/results/:
python benchmarks/token_efficiency.py --save

# JSON output only:
python benchmarks/token_efficiency.py --output json
```

Results are saved to:
- `benchmarks/results/token_efficiency.json`
- `benchmarks/results/token_efficiency.csv`

---

*Generated with `tiktoken:cl100k_base` (GPT-4 compatible tokenizer). Run `python benchmarks/token_efficiency.py` to reproduce.*
