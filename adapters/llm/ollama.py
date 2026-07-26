"""
Ollama adapter — local LLM, no API key needed.

Install Ollama: https://ollama.com
    ollama pull qwen2.5:14b
"""

import os
import requests
from .base import LLMAdapter

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:14b"


class OllamaAdapter(LLMAdapter):
    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(
            model=model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL),
            api_key="",  # Ollama doesn't need a key
            base_url=base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL),
        )

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }

        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
