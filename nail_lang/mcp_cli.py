"""MCP CLI: Logic for `nail mcp` subcommands.

Provides check, convert, a2a, and serve operations for MCP-compatible tools.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from nail_lang._mcp import to_a2a_agent_card, to_mcp, validate_for_mcp


def _unwrap_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Return function payload for OpenAI-style tools, else the tool itself."""
    if not isinstance(tool, dict):
        return {}
    fn = tool.get("function")
    if isinstance(fn, dict):
        return fn
    return tool


def _load_tools(input_path: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Load tools from a .nail file (array or module with 'tools')."""
    p = Path(input_path)
    if not p.exists():
        return None, f"File not found: {input_path}"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return None, f"JSON parse error in {input_path}: {e}"
    except OSError as e:
        return None, f"Cannot read file {input_path}: {e}"

    tools: Any = data
    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        tools = data["tools"]

    if not isinstance(tools, list):
        return None, f"Expected a JSON array of tools or module with 'tools', got {type(data).__name__}"
    return tools, None


def _mcp_tools_with_effects(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert tools to MCP format and preserve NAIL effects as extension."""
    mcp_tools = to_mcp(tools)
    effects_by_name: dict[str, list[Any]] = {}
    for tool in tools:
        fn = _unwrap_tool(tool)
        name = fn.get("name")
        effects = fn.get("effects")
        if isinstance(name, str) and isinstance(effects, list):
            effects_by_name[name] = list(effects)

    for mcp_tool in mcp_tools:
        name = mcp_tool.get("name")
        if isinstance(name, str) and name in effects_by_name:
            mcp_tool["_nail_effects"] = effects_by_name[name]
    return mcp_tools


def mcp_check(input_path: str, fmt: str = "human") -> int:
    """Validate tool list for MCP compatibility."""
    tools, err = _load_tools(input_path)
    if err:
        if fmt == "json":
            print(json.dumps({"ok": False, "errors": [err]}, indent=2))
        else:
            print(f"✗ {err}", file=sys.stderr)
        return 1

    errors = validate_for_mcp(tools)
    ok = len(errors) == 0

    if fmt == "json":
        print(json.dumps({"ok": ok, "errors": errors}, indent=2, ensure_ascii=False))
    else:
        total = len(tools)
        if ok:
            print(f"✓ {input_path}  [{total} tool(s)]  MCP-compatible")
        else:
            print(f"✗ {input_path}  [{total} tool(s)]  MCP-compatible")
            for e in errors:
                print(f"  ERROR: {e}")

    return 0 if ok else 2


def mcp_convert(input_path: str, out: str | None = None, fmt: str = "human") -> int:
    """Convert NAIL tools to MCP tool schema."""
    tools, err = _load_tools(input_path)
    if err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    errors = validate_for_mcp(tools)
    if errors:
        if fmt == "json":
            print(json.dumps({"ok": False, "errors": errors}, indent=2, ensure_ascii=False))
        else:
            print(f"✗ {input_path}  [{len(tools)} tool(s)]  MCP-compatible")
            for e in errors:
                print(f"  ERROR: {e}")
        return 2

    payload = {"tools": _mcp_tools_with_effects(tools)}
    output = json.dumps(payload, indent=2, ensure_ascii=False)

    if out:
        try:
            Path(out).write_text(output + "\n", encoding="utf-8")
            if fmt == "human":
                print(f"✓ Converted {len(payload['tools'])} tool(s) → MCP  →  {out}")
        except OSError as e:
            print(f"✗ Cannot write output file: {e}", file=sys.stderr)
            return 1
    else:
        print(output)

    return 0


def mcp_a2a(
    input_path: str,
    name: str,
    url: str,
    description: str = "",
    version: str = "0.1.0",
    out: str | None = None,
    fmt: str = "human",
) -> int:
    """Generate A2A Agent Card from NAIL tools."""
    tools, err = _load_tools(input_path)
    if err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    errors = validate_for_mcp(tools)
    if errors:
        if fmt == "json":
            print(json.dumps({"ok": False, "errors": errors}, indent=2, ensure_ascii=False))
        else:
            print(f"✗ {input_path}  [{len(tools)} tool(s)]  MCP-compatible")
            for e in errors:
                print(f"  ERROR: {e}")
        return 2

    card = to_a2a_agent_card(
        tools,
        name=name,
        url=url,
        description=description,
        version=version,
    )
    output = json.dumps(card, indent=2, ensure_ascii=False)

    if out:
        try:
            Path(out).write_text(output + "\n", encoding="utf-8")
        except OSError as e:
            print(f"✗ Cannot write output file: {e}", file=sys.stderr)
            return 1
    else:
        print(output)

    if fmt == "human":
        print(
            f"✓ A2A Agent Card generated: {name} ({len(card.get('skills', []))} skills)",
            file=sys.stderr,
        )

    return 0


def mcp_serve(
    input_path: str,
    server_name: str = "nail-mcp-server",
    version: str = "0.1.0",
) -> int:
    """Run a minimal MCP stdio server with JSON-RPC 2.0."""
    tools, err = _load_tools(input_path)
    if err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    errors = validate_for_mcp(tools)
    if errors:
        print(f"✗ {input_path}  [{len(tools)} tool(s)]  MCP-compatible", file=sys.stderr)
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        return 2

    tools_with_effects = _mcp_tools_with_effects(tools)
    tools_for_list = []
    for tool in tools_with_effects:
        t = dict(tool)
        t.pop("_nail_effects", None)
        tools_for_list.append(t)

    print(f"NAIL MCP Server started: {len(tools_for_list)} tools available", file=sys.stderr)

    try:
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
                print(json.dumps(err_resp), flush=True)
                continue

            if not isinstance(req, dict):
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32600, "message": "Invalid Request"},
                }
                print(json.dumps(err_resp), flush=True)
                continue

            req_id = req.get("id")
            method = req.get("method")
            if not isinstance(method, str):
                if req_id is not None:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32600, "message": "Invalid Request"},
                    }
                    print(json.dumps(err_resp), flush=True)
                continue

            if method == "initialized":
                continue  # notification: no response

            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": server_name, "version": version},
                    "capabilities": {"tools": {}},
                }
                resp = {"jsonrpc": "2.0", "id": req_id, "result": result}
                print(json.dumps(resp), flush=True)
                continue

            if method == "tools/list":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_for_list}}
                print(json.dumps(resp), flush=True)
                continue

            if method == "tools/call":
                params = req.get("params") if isinstance(req.get("params"), dict) else {}
                name = params.get("name", "")
                msg = f"Tool {name} called. Implement handler with @server.tool_handler()."
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": msg}]},
                }
                print(json.dumps(resp), flush=True)
                continue

            if method == "resources/list":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}
                print(json.dumps(resp), flush=True)
                continue

            if method == "prompts/list":
                resp = {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}
                print(json.dumps(resp), flush=True)
                continue

            if req_id is not None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": "Method not found"},
                }
                print(json.dumps(resp), flush=True)
    except KeyboardInterrupt:
        return 0

    return 0
