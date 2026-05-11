"""Thin wrappers over Ollama and OpenAI-compatible chat APIs."""

from __future__ import annotations

import os
from typing import Any


def chat_ollama(base_url: str, model: str, messages: list[dict], tools: list[dict]) -> dict:
    import ollama

    client = ollama.Client(host=base_url)
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    response = client.chat(**kwargs)
    msg = response.message
    # Normalise to OpenAI-style dict
    return {
        "role": "assistant",
        "content": msg.content or "",
        "tool_calls": [
            {
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            }
            for tc in (msg.tool_calls or [])
        ],
    }


def chat_openai(base_url: str, model: str, api_key: str, messages: list[dict], tools: list[dict]) -> dict:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    response = client.chat.completions.create(**kwargs)
    choice = response.choices[0].message
    tool_calls = []
    for tc in choice.tool_calls or []:
        tool_calls.append(
            {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
        )
    return {
        "role": "assistant",
        "content": choice.content or "",
        "tool_calls": tool_calls,
    }


def chat(cfg: dict, messages: list[dict], tools: list[dict]) -> dict:
    provider = cfg.get("provider", "ollama")
    if provider == "ollama":
        c = cfg["ollama"]
        return chat_ollama(c["base_url"], c["model"], messages, tools)
    elif provider == "openai":
        c = cfg["openai_compatible"]
        key = os.getenv("TOGETHER_API_KEY") or os.getenv("OPENAI_API_KEY") or "none"
        return chat_openai(c["base_url"], c["model"], key, messages, tools)
    else:
        raise ValueError(f"Unknown provider: {provider!r}")
