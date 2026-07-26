"""
LLMAdapter — abstract base for LLM interaction.

All adapters implement a single method: chat(system, user) -> str.
"""

from abc import ABC, abstractmethod
from typing import Optional


class LLMAdapter(ABC):
    """Abstract LLM adapter."""

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        """Send a chat completion request, return the assistant's text response."""
        ...

    @property
    def name(self) -> str:
        return f"{self.__class__.__name__}({self.model})"
