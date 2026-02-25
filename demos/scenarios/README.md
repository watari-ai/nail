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

## Termination Demo Scenarios

These files demonstrate NAIL's **L3 termination prover** — proving that loops
and recursive functions terminate before allowing execution.

### `term-bounded-pass.nail`
**Scenario:** Bounded loop from 0 to 10 with `step=1`.

- **Expected:** PASS (`nail check --level 3` exits 0)
- **Proof:** Loop step is a non-zero literal — terminates in finite iterations.

```bash
nail check demos/scenarios/term-bounded-pass.nail --level 3
# ✓ ...
```

### `term-zero-step-fail.nail`
**Scenario:** Loop from 0 to 10 with `step=0` — infinite loop.

- **Expected:** FAIL (`nail check --level 3` exits 1)
- **Catch:** Zero step detected — loop never progresses.

```bash
nail check demos/scenarios/term-zero-step-fail.nail --level 3
# ✗ Termination error: zero step
```

### `term-recursive-pass.nail`
**Scenario:** Recursive factorial with `termination: {measure: "n"}` annotation.

- **Expected:** PASS (`nail check --level 3` exits 0)
- **Proof:** Measure annotation declares `n` decreases on each recursive call.

```bash
nail check demos/scenarios/term-recursive-pass.nail --level 3
# ✓ ...
```

### `term-recursive-fail.nail`
**Scenario:** Recursive factorial **without** termination annotation.

- **Expected:** FAIL (`nail check --level 3` exits 1)
- **Catch:** Recursion cycle detected but no measure annotation — cannot prove termination.

```bash
nail check demos/scenarios/term-recursive-fail.nail --level 3
# ✗ Termination error: recursive cycle without measure
```

---

## AI Review Demo Scenarios

These files demonstrate NAIL catching **common AI code-generation mistakes**
at check time — bugs that Python misses or only catches at runtime.

### `ai-review-effect-leak-fail.nail`
**Scenario:** Pure function (`effects: []`) contains a `print` (IO effect).

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** Effect check — undeclared IO usage in a pure function.

```bash
nail check demos/scenarios/ai-review-effect-leak-fail.nail
# ✗ Effect error: ...
```

### `ai-review-type-mixup-fail.nail`
**Scenario:** Function declares return type `int` but returns a `bool` (from `gte`).

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** Type check — `bool` ≠ `int`.

```bash
nail check demos/scenarios/ai-review-type-mixup-fail.nail
# ✗ Type error: return type mismatch
```

### `ai-review-missing-branch-fail.nail`
**Scenario:** `clamp_positive` — `then` returns, `else` is empty (no return).

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** Return exhaustiveness — not all branches return a value.

```bash
nail check demos/scenarios/ai-review-missing-branch-fail.nail
# ✗ Type error: not all branches return
```

### `ai-review-fixed-pass.nail`
**Scenario:** All four AI mistakes corrected — module with `double`, `is_adult`, `clamp_positive`, `main`.

- **Expected:** PASS (`nail check` exits 0)

```bash
nail check demos/scenarios/ai-review-fixed-pass.nail
# ✓ ...
```

---

## Trust Boundary Demo Scenarios

These files demonstrate NAIL's **cross-module trust boundary** enforcement —
a dependency cannot escalate beyond the caller's declared effects.

Trust boundary scenarios require `--modules` to provide the dependency file.

### `trust-pure-caller-pass.nail` + `trust-pure-math.nail`
**Scenario:** Pure caller imports a pure math module (`add`).

- **Expected:** PASS (`nail check` exits 0)
- **Reason:** Both sides are pure — no effect escalation.

```bash
nail check demos/scenarios/trust-pure-caller-pass.nail --modules demos/scenarios/trust-pure-math.nail
# ✓ ...
```

### `trust-escalation-fail.nail` + `trust-net-smuggler.nail`
**Scenario:** FS-only caller imports a dependency that secretly uses NET.

- **Expected:** FAIL (`nail check` exits 1)
- **Catch:** Effect escalation — NET is not a subset of FS.

```bash
nail check demos/scenarios/trust-escalation-fail.nail --modules demos/scenarios/trust-net-smuggler.nail
# ✗ Effect error: ...
```

### `trust-io-caller-pass.nail` + `trust-logger.nail`
**Scenario:** IO caller imports an IO logger module.

- **Expected:** PASS (`nail check` exits 0)
- **Reason:** Both sides declare IO — the effect boundary is respected.

```bash
nail check demos/scenarios/trust-io-caller-pass.nail --modules demos/scenarios/trust-logger.nail
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
nail check demos/scenarios/term-bounded-pass.nail --level 3
nail check demos/scenarios/term-recursive-pass.nail --level 3
nail check demos/scenarios/ai-review-fixed-pass.nail
nail check demos/scenarios/trust-pure-caller-pass.nail --modules demos/scenarios/trust-pure-math.nail
nail check demos/scenarios/trust-io-caller-pass.nail --modules demos/scenarios/trust-logger.nail

# All FAIL scenarios should exit 1
nail check demos/scenarios/rogue-exfil-blocked.nail     # expected: error
nail check demos/scenarios/rogue-traversal-blocked.nail  # expected: error
nail check demos/scenarios/rogue-scheme-blocked.nail     # expected: error
nail check demos/scenarios/verify-hidden-effect-fail.nail  # expected: error
nail check demos/scenarios/verify-partial-return-fail.nail # expected: error
nail check demos/scenarios/verify-type-mismatch-fail.nail  # expected: error
nail check demos/scenarios/term-zero-step-fail.nail --level 3          # expected: error
nail check demos/scenarios/term-recursive-fail.nail --level 3          # expected: error
nail check demos/scenarios/ai-review-effect-leak-fail.nail             # expected: error
nail check demos/scenarios/ai-review-type-mixup-fail.nail              # expected: error
nail check demos/scenarios/ai-review-missing-branch-fail.nail          # expected: error
nail check demos/scenarios/trust-escalation-fail.nail --modules demos/scenarios/trust-net-smuggler.nail  # expected: error
```

Or run the interactive demos:

```bash
nail demo rogue-agent
nail demo verifiability
nail demo termination
nail demo ai-review
nail demo mcp-firewall
nail demo trust-boundary
nail demo --list
```
