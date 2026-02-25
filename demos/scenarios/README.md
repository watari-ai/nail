# NAIL Demo Scenarios

Standalone `.nail` files extracted from the demo scripts for direct verification with `nail check`.

Each file is in canonical JSON form (`sort_keys=True, separators=(',',':')`).

---

## Rogue-Agent Demo Scenarios

These files demonstrate NAIL's **effect system** catching malicious or
accidental permission violations at check time — before execution.

### `rogue-exfil-blocked.nail`
**Scenario:** Data exfiltration — agent declares `FS` only but tries to call `http_get` (NET).

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** Effect mismatch — `NET` not in declared effects `["FS"]`

```bash
nail check demos/scenarios/rogue-exfil-blocked.nail
# ✗ Effect error: ...
```

### `rogue-exfil-correct.nail`
**Scenario:** Legitimate file summariser — `FS` declared, no network access.

- **Expected:** PASS (`nail check` exits 0)

```bash
nail check demos/scenarios/rogue-exfil-correct.nail
# ✓ ...
```

### `rogue-traversal-blocked.nail`
**Scenario:** Path traversal — agent scoped to `/tmp/nail_data/` tries `../../etc/passwd`.

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** FS capability rejects path outside `allow` list

```bash
nail check demos/scenarios/rogue-traversal-blocked.nail
# ✗ Effect error: path traversal outside allowed directory
```

### `rogue-traversal-legit.nail`
**Scenario:** Legitimate read within the allowed directory `/tmp/nail_data/report.txt`.

- **Expected:** PASS (`nail check` exits 0)

```bash
nail check demos/scenarios/rogue-traversal-legit.nail
# ✓ ...
```

### `rogue-scheme-blocked.nail`
**Scenario:** Scheme smuggling — agent has NET access but uses `file://` URL via `http_get`.

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** Scheme validation rejects non-http/https in `http_get`

```bash
nail check demos/scenarios/rogue-scheme-blocked.nail
# ✗ Effect error: file:// scheme not allowed in http_get
```

### `rogue-scheme-legit.nail`
**Scenario:** Legitimate HTTPS fetch to an allowed domain.

- **Expected:** PASS (`nail check` exits 0)

```bash
nail check demos/scenarios/rogue-scheme-legit.nail
# ✓ ...
```

---

## Verifiability Demo Scenarios

These files demonstrate NAIL's **static checker (L0–L2)** catching bugs that
Python misses entirely or only catches at runtime.

### `verify-hidden-effect-fail.nail`
**Scenario:** Function declared pure (`effects: []`) but contains a `read_file` (FS) op.

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** Effect check — undeclared FS usage

```bash
nail check demos/scenarios/verify-hidden-effect-fail.nail
# ✗ Effect error: ...
```

### `verify-hidden-effect-pass.nail`
**Scenario:** Same function with `FS` correctly declared.

- **Expected:** PASS (`nail check` exits 0)

```bash
nail check demos/scenarios/verify-hidden-effect-pass.nail
# ✓ ...
```

### `verify-partial-return-fail.nail`
**Scenario:** `abs_val` — only the `then` branch returns; `else` is empty (implicit `None`).

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** Return exhaustiveness — not all branches return a value

```bash
nail check demos/scenarios/verify-partial-return-fail.nail
# ✗ Type error: not all branches return
```

### `verify-partial-return-pass.nail`
**Scenario:** `abs_val` — both `then` and `else` branches return.

- **Expected:** PASS (`nail check` exits 0)

```bash
nail check demos/scenarios/verify-partial-return-pass.nail
# ✓ ...
```

### `verify-type-mismatch-fail.nail`
**Scenario:** `is_positive` declares return type `int` but body returns a `bool` from `gt`.

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** Type check — `bool` ≠ `int`

```bash
nail check demos/scenarios/verify-type-mismatch-fail.nail
# ✗ Type error: return type mismatch
```

### `verify-type-mismatch-pass.nail`
**Scenario:** `is_positive` correctly declares return type `bool`.

- **Expected:** PASS (`nail check` exits 0)

```bash
nail check demos/scenarios/verify-type-mismatch-pass.nail
# ✓ ...
```

---

## Run All Checks at Once

```bash
# All PASS scenarios should exit 0
nail check demos/scenarios/rogue-exfil-correct.nail
nail check demos/scenarios/rogue-traversal-legit.nail
nail check demos/scenarios/rogue-scheme-legit.nail
nail check demos/scenarios/verify-hidden-effect-pass.nail
nail check demos/scenarios/verify-partial-return-pass.nail
nail check demos/scenarios/verify-type-mismatch-pass.nail

# All FAIL scenarios should exit 1
nail check demos/scenarios/rogue-exfil-blocked.nail     # expected: error
nail check demos/scenarios/rogue-traversal-blocked.nail  # expected: error
nail check demos/scenarios/rogue-scheme-blocked.nail     # expected: error
nail check demos/scenarios/verify-hidden-effect-fail.nail  # expected: error
nail check demos/scenarios/verify-partial-return-fail.nail # expected: error
nail check demos/scenarios/verify-type-mismatch-fail.nail  # expected: error
```

Or run the interactive demos:

```bash
nail demo rogue-agent
nail demo verifiability
nail demo --list
```
