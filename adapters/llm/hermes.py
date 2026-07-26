"""
Hermes API-based LLM adapter.
Uses the local Hermes API server which already has OpenRouter configured.
"""

import os
import requests
from .base import LLMAdapter

HERMES_URL = os.getenv("HERMES_API_URL", "http://localhost:8642/v1")
HERMES_KEY = os.getenv("HERMES_API_KEY", "hermes-api-key-local")
HERMES_MODEL = os.getenv("HERMES_MODEL", "hermes-agent")


class HermesAdapter(LLMAdapter):
    """Adapter for local Hermes API server. Uses Hermes's OpenRouter connection."""

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(
            model=model or HERMES_MODEL,
            api_key=api_key or HERMES_KEY,
            base_url=base_url or HERMES_URL,
        )

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]