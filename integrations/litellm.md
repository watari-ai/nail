# NAIL × LiteLLM Integration Guide

## Overview

NAIL is an AI-native language with a formal effect system that declares and enforces which side effects (filesystem, network, process, etc.) a tool is permitted to invoke. LiteLLM is a widely-adopted gateway (42,000+ GitHub stars) that normalizes 100+ LLM APIs to a unified OpenAI-compatible interface. Together, NAIL provides **effect safety** (what tools can do) while LiteLLM provides **provider portability** (which model runs them) — giving you both security and flexibility in multi-LLM agent pipelines.

## Installation

```bash
pip install nail-lang litellm
```

## Quick Start

```python
from nail_lang import filter_by_effects
import litellm

# Define tools with NAIL effect annotations
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from disk",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Path to file"}},
                "required": ["path"]
            },
            "effects": ["FS"]
        }
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Fetch content from a URL",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "URL to fetch"}},
                "required": ["url"]
            },
            "effects": ["NET"]
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_message",
            "description": "Log a message to console",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"]
            },
            "effects": ["IO"]
        }
    }
]

# Pre-flight validation: filter to sandbox (FS + IO only, no network)
sandbox_tools = filter_by_effects(tools, allowed=["FS", "IO"])
# → [read_file_tool, log_message_tool]
# http_get excluded: requires NET which is not in allowed set

# Pass effect-verified tools to LiteLLM
response = litellm.completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Read the config file and log its contents"}],
    tools=sandbox_tools
)

print(response.choices[0].message)
```

## Use Cases

### 1. Read-Only Sandbox

Restrict an audit or verification agent to read-only filesystem and console output only — no network, no writes, no process execution:

```python
from nail_lang import filter_by_effects
import litellm

# All available tools in your system
all_tools = [
    {"type": "function", "function": {"name": "read_file",    "effects": ["FS"],       ...}},
    {"type": "function", "function": {"name": "write_file",   "effects": ["FS"],       ...}},
    {"type": "function", "function": {"name": "http_get",     "effects": ["NET"],      ...}},
    {"type": "function", "function": {"name": "run_command",  "effects": ["PROC"],     ...}},
    {"type": "function", "function": {"name": "log",          "effects": ["IO"],       ...}},
]

# Audit agent: read files and log findings only
# Note: NAIL's FS covers both read and write; split into FS_READ/FS_WRITE is planned for a future version.
# For now, combine with your own naming convention to distinguish read vs write tools.
audit_tools = filter_by_effects(all_tools, allowed=["FS", "IO"])

response = litellm.completion(
    model="claude-3-5-sonnet",  # LiteLLM routes to Anthropic
    messages=[{"role": "user", "content": "Audit the /etc/config directory for anomalies"}],
    tools=audit_tools
)
```

### 2. Effect-Scoped Multi-Agent

When Agent A (orchestrator) delegates to Agent B (sub-agent), restrict B's tool set to the effects A itself is authorized for. This prevents privilege escalation across agent boundaries:

```python
from nail_lang import filter_by_effects
import litellm

# Agent A is authorized for FS and IO only
agent_a_effects = ["FS", "IO"]

# Agent B has access to a broader tool set
agent_b_all_tools = [
    {"type": "function", "function": {"name": "read_file",   "effects": ["FS"],  ...}},
    {"type": "function", "function": {"name": "http_post",   "effects": ["NET"], ...}},
    {"type": "function", "function": {"name": "exec_script", "effects": ["PROC"],...}},
    {"type": "function", "function": {"name": "log",         "effects": ["IO"],  ...}},
]

# Delegation: constrain B's tools to A's declared scope
agent_b_scoped_tools = filter_by_effects(agent_b_all_tools, allowed=agent_a_effects)
# → [read_file_tool, log_tool]
# http_post (NET) and exec_script (PROC) are excluded

# B can only use tools within A's authorized effect scope
response = litellm.completion(
    model="gpt-4o-mini",  # LiteLLM can route to a cheaper model for sub-tasks
    messages=[{"role": "user", "content": "Process the data file"}],
    tools=agent_b_scoped_tools
)
```

### 3. MCP Bridge + NAIL

LiteLLM's MCP Bridge converts MCP (Model Context Protocol) tools to OpenAI function-calling format. NAIL effect annotations can be applied post-conversion to sandbox MCP tools:

```python
import litellm
from nail_lang import filter_by_effects

# Step 1: LiteLLM converts MCP tools to OpenAI format
mcp_server_tools = [...]  # Raw tools from MCP server
openai_format_tools = litellm.utils.convert_mcp_to_openai(mcp_server_tools)

# Step 2: Annotate tools with NAIL effects
# TODO: future API — nail.annotate_effects() will auto-annotate based on tool names/descriptions
# annotated_tools = nail.annotate_effects(openai_format_tools)

# For now, manually add effects to the converted tools:
for tool in openai_format_tools:
    name = tool["function"]["name"]
    if "file" in name or "read" in name or "write" in name:
        tool["function"]["effects"] = ["FS"]
    elif "http" in name or "fetch" in name or "request" in name:
        tool["function"]["effects"] = ["NET"]
    elif "exec" in name or "run" in name or "shell" in name:
        tool["function"]["effects"] = ["PROC"]
    else:
        tool["function"]["effects"] = ["IO"]  # default conservative

# Step 3: Sandbox to safe effects
safe_tools = filter_by_effects(openai_format_tools, allowed=["FS", "IO"])

# Step 4: Use with LiteLLM
response = litellm.completion(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Process the uploaded file"}],
    tools=safe_tools
)
```

## API Reference

### `filter_by_effects(tools, allowed)`

Filters a list of OpenAI-format tool definitions to include only those whose effect sets are fully contained within the `allowed` set.

**Arguments:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tools` | `list[dict]` | List of OpenAI-format tool objects. Each tool's `function` dict may include an `"effects"` key. |
| `allowed` | `list[str]` | Allowed effect labels. Valid values: `"IO"`, `"FS"`, `"NET"`, `"PROC"`, `"RAND"`. |

**Returns:** `list[dict]` — Filtered list of tools where every declared effect is in the `allowed` set.

**Behavior:**
- Tools with no `"effects"` field are treated as having **unrestricted effects** and are excluded when any `allowed` restriction is in place (recommended for production). See `fc-standard-proposal.md` Section 4.3 for configuration options.
- Tools whose entire effect set is a subset of `allowed` are included.
- Tools with any effect outside `allowed` are excluded.

**Example:**

```python
from nail_lang import filter_by_effects

tools = [
    {"type": "function", "function": {"name": "read_file",    "effects": ["FS"]}},
    {"type": "function", "function": {"name": "http_get",     "effects": ["NET"]}},
    {"type": "function", "function": {"name": "download",     "effects": ["NET", "FS"]}},
    {"type": "function", "function": {"name": "log",          "effects": ["IO"]}},
    {"type": "function", "function": {"name": "unknown_tool"                         }},  # no effects
]

result = filter_by_effects(tools, allowed=["FS", "IO"])
# Returns: [read_file_tool, log_tool]
# Excluded: http_get (NET not allowed), download (NET not allowed), unknown_tool (unrestricted)
```

## See Also

- [fc-standard-proposal.md](../docs/fc-standard-proposal.md) — NAIL effect system formal specification
- [LiteLLM documentation](https://docs.litellm.ai/)
- [LiteLLM MCP Bridge](https://docs.litellm.ai/docs/mcp)
- [OpenAI Function Calling spec](https://platform.openai.com/docs/guides/function-calling)
- [NAIL GitHub](https://github.com/watari-ai/nail)
- [NAIL PyPI](https://pypi.org/project/nail-lang/)
