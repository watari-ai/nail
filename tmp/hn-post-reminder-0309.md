# 📌 HN投稿リマインダー — 2026-03-09（月）

## 投稿タイミング

| 項目 | 内容 |
|------|------|
| 投稿日時 | **2026-03-09（月）21:00〜23:00 JST** |
| 投稿URL | https://news.ycombinator.com/submit |

---

## Step 1: ログイン確認

アカウント: `naillang`

---

## Step 2: タイトル（コピー用）

```
Show HN: NAIL – JSON-native language for AI agents (v0.9.2, 954 tests)
```

---

## Step 3: URL（コピー用）

```
https://github.com/watari-ai/nail
```

---

## Step 4: 本文（コピー用）

> 📄 本文は `nail/tmp/hn-post-v14.md` を使用（以下に全文）

---

NAIL is a programming language designed to be written by AI agents. Every program is pure JSON — no text syntax, no parser. The key bet: if an LLM generates code you can't review line-by-line, the language itself must enforce your constraints.

The effect system is the core. Every function and agent declares what it touches — filesystem, network, time, randomness — and the checker rejects violations before execution. An agent that secretly calls `http_get` when only `FS` is declared fails at check time, not at runtime after the data leaves.

---

## New in v0.9.2: Delegation Qualifiers (FC-E010)

Multi-agent pipelines have a delegation problem: Agent A tells Agent B to write a file. But did A actually have permission to delegate that? In most frameworks, this check doesn't exist.

NAIL v0.9.2 adds `grants` to the delegation chain:

```json
{
  "kind": "fc",
  "id": "supervisor",
  "effects": ["FS.write"],
  "grants": ["FS.read"],
  "body": [...]
}
```

```json
{
  "kind": "fc",
  "id": "worker",
  "required_grants": ["FS.read"],
  "body": [...]
}
```

```
$ nail check pipeline.nail
FC-E010 ExplicitDelegationViolation: worker requires FS.read in caller grants,
  but supervisor.grants does not include it
```

An agent cannot grant permissions it doesn't hold. The entire authorization chain — across five or fifty agents — is verified at type-check time, before any agent runs. This is the thing most agentic frameworks skip.

---

## Why JSON?

NAIL outputs JSON Canonical Form (JCS): sorted keys, compact separators, deterministic encoding. Two LLM runs generating identical logic produce token-for-token identical output. There is no grammar to parse, no ambiguous whitespace, no string-matching error messages — just schema validation. `nail check --format json` returns machine-parseable failures that agents can act on directly.

`spec_version: "1.0"` pins the schema against breaking changes. Programs that check against NAIL-1.0 will keep checking against it.

---

## What's there (v0.9.2, 954 tests)

- Effect system: `IO / FS / NET / TIME / RAND` with fine-grained capability declarations
- L0 (schema) → L1 (types) → L2 (effects) → L3 (termination proof)
- Delegation qualifiers: `allow`, `grants`, `reversible` — FC-E010 enforced at type-check
- `filter_by_effects()` — restrict agent tools by effect at runtime
- FC Standard — converts NAIL definitions to OpenAI / Anthropic / Gemini tool schemas
- Nail-Lens CLI: `nail inspect / diff / validate / effects`
- Playground at naillang.com

```python
from nail_lang import filter_by_effects

# Restrict agent to read-only — no network, no process spawning
safe_tools = filter_by_effects(tools, allowed=["FS.read"])
```

---

The core claim: every AI agent framework today trusts the agent to stay in bounds. NAIL doesn't. The effect system and delegation chain are enforced at the language level — not by a wrapper, not by a policy, not by a prompt.

**Links:**
- Repo: https://github.com/watari-ai/nail
- PyPI: `pip install nail-lang` (v0.9.2)
- Playground / docs: https://naillang.com

---

## Step 5: 投稿直後のコメント

投稿直後、自分の投稿を開いて「reply」→ 本文コメントを投稿（上記本文全文をコメントとして貼る）

---

## Step 6: 完了連絡

投稿後、Slack DM（ワタリ宛）に一言：

> 「HN投稿した」

---

*作成: 2026-03-08 04:30 JST by ワタリ*
