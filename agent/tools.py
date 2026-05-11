"""Tool registry and built-in tool implementations."""

from __future__ import annotations

import math
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# ── Schema helpers ────────────────────────────────────────────────────────────

def _schema(name: str, description: str, parameters: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", **parameters},
        },
    }


# ── Built-in tools ────────────────────────────────────────────────────────────

def tool_calculator(expression: str) -> str:
    """Evaluate a safe mathematical expression."""
    allowed = set("0123456789+-*/().% eE")
    if not all(c in allowed for c in expression):
        return "Error: expression contains disallowed characters"
    try:
        result = eval(expression, {"__builtins__": {}}, {k: getattr(math, k) for k in dir(math)})  # noqa: S307
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def tool_current_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def tool_read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error: {e}"


def tool_write_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def tool_http_get(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "hermes-agent/0.1"})
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read(32_000).decode("utf-8", errors="replace")
        return body
    except Exception as e:
        return f"Error: {e}"


def tool_run_shell(command: str, allowed_commands: list[str]) -> str:
    first_word = command.strip().split()[0] if command.strip() else ""
    if allowed_commands and first_word not in allowed_commands:
        return f"Error: command '{first_word}' not in allowed list"
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30  # noqa: S602
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"Error: {e}"


# ── Registry ──────────────────────────────────────────────────────────────────

SCHEMAS: dict[str, dict] = {
    "calculator": _schema(
        "calculator",
        "Evaluate a mathematical expression. Supports +, -, *, /, **, %, and math functions like sqrt, sin, cos, log.",
        {"properties": {"expression": {"type": "string", "description": "The expression to evaluate"}}, "required": ["expression"]},
    ),
    "current_time": _schema(
        "current_time",
        "Return the current UTC date and time.",
        {"properties": {}, "required": []},
    ),
    "read_file": _schema(
        "read_file",
        "Read a local file and return its contents.",
        {"properties": {"path": {"type": "string", "description": "Absolute or relative file path"}}, "required": ["path"]},
    ),
    "write_file": _schema(
        "write_file",
        "Write content to a local file, creating directories as needed.",
        {
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Text to write"},
            },
            "required": ["path", "content"],
        },
    ),
    "http_get": _schema(
        "http_get",
        "Fetch the body of a URL via HTTP GET (first 32 KB).",
        {"properties": {"url": {"type": "string", "description": "The URL to fetch"}}, "required": ["url"]},
    ),
    "run_shell": _schema(
        "run_shell",
        "Run a shell command and return its stdout/stderr.",
        {"properties": {"command": {"type": "string", "description": "Shell command to execute"}}, "required": ["command"]},
    ),
}


def build_registry(cfg: dict) -> tuple[list[dict], dict[str, Callable[..., str]]]:
    """Return (schemas_for_model, name→callable) based on config."""
    tool_cfg = cfg.get("tools", {})
    shell_cfg = cfg.get("shell", {})
    allowed_cmds = shell_cfg.get("allowed_commands", [])

    enabled_schemas: list[dict] = []
    dispatch: dict[str, Callable[..., str]] = {}

    def maybe(name: str, fn: Callable) -> None:
        if tool_cfg.get(name, False):
            enabled_schemas.append(SCHEMAS[name])
            dispatch[name] = fn

    maybe("calculator", lambda expression: tool_calculator(expression))
    maybe("current_time", lambda: tool_current_time())
    maybe("read_file", lambda path: tool_read_file(path))
    maybe("write_file", lambda path, content: tool_write_file(path, content))
    maybe("http_get", lambda url: tool_http_get(url))
    maybe("run_shell", lambda command: tool_run_shell(command, allowed_cmds))

    return enabled_schemas, dispatch


def call_tool(dispatch: dict[str, Callable], name: str, arguments: dict[str, Any]) -> str:
    fn = dispatch.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'"
    try:
        return fn(**arguments)
    except Exception as e:
        return f"Error running {name}: {e}"
