"""OpenAI adapter — any OpenAI-compatible API."""

import os
import requests
from .base import LLMAdapter

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIAdapter(LLMAdapter):
    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(
            model=model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
            base_url=base_url or os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL),
        )

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

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
