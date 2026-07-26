"""
Config loader — reads .env + config.yaml, builds adapter configs.

No hardcoded keys. Everything from env vars or config file.
"""

import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load config from .env + config.yaml.

    Priority: config.yaml values > env vars > defaults.
    """
    # Load .env if present
    load_dotenv()

    config: Dict[str, Any] = {}

    # Load YAML config if present
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # Expand ${VAR} references in config values
    config = _expand_env(config)

    # Fill schema config from env if not set
    config.setdefault("schema", {})
    if "connection" not in config["schema"]:
        config["schema"]["connection"] = os.getenv("DB_CONNECTION", "")
        config["schema"]["adapter"] = config["schema"].get("adapter") or "postgres"

    # Fill LLM config from env
    config.setdefault("llm", {})
    if config["llm"].get("adapter", "") == "" or config["llm"].get("adapter") is None:
        config["llm"]["adapter"] = "openrouter"
    config["llm"].setdefault("api_key", "")
    config["llm"].setdefault("model", "")
    config["llm"].setdefault("base_url", "")

    # Web config
    config.setdefault("web", {})
    config["web"].setdefault("host", os.getenv("FLASK_HOST", "0.0.0.0"))
    config["web"].setdefault("port", int(os.getenv("FLASK_PORT", "5000")))
    config["web"].setdefault("debug", os.getenv("FLASK_DEBUG", "true").lower() == "true")

    return config


def _expand_env(obj):
    """Recursively expand ${VAR} references in strings."""
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env(i) for i in obj]
    elif isinstance(obj, str):
        return os.path.expandvars(obj)
    return obj
