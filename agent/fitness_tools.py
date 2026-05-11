"""Fitness-specific tools exposed to the Hermes model."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Callable

from db import storage


def _schema(name: str, description: str, parameters: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", **parameters},
        },
    }


# ── Tool implementations ───────────────────────────────────────────────────────

def log_meal(
    user_id: str,
    description: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    date: str | None = None,
) -> str:
    meal_id = storage.insert_meal(user_id, description, calories, protein_g, carbs_g, fat_g, date)
    return json.dumps({
        "logged": True,
        "meal_id": meal_id,
        "macros": {"calories": calories, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g},
    })


def log_weight(user_id: str, weight_kg: float, notes: str = "", date: str | None = None) -> str:
    wid = storage.insert_weight(user_id, weight_kg, notes, date)
    return json.dumps({"logged": True, "weight_id": wid, "weight_kg": weight_kg})


def get_daily_summary(user_id: str, for_date: str | None = None) -> str:
    d = for_date or date.today().isoformat()
    meals = storage.get_daily_meals(user_id, d)
    totals = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    items = []
    for m in meals:
        totals["calories"] += m["calories"]
        totals["protein_g"] += m["protein_g"]
        totals["carbs_g"] += m["carbs_g"]
        totals["fat_g"] += m["fat_g"]
        items.append({"description": m["description"], **{k: m[k] for k in totals}})

    goals = storage.get_goals(user_id)
    return json.dumps({
        "date": d,
        "meals": items,
        "totals": totals,
        "goals": dict(goals) if goals else None,
    })


def get_weekly_report(user_id: str) -> str:
    today = date.today()
    start = (today - timedelta(days=6)).isoformat()
    end = today.isoformat()

    meals = storage.get_meals_range(user_id, start, end)
    weights = storage.get_weights_range(user_id, start, end)

    by_day: dict[str, dict] = {}
    for m in meals:
        d = m["date"]
        if d not in by_day:
            by_day[d] = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "meals": 0}
        by_day[d]["calories"] += m["calories"]
        by_day[d]["protein_g"] += m["protein_g"]
        by_day[d]["carbs_g"] += m["carbs_g"]
        by_day[d]["fat_g"] += m["fat_g"]
        by_day[d]["meals"] += 1

    weight_log = [{"date": w["date"], "weight_kg": w["weight_kg"]} for w in weights]
    goals = storage.get_goals(user_id)

    return json.dumps({
        "range": {"start": start, "end": end},
        "daily": by_day,
        "weights": weight_log,
        "goals": dict(goals) if goals else None,
    })


def set_goals(user_id: str, calories: float, protein_g: float, carbs_g: float, fat_g: float) -> str:
    storage.set_goals(user_id, calories, protein_g, carbs_g, fat_g)
    return json.dumps({"saved": True, "goals": {"calories": calories, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g}})


# ── Registry ───────────────────────────────────────────────────────────────────

SCHEMAS = [
    _schema(
        "log_meal",
        "Log a meal with estimated macros. Call this every time the user describes food they ate. "
        "Estimate the macros yourself from the description before calling.",
        {
            "properties": {
                "description": {"type": "string", "description": "Plain-text description of the meal"},
                "calories": {"type": "number", "description": "Estimated total kcal"},
                "protein_g": {"type": "number", "description": "Estimated protein in grams"},
                "carbs_g": {"type": "number", "description": "Estimated carbohydrates in grams"},
                "fat_g": {"type": "number", "description": "Estimated fat in grams"},
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD, omit for today"},
            },
            "required": ["description", "calories", "protein_g", "carbs_g", "fat_g"],
        },
    ),
    _schema(
        "log_weight",
        "Log the user's body weight. Call whenever the user mentions their current weight.",
        {
            "properties": {
                "weight_kg": {"type": "number", "description": "Body weight in kilograms"},
                "notes": {"type": "string", "description": "Optional context (e.g. 'morning, fasted')"},
                "date": {"type": "string", "description": "ISO date YYYY-MM-DD, omit for today"},
            },
            "required": ["weight_kg"],
        },
    ),
    _schema(
        "get_daily_summary",
        "Return today's logged meals with macro totals and remaining vs goals.",
        {
            "properties": {
                "for_date": {"type": "string", "description": "ISO date YYYY-MM-DD, omit for today"},
            },
            "required": [],
        },
    ),
    _schema(
        "get_weekly_report",
        "Return the last 7 days of macro totals and weight entries for trend analysis.",
        {"properties": {}, "required": []},
    ),
    _schema(
        "set_goals",
        "Save the user's daily macro and calorie targets.",
        {
            "properties": {
                "calories": {"type": "number"},
                "protein_g": {"type": "number"},
                "carbs_g": {"type": "number"},
                "fat_g": {"type": "number"},
            },
            "required": ["calories", "protein_g", "carbs_g", "fat_g"],
        },
    ),
]


def build_fitness_registry(user_id: str) -> tuple[list[dict], dict[str, Callable]]:
    dispatch: dict[str, Callable] = {
        "log_meal": lambda **kw: log_meal(user_id, **kw),
        "log_weight": lambda **kw: log_weight(user_id, **kw),
        "get_daily_summary": lambda **kw: get_daily_summary(user_id, **kw),
        "get_weekly_report": lambda **kw: get_weekly_report(user_id),
        "set_goals": lambda **kw: set_goals(user_id, **kw),
    }
    return SCHEMAS, dispatch
