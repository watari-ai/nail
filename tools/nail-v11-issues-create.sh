#!/bin/bash
set -e

EXECUTE=false
for arg in "$@"; do
  if [ "$arg" = "--execute" ]; then
    EXECUTE=true
  fi
done

if [ "$EXECUTE" = false ]; then
  echo "⚠️ Dry-run mode. Pass --execute to actually create issues."
  echo ""
  echo "Would create the following issues in order: #111 → #108 → #110 → #112"
  echo ""
  echo "--- Issue 1: #111 ---"
  echo "Title: feat: RAG Context Kind — NAIL as intermediate format for RAG"
  echo "Labels: language-design, v1.1"
  echo ""
  echo "--- Issue 2: #108 ---"
  echo "Title: feat: Delegation depth tracking — max_delegation_depth (Phase 2)"
  echo "Labels: enhancement, v1.1, delegation"
  echo ""
  echo "--- Issue 3: #110 ---"
  echo "Title: feat: Multi-layer LLM interface contracts"
  echo "Labels: language-design, v1.1"
  echo ""
  echo "--- Issue 4: #112 ---"
  echo "Title: feat: Routing hints as declarative qualifiers"
  echo "Labels: enhancement, v1.1"
  echo ""
  echo "Done. Created 4 issues."
  exit 0
fi

# === #111: RAG Context Kind ===
gh issue create \
  --repo watari-ai/nail \
  --title "feat: RAG Context Kind — NAIL as intermediate format for RAG" \
  --label "language-design,v1.1" \
  --body "Following up on the RAG integration discussion, I've drafted a design spec for a new \`kind: context\` — RAG-retrieved knowledge as a first-class NAIL construct.

### Summary

Current NAIL kinds (\`skill\`, \`persona\`, \`effect\`) describe agent capability and behavior. There is no native way to represent *retrieved world knowledge*. \`kind: context\` gives RAG-produced facts a proper home in the NAIL ecosystem: typed, provenance-annotated, confidence-scored, and expiry-aware chunks that AI agents can consume with full structural awareness.

### Motivation

Without this, developers inject raw text into system prompts (no structure, no confidence, no expiry), pass JSON blobs outside the NAIL contract, or embed knowledge into \`persona\`/\`skill\` at the wrong abstraction layer. A dedicated \`context\` kind enables native integration with LlamaIndex, LangChain, and custom retrieval stacks.

### Minimal Spec

\`\`\`nail
kind: context
id: auth_flow_ctx_001
source:
  document_id: \"docs/auth/oauth2-flow.md\"
  retrieval_score: 0.91
valid_until: \"2026-12-31\"
facts:
  - key: \"oauth2.pkce_required\"
    value: true
    type: bool
    fact_confidence: 0.95
\`\`\`

The pipeline becomes: RAG database → NAIL context chunks → AI agent runtime.

### Design Doc

See [\`designs/v1.1/rag-context-kind.md\`](designs/v1.1/rag-context-kind.md) for the full specification including JSON Schema, fact typing, provenance fields, cross-chunk relations, and runtime consumption semantics."

echo "✅ Created #111"

# === #108: Delegation depth tracking ===
gh issue create \
  --repo watari-ai/nail \
  --title "feat: Delegation depth tracking — max_delegation_depth (Phase 2)" \
  --label "enhancement,v1.1,delegation" \
  --body "Following up on the delegation feature discussion, I've drafted a full design spec for runtime-enforced delegation depth tracking.

### Summary

NAIL v1.0 introduced \`can_delegate\` as a binary qualifier. This is insufficient for real-world agent hierarchies where the concern is not delegation itself but **unbounded** delegation. \`max_delegation_depth\` allows authors to declare, in the spec language itself, the maximum number of additional hops a task may undergo after first invocation.

### Motivation

Without depth bounds:
- Sensitive effects (\`FS_WRITE\`, \`STATE\`) can propagate arbitrarily deep.
- Irreversible actions (file deletion, data mutation) can reach agents never audited for those responsibilities.
- Authority provenance becomes opaque.

### Minimal Spec

\`\`\`nail
can_delegate:
  allowed: true
  max_delegation_depth: 2
\`\`\`

The runtime maintains a \`delegation_depth\` counter per invocation. When a delegated call would exceed the declared maximum, the runtime raises \`DelegationDepthExceeded\` before the call is dispatched. Dynamic enforcement was chosen over static analysis due to NAIL's open-world assumption (remote registries, dynamic dispatch).

### Design Doc

See [\`designs/v1.1/delegation-depth.md\`](designs/v1.1/delegation-depth.md) for the full specification including runtime semantics, inheritance rules, and the Phase B static analysis plan."

echo "✅ Created #108"

# === #110: Multi-layer LLM interface contracts ===
gh issue create \
  --repo watari-ai/nail \
  --title "feat: Multi-layer LLM interface contracts" \
  --label "language-design,v1.1" \
  --body "Following up on the architectural layering discussion, I've drafted a design spec for multi-layer LLM interface contracts.

### Summary

Modern AI systems chain multiple LLM backends hierarchically (L1: frontier orchestrator → L2: mid-tier specialist → L3: local model). Today, boundaries between layers are enforced only by convention. This spec adds a \`layer\` qualifier block that allows developers to declare each layer's identity, locality, allowed inputs/outputs, and permitted effects — all in the NAIL file itself.

### Motivation

NAIL v1.0 effect qualifiers and delegation depth operate at the function level. There is no native way to describe **architectural-layer contracts** that every agent at a given layer must honour. Without this, an L1 can inadvertently delegate a privileged action to an L3 never designed to handle it.

### Minimal Spec

\`\`\`nail
layer:
  id: \"l1_orchestrator\"
  level: 1
  locality: \"cloud\"
  model_hint: \"claude-3-5\"
  delegates_to:
    - \"l2_specialist\"
\`\`\`

\`nail fc check\` enforces that delegation chains never escalate privileges from lower to higher layers, and never leak retained fields across layer boundaries. Combined with routing hints (#112), the runtime can verify not just *what* is delegated but *where* it executes.

### Design Doc

See [\`designs/v1.1/multi-layer-contracts.md\`](designs/v1.1/multi-layer-contracts.md) for the full specification including layer declaration schema, input/output contracts, linting rules, and interaction with effect qualifiers."

echo "✅ Created #110"

# === #112: Routing hints as declarative qualifiers ===
gh issue create \
  --repo watari-ai/nail \
  --title "feat: Routing hints as declarative qualifiers" \
  --label "enhancement,v1.1" \
  --body "Following up on the multi-backend routing discussion, I've drafted a design spec for routing hint qualifiers.

### Summary

As NAIL-powered systems coordinate multiple LLM backends (local Ollama/mlx-lm alongside cloud APIs), the decision of *where* to route an inference call is currently made entirely outside the NAIL contract in ad-hoc application code. Routing hint qualifiers make this intent a first-class NAIL declaration, auditable by \`nail fc check\`.

### Motivation

Without routing hints, developers cannot express routing intent in the skill/effect definition, the checker has no surface to validate routing mismatches, and privacy constraints (data residency, PII) are enforced only by convention.

### New Qualifiers (on \`kind: effect\`)

\`\`\`nail
complexity_tier: \"light\" | \"heavy\"    # local vs cloud preference
persona_required: true | false         # requires user-specific context
privacy_tier: \"public\" | \"internal\" | \"restricted\"  # data sensitivity
token_budget: 500                      # expected max tokens (load planning)
routing: \"soft\" | \"strict\"            # hint vs hard constraint
\`\`\`

\`complexity_tier: \"light\"\` routes to local LLMs by preference; \`\"heavy\"\` routes to cloud. \`privacy_tier: \"restricted\"\` prohibits cloud routing. These qualifiers interact with #110 (multi-layer contracts): the runtime can verify not just what is delegated but where it will execute.

### Design Doc

See [\`designs/v1.1/routing-hints.md\`](designs/v1.1/routing-hints.md) for the full specification including all qualifier definitions, soft vs hard constraint semantics, linting rules, and interaction with multi-layer contracts."

echo "✅ Created #112"

echo ""
echo "Done. Created 4 issues."
