"""
OpenRouter adapter — access all models (OpenAI, Anthropic, Google, etc.)
via a single API. https://openrouter.ai/keys

Cost-effective routing to many providers.
"""

import os
import requests
from .base import LLMAdapter

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"


class OpenRouterAdapter(LLMAdapter):
    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(
            model=model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL),
            api_key=api_key or os.getenv("OPENROUTER_API_KEY", ""),
            base_url=base_url or os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL),
        )

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set — get one at https://openrouter.ai/keys")

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

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
