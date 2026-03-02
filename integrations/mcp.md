# NAIL × MCP Integration Guide

## Overview

MCP (Model Context Protocol) is an open standard for connecting AI agents to tools, data sources, and services. NAIL provides a formal effect system that can sandbox which MCP tools an agent is permitted to use.

This guide shows how to:
1. Convert MCP tools to OpenAI FC format with automatic NAIL effect annotations
2. Filter the annotated tools by effect scope (sandboxing)
3. Convert filtered tools back to MCP format for downstream consumers

## Installation

```bash
pip install nail-lang
```

## Quick Start

```python
from nail_lang import from_mcp, filter_by_effects, to_mcp

# 1. Your MCP tool list (standard MCP format)
mcp_tools = [
    {
        "name": "read_file",
        "description": "Read contents of a file",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        }
    },
    {
        "name": "http_get",
        "description": "Fetch a URL",
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"]
        }
    },
    {
        "name": "run_script",
        "description": "Execute a shell script",
        "inputSchema": {
            "type": "object",
            "properties": {"script": {"type": "string"}},
            "required": ["script"]
        }
    },
    {
        "name": "log",
        "description": "Log a message to console",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"]
        }
    },
]

# 2. Auto-annotate with NAIL effects (heuristic based on name + description)
fc_tools = from_mcp(mcp_tools)
# Effects inferred:
#   read_file  → ["FS"]    (keyword: "file", "read")
#   http_get   → ["NET"]   (keyword: "http")
#   run_script → ["PROC"]  (keyword: "script")
#   log        → ["IO"]    (default)

# 3. Sandbox to read-only (FS + IO only)
sandboxed = filter_by_effects(fc_tools, allowed=["FS", "IO"])
# → [read_file, log]   —  http_get and run_script excluded

# 4. Pass to your LLM (LiteLLM, OpenAI, Anthropic…)
import litellm
response = litellm.completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Read the config file"}],
    tools=sandboxed,
)

# 5. If needed, convert back to MCP format
mcp_sandboxed = to_mcp(sandboxed)
```

## API Reference

### `from_mcp(mcp_tools, *, auto_annotate=True, existing_effects=None)`

Convert MCP tool definitions to OpenAI Function Calling format with NAIL effect annotations.

| Parameter | Type | Description |
|-----------|------|-------------|
| `mcp_tools` | `list[dict]` | MCP tool dicts with `name`, `description`, `inputSchema` |
| `auto_annotate` | `bool` | Infer effects from name/description (default: `True`) |
| `existing_effects` | `dict[str, list[str]]` | Override map: `{"tool_name": ["FS"]}` |

**Returns:** List of OpenAI-format tool dicts with `"effects"` field added.

### `to_mcp(openai_tools)`

Convert OpenAI FC tools back to MCP format. Strips NAIL effect annotations.

**Returns:** List of MCP tool dicts with `name`, `description`, `inputSchema`.

### `infer_effects(name, description="")`

Heuristically infer NAIL effect labels from a tool's name and description.

**Effect inference rules:**

| Keywords | Effect | Examples |
|----------|--------|---------|
| file, read, write, path, dir, disk | `FS` | `read_file`, `write_config` |
| http, fetch, url, web, curl | `NET` | `http_get`, `fetch_url` |
| exec, run, shell, command, bash | `PROC` | `exec_command`, `run_script` |
| time, date, sleep, wait | `TIME` | `get_time`, `sleep_ms` |
| random, rand, uuid | `RAND` | `random_int`, `gen_uuid` |
| *(default)* | `IO` | `log`, `print_output` |

## Effect Scope Patterns

### Read-Only Agent

An agent that can only read files and produce output — no writes, no network:

```python
read_only_tools = filter_by_effects(fc_tools, allowed=["FS", "IO"])
```

Note: NAIL's `FS` effect covers both read and write. For finer-grained control,
use `existing_effects` to manually set `["FS_READ"]` vs `["FS_WRITE"]` and filter
by your own custom labels.

### Privileged Agent

An orchestrator that delegates to a sub-agent with restricted permissions:

```python
orchestrator_scope = ["FS", "IO", "NET"]
sub_agent_tools = filter_by_effects(all_tools, allowed=orchestrator_scope)
# Sub-agent cannot use PROC (shell execution) even if tools exist
```

### Air-Gapped Agent

An agent that cannot make any network requests:

```python
no_network_tools = filter_by_effects(all_tools, allowed=["FS", "IO", "TIME", "RAND"])
# All NET tools excluded
```

## Override Heuristics

If the auto-inferred effects are wrong for a specific tool, override them:

```python
custom_effects = {
    "database_query": ["FS"],    # DB reads treated as FS
    "send_email":     ["NET"],   # Email is a network operation
    "get_weather":    ["NET"],   # External API call
}

fc_tools = from_mcp(mcp_tools, existing_effects=custom_effects)
```

## MCP + LiteLLM Pipeline

```python
import litellm
from nail_lang import from_mcp, filter_by_effects

# Full pipeline
def create_sandboxed_agent(mcp_tools, allowed_effects):
    fc_tools = from_mcp(mcp_tools)
    safe_tools = filter_by_effects(fc_tools, allowed=allowed_effects)
    return safe_tools

# Use in LiteLLM completion
safe = create_sandboxed_agent(my_mcp_tools, allowed_effects=["FS", "IO"])

response = litellm.completion(
    model="claude-3-5-sonnet",
    messages=[{"role": "user", "content": "Audit the config directory"}],
    tools=safe,
)
```

## Effect Qualifiers with MCP (v0.9.2)

When converting MCP tools with `from_mcp()`, you can attach Effect Qualifiers to fine-tune policy at the tool level:

```python
from nail_lang import from_mcp, annotate_tool_effects

fc_tools = from_mcp(mcp_tools)

# Add qualifiers to specific tools after conversion
for tool in fc_tools:
    name = tool["function"]["name"]
    if name == "http_fetch":
        tool["function"]["effect_qualifiers"] = {
            "NET": {"scope": "external", "trust": "untrusted"}
        }
    elif name == "db_query":
        tool["function"]["effect_qualifiers"] = {
            "FS": {"scope": "internal", "trust": "trusted"}
        }
```

Qualifiers are preserved through `filter_by_effects()` and all provider conversions. Use them to implement fine-grained routing logic — for example, routing `untrusted` external tools through a stricter sandbox.


## See Also

- [filter_by_effects documentation](litellm.md)
- [FC Standard Proposal](../docs/fc-standard-proposal.md)
- [MCP Specification](https://modelcontextprotocol.io/)
- [LiteLLM MCP Bridge](https://docs.litellm.ai/docs/mcp)
