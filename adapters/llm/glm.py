"""
GLM adapter — z.ai / ZhipuAI GLM models via OpenAI-compatible API.

Uses requests (no SDK dependency) against the z.ai coding/paas endpoint.
"""

import os
import requests
from typing import Optional
from .base import LLMAdapter

# z.ai default endpoint
DEFAULT_BASE_URL = "https://api.z.ai/api/coding/paas/v4"
DEFAULT_MODEL = "glm-4-flash"


class GlmAdapter(LLMAdapter):
    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(
            model=model or os.getenv("GLM_MODEL", DEFAULT_MODEL),
            api_key=api_key or os.getenv("GLM_API_KEY", ""),
            base_url=base_url or os.getenv("GLM_BASE_URL", DEFAULT_BASE_URL),
        )

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        if not self.api_key:
            raise ValueError("GLM_API_KEY not set — get one at https://z.ai")

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
        data = resp.json()
        return data["choices"][0]["message"]["content"]
