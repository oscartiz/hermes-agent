"""Main agent loop."""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from agent.providers import chat
from agent.tools import build_registry, call_tool

console = Console()


def _render_tool_call(name: str, args: dict, result: str, show: bool) -> None:
    if not show:
        return
    console.print(
        Panel(
            Syntax(json.dumps(args, indent=2), "json", theme="monokai"),
            title=f"[bold cyan]tool: {name}[/]",
            subtitle=f"[dim]→ {result[:120]}{'…' if len(result) > 120 else ''}[/]",
            border_style="cyan",
        )
    )


def run(cfg: dict, query: str) -> None:
    agent_cfg = cfg.get("agent", {})
    log_cfg = cfg.get("logging", {})
    max_turns = agent_cfg.get("max_turns", 20)
    system_prompt = agent_cfg.get("system_prompt", "You are a helpful assistant.")
    show_tool_calls = log_cfg.get("show_tool_calls", True)

    tool_schemas, dispatch = build_registry(cfg)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query},
    ]

    console.print(Panel(Text(query, style="bold white"), title="[bold green]User[/]", border_style="green"))

    for turn in range(max_turns):
        response = chat(cfg, messages, tool_schemas)
        messages.append({"role": "assistant", "content": response["content"], "tool_calls": response["tool_calls"]})

        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            # Final answer
            console.print(
                Panel(
                    Text(response["content"], style="white"),
                    title=f"[bold yellow]Hermes[/] [dim](turn {turn + 1})[/]",
                    border_style="yellow",
                )
            )
            return

        # Execute tools and feed results back
        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            raw_args = fn.get("arguments", {})
            args: dict = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
            result = call_tool(dispatch, name, args)
            _render_tool_call(name, args, result, show_tool_calls)
            messages.append({"role": "tool", "content": result, "name": name})

    console.print("[bold red]Max turns reached — forcing final answer.[/]")


def interactive(cfg: dict) -> None:
    console.print("[bold magenta]Hermes Agent[/] — type [dim]exit[/] to quit\n")
    while True:
        try:
            query = console.input("[bold green]>[/] ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if query.lower() in ("exit", "quit", "q"):
            break
        if not query:
            continue
        run(cfg, query)
        console.print()
