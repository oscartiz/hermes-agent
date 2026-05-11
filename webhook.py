"""
HTTP webhook server — the WhatsApp integration plugs in here.

Inbound:  POST /message   {"from": "<user_id>", "text": "<message>"}
Outbound: {"reply": "<agent response>"}

Run with:  uvicorn webhook:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from agent.fitness_agent import process_message
from db import storage

app = FastAPI(title="Hermes Fitness Agent")

_cfg: dict = {}


def _load_cfg() -> dict:
    global _cfg
    if not _cfg:
        with open("config.yaml") as f:
            _cfg = yaml.safe_load(f)
    return _cfg


@app.on_event("startup")
async def startup() -> None:
    storage.init_db()
    _load_cfg()


class InboundMessage(BaseModel):
    # "from" is a Python keyword, so we alias it
    sender: str = "default"       # maps to user_id
    text: str


@app.post("/message")
async def receive_message(msg: InboundMessage) -> dict:
    if not msg.text.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    reply = process_message(_load_cfg(), msg.sender, msg.text)
    return {"reply": reply}


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "ok"
