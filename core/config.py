"""Configuration handling.

Non-secret settings (selected provider, model name, scoring weights) are
persisted to ``config.yaml`` next to the project root.  Secrets (API keys) are
read from environment variables first, and may be overridden per-session in the
UI without ever being written to disk.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Load a .env file from the project root if one exists.  This runs once at
# import time, before any os.environ lookups, so ANTHROPIC_API_KEY and friends
# are available without the user having to source the file manually.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed; rely on the shell environment

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"

PROVIDERS = ["Demo (offline)", "Ollama", "Claude", "OpenAI", "OpenAI via Azure"]

DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "Demo (offline)",
    "models": {
        "Ollama": "llama3.1",
        "Claude": "claude-sonnet-4-6",
        "OpenAI": "gpt-4o",
        "OpenAI via Azure": "gpt-4o",
    },
    "ollama_base_url": "http://localhost:11434",
    "azure_endpoint": "",          # e.g. https://my-resource.openai.azure.com
    "azure_api_version": "2024-06-01",
    "azure_deployment": "",        # Azure deployment name (defaults to model)
    "temperature": 0.2,
    "max_opportunities": 8,
    # scoring weights used by the legacy "weighted" method
    "weights": {"impact": 1.0, "effort": 0.6, "votes": 0.4},
    # prioritization method: "rice" (Reach x Impact x Confidence / Effort) or "weighted"
    "scoring": {"method": "rice"},
    "rice": {"vote_influence": 0.05},   # each net vote shifts the RICE score +/- 5%
    # opportunity clustering / dedup (local similarity, no extra model calls)
    "clustering": {"threshold": 0.52},
    # ROI / business-case assumptions (all editable in Settings)
    "roi": {
        "loaded_hourly_cost": 75,        # fully-loaded $/hour
        "working_weeks": 46,             # productive weeks per year
        "headcount_per_role": 1,         # FTEs per matched role (reach multiplier)
        "augmentation_factor": 0.5,      # augmentation realizes 50% of automation hours
        # weekly hours saved per role, indexed by impact 1..5
        "impact_hours_per_week": [1, 2, 4, 6, 10],
        # one-time implementation cost ($), indexed by effort 1..5
        "effort_cost": [5000, 15000, 35000, 60000, 100000],
        # annual run cost ($), indexed by effort 1..5
        "annual_run_cost": [1000, 3000, 6000, 12000, 24000],
    },
}

# Environment variable names per provider for API keys.
ENV_KEYS = {
    "Claude": "ANTHROPIC_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
    "OpenAI via Azure": "AZURE_OPENAI_API_KEY",
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                on_disk = yaml.safe_load(fh) or {}
            cfg = _deep_merge(cfg, on_disk)
        except Exception:
            pass
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    # never persist API keys
    to_save = {k: v for k, v in cfg.items() if not k.endswith("_api_key")}
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        yaml.safe_dump(to_save, fh, sort_keys=False)


def get_api_key(provider: str, session_override: str | None = None) -> str:
    """Resolve an API key: session override wins, otherwise the env var."""
    if session_override:
        return session_override
    env_name = ENV_KEYS.get(provider)
    return os.environ.get(env_name, "") if env_name else ""
