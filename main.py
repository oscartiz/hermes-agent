"""Entry point: hermes [QUERY]  — or run with no args for interactive mode."""

from __future__ import annotations

import sys

import yaml
from dotenv import load_dotenv

load_dotenv()


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main() -> None:
    cfg = load_config()

    from agent.agent import interactive, run

    args = sys.argv[1:]
    if args:
        run(cfg, " ".join(args))
    else:
        interactive(cfg)


if __name__ == "__main__":
    main()
