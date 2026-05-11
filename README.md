# hermes-agent

A small tool-calling agent loop in Python, built around the [Hermes 3](https://nousresearch.com/hermes-3) family of open models. Works with a local Ollama install or any OpenAI-compatible endpoint (Together AI, OpenRouter, …).

Ships with two surfaces:

- **`hermes`** — interactive REPL for general-purpose tool use (calculator, current time, optional file I/O, HTTP GET, shell).
- **`webhook.py`** — a FastAPI server exposing a per-user fitness coach: it takes WhatsApp-style inbound messages, estimates macros from natural-language meal descriptions, and logs them to SQLite.

## How it works

A standard agent loop: `system → user → (assistant + tool_calls → tool results)* → final assistant message`. Two providers are wired up in `agent/providers.py`:

- **Ollama** (`ollama` Python client) — for fully local runs against `hermes3` GGUF builds.
- **OpenAI-compatible** (`openai` SDK with a custom `base_url`) — for Together AI, OpenRouter, etc., e.g. `NousResearch/Hermes-3-Llama-3.1-70B-Turbo`.

Tool schemas are advertised in OpenAI function-calling format. The loop runs up to `max_turns` iterations, feeding each tool result back as a `tool` message until the model returns a final answer.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Option A — local Ollama
ollama pull hermes3
python main.py "what's 17! divided by 13!?"

# Option B — Together AI
cp .env.example .env   # fill in TOGETHER_API_KEY
# edit config.yaml → provider: openai
python main.py
```

Without arguments, `main.py` drops into an interactive REPL.

## Fitness agent (`webhook.py`)

A stateful per-user agent that turns free-text messages into structured macro logs.

```bash
uvicorn webhook:app --host 0.0.0.0 --port 8000 --reload
```

```bash
curl -X POST localhost:8000/message \
  -H 'Content-Type: application/json' \
  -d '{"sender": "+5215512345678", "text": "had 3 eggs and a coffee"}'
# { "reply": "Logged: 3 eggs + coffee — 240 kcal, 18g protein, 2g carbs, 17g fat ..." }
```

Tools exposed to the model (`agent/fitness_tools.py`):

| Tool | Purpose |
|---|---|
| `log_meal` | Estimate macros from a description and persist them |
| `log_weight` | Record a body-weight entry |
| `get_daily_summary` | Today's meals + totals + goal deltas |
| `get_weekly_report` | 7-day macro rollup and weight trend |
| `set_goals` | Save daily calorie/macro targets |

Conversation history (last 16 messages by default) is stored in SQLite (`db/storage.py`) and replayed on every inbound message — so the agent has continuity without re-uploading context per request.

## Configuration

`config.yaml` controls which provider/model to use, which general-purpose tools are enabled in the REPL, and fitness/logging settings. Secrets (`TOGETHER_API_KEY`, etc.) come from `.env`.

## Project layout

```
hermes-agent/
├── main.py              — REPL entry point
├── webhook.py           — FastAPI server for the fitness agent
├── config.yaml          — provider + tool config
├── agent/
│   ├── agent.py         — generic tool-calling loop
│   ├── fitness_agent.py — per-user coach with macro tools
│   ├── providers.py     — ollama / openai-compatible chat shims
│   ├── tools.py         — built-in tools (calc, time, http, shell, file I/O)
│   └── fitness_tools.py — log_meal, log_weight, summaries, goals
└── db/
    └── storage.py       — SQLite persistence (messages, meals, weights, goals)
```
