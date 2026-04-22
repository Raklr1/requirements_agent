from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(slots=True)
class ChatRequest:
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    response_format: dict[str, Any] | None = None


@dataclass(slots=True)
class ProviderResponse:
    model: str
    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    def __init__(
        self,
        *,
        model_name: str,
        api_base_url: str,
        api_key: str,
        chat_completions_path: str = "/chat/completions",
        timeout_seconds: int = 60,
    ) -> None:
        self.model_name = model_name
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key
        self.chat_completions_path = chat_completions_path
        self.timeout_seconds = timeout_seconds

    @abstractmethod
    def chat(self, request: ChatRequest) -> ProviderResponse:
        raise NotImplementedError
