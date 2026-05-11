"""Fitness agent: stateful, per-user conversation with macro tracking."""

from __future__ import annotations

import json
from typing import Any

from agent.fitness_tools import build_fitness_registry
from agent.providers import chat
from agent.tools import call_tool
from db import storage

SYSTEM_PROMPT = """You are a knowledgeable and encouraging fitness coach assistant.

Your job:
1. When the user describes any food or meal, ALWAYS call log_meal with your best macro estimate.
   Do not ask for confirmation first — log it, then show the numbers to the user.
2. When the user mentions their weight, call log_weight immediately.
3. When asked for a summary or progress, call get_daily_summary or get_weekly_report and present
   the results in a clear, friendly format.
4. If the user wants to set daily targets, call set_goals.

Macro estimation guidelines:
- Use standard nutritional values (per 100g or per unit) from your training knowledge.
- When quantities are vague (e.g. "a bowl of rice"), use typical portion sizes.
- Always show the user your estimates so they can correct you.
- Be concise — WhatsApp messages should be short and scannable.
  Use line breaks and simple formatting, not markdown headers or tables.

Reply in the same language the user writes in.
"""


def process_message(cfg: dict, user_id: str, text: str) -> str:
    """Process one WhatsApp message and return the reply string."""
    storage.init_db()

    tool_schemas, dispatch = build_fitness_registry(user_id)

    # Build message history (system + last N turns + new user message)
    history = storage.get_recent_messages(user_id, limit=16)
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for row in history:
        messages.append({"role": row["role"], "content": row["content"]})
    messages.append({"role": "user", "content": text})

    # Persist user message
    storage.append_message(user_id, "user", text)

    max_turns = cfg.get("agent", {}).get("max_turns", 10)
    final_reply = ""

    for _ in range(max_turns):
        response = chat(cfg, messages, tool_schemas)
        messages.append({
            "role": "assistant",
            "content": response["content"],
            "tool_calls": response["tool_calls"],
        })

        tool_calls = response.get("tool_calls", [])
        if not tool_calls:
            final_reply = response["content"]
            break

        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            raw_args = fn.get("arguments", {})
            args: dict = raw_args if isinstance(raw_args, dict) else json.loads(raw_args)
            result = call_tool(dispatch, name, args)
            messages.append({"role": "tool", "content": result, "name": name})

    if not final_reply:
        final_reply = "Done! Let me know if you need anything else."

    storage.append_message(user_id, "assistant", final_reply)
    return final_reply
