# Demo #104 — Multi-Provider API Routing

## Problem

When integrating LLM tool-calling across OpenAI, Anthropic, and Gemini, teams
typically maintain **three separate tool definitions** — one per provider. These
drift out of sync, causing subtle bugs and extra maintenance overhead.

## Solution

NAIL acts as a single source of truth. Define your tool once in
`tool_spec.nail` with effect annotations (`NET`, `FS`, etc.), then call
`nail.convert_tools()` to generate the correct format for every provider:

| Provider  | Format                                   |
|-----------|------------------------------------------|
| OpenAI    | `{"type": "function", "function": {...}}`|
| Anthropic | `{"name": ..., "input_schema": {...}}`   |
| Gemini    | `{"name": ..., "parameters": {...}}`     |

## Run

```bash
cd examples/demos/api_routing
python3 demo.py
```

## Files

- `tool_spec.nail` — NAIL tool spec (single source of truth)
- `demo.py` — Loads spec, validates effects, converts to all three provider formats
