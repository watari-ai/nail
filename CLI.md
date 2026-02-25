# NAIL CLI Reference

Install: `pip install nail-lang`
Run from source: `./nail <command>` (requires Python 3.10+)

---

## Commands

### `nail run`

Execute a NAIL program.

```
nail run <file.nail> [options]
```

| Option | Description |
|--------|-------------|
| `--call <fn>` | Call a specific function by name |
| `--arg <name=value>` | Pass a named argument to the called function (repeatable) |
| `--modules <path>` | Add a module file to the import search path (repeatable) |
| `--level <1\|2\|3>` | Verification level before execution (default: 2) |

**Examples:**

```bash
# Run the module entry point
nail run examples/hello.nail

# Call a specific function with arguments
nail run examples/add.nail --call add --arg a=10 --arg b=20

# Run with L3 termination proof
nail run examples/factorial.nail --level 3

# Run with an imported module
nail run examples/main.nail --modules examples/math_module.nail
```

---

### `nail check`

Verify a NAIL program without executing it.

```
nail check <file.nail> [options]
```

| Option | Description |
|--------|-------------|
| `--level <1\|2\|3>` | Verification level: 1=types, 2=effects (default), 3=termination |
| `--strict` | Reject non-canonical JSON (enforces JCS canonical form) |
| `--format <human\|json>` | Output format: `human` (default) or `json` (machine-parseable) |
| `--modules <path>` | Add a module file to the import search path (repeatable) |

**Verification levels:**

| Level | Checks |
|-------|--------|
| L1 | Type correctness |
| L2 | Type + effect consistency (default) |
| L3 | Type + effect + termination proof |

**Examples:**

```bash
# Default check (L2)
nail check examples/hello.nail

# Strict canonical form enforcement
nail check examples/hello.nail --strict

# L3 termination proof
nail check examples/factorial.nail --level 3

# Machine-parseable JSON output (for AI agents)
nail check examples/hello.nail --format json

# Check with imported module
nail check examples/main.nail --modules examples/math_module.nail
```

**JSON output format:**

```json
{ "ok": true }
{ "ok": false, "error": "CheckError: ...", "code": "EFFECT_UNDECLARED" }
```

---

### `nail canonicalize`

Normalize a NAIL program to JCS canonical form (RFC 8785).

```
nail canonicalize [file.nail]
```

If no file is given, reads from stdin. Outputs canonical JSON to stdout.

**Examples:**

```bash
# Canonicalize a file
nail canonicalize examples/hello.nail

# Pipe input
cat examples/hello.nail | nail canonicalize

# In-place update (overwrite)
nail canonicalize examples/hello.nail > /tmp/out.nail && mv /tmp/out.nail examples/hello.nail
```

---

### `nail version`

Print the interpreter version.

```
nail version
nail --version
```

---

### `nail demo`

Run interactive demonstrations of NAIL's effect system and verification.

```
nail demo [--list]
nail demo <name>
```

**Available demos:**

| Name | Description |
|------|-------------|
| `rogue-agent` | Effect system: 3 escalating scenarios where an AI agent attempts to exceed its declared permissions. NAIL catches each attempt at check time before execution. |
| `verifiability` | Verification: 3 bug classes that Python misses (hidden side effects, missing return paths, type mismatches) caught statically by NAIL's L1/L2 checker. |

**Examples:**

```bash
# List available demos
nail demo --list

# Run the rogue agent demo
nail demo rogue-agent

# Run the verifiability demo
nail demo verifiability
```

Individual scenario `.nail` files are in `demos/scenarios/` for direct `nail check` use:

```bash
nail check demos/scenarios/rogue-exfil-blocked.nail     # expected: FAIL
nail check demos/scenarios/rogue-exfil-correct.nail     # expected: PASS
nail check demos/scenarios/verify-type-mismatch-fail.nail  # expected: FAIL
```

See [`demos/scenarios/README.md`](demos/scenarios/README.md) for the full list with expected outcomes.

---

## Python API

The NAIL interpreter is also available as a Python library:

```python
from nail_lang import Checker, Runtime, filter_by_effects
from nail_lang.fc_standard import to_openai_tool, to_anthropic_tool, to_gemini_tool, convert_tools

# Check a program
checker = Checker(program)
result = checker.check()         # L2 (default)
result = checker.check(level=3)  # L3 termination proof

# Run a program
runtime = Runtime(program)
runtime.run()

# Effect-safe tool filtering
safe_tools = filter_by_effects(tools, allowed=["FS", "IO"])

# FC Standard — cross-provider conversion
openai_tool    = to_openai_tool(nail_fn)
anthropic_tool = to_anthropic_tool(nail_fn)
gemini_tool    = to_gemini_tool(nail_fn)

# Batch conversion
openai_tools = convert_tools(nail_fns, target="openai")
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Check/run error (type error, effect violation, etc.) |
| 1 | Invalid CLI usage |

---

*See [README.md](README.md) for full feature documentation and examples.*
*See [SPEC.md](SPEC.md) for the language specification.*
