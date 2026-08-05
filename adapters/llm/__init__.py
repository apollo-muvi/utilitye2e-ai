"""LLM adapter factory."""

import os
from typing import Optional

from .base import LLMAdapter
from .glm import GlmAdapter
from .hermes import HermesAdapter
from .openai import OpenAIAdapter
from .openrouter import OpenRouterAdapter
from .ollama import OllamaAdapter


def create_llm_adapter(config: dict) -> LLMAdapter:
    """Create an LLM adapter from config dict.

    Expected config keys:
        adapter: openrouter | glm | openai | ollama
        model: (optional, defaults per adapter)
        api_key: (optional, falls back to env var)
        base_url: (optional, falls back to env var)
    """
    adapter_type = config.get("adapter", "openrouter").lower()

    if adapter_type == "openrouter":
        return OpenRouterAdapter(
            model=config.get("model", ""),
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
        )
    elif adapter_type == "hermes":
        return HermesAdapter(
            model=config.get("model", ""),
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
        )
    elif adapter_type == "glm":
        return GlmAdapter(
            model=config.get("model", ""),
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
        )
    elif adapter_type == "openai":
        return OpenAIAdapter(
            model=config.get("model", ""),
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
        )
    elif adapter_type == "ollama":
        return OllamaAdapter(
            model=config.get("model", ""),
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
        )
    else:
        raise ValueError(f"Unknown LLM adapter: {adapter_type}")
