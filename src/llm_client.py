from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .config import ModelSettings
from .providers import ChatMessage, ChatRequest, CompatibleProvider, OpenAIProvider


class LLMUnavailableError(RuntimeError):
    """Raised when the configured LLM cannot be used."""


@dataclass(slots=True)
class PromptBundle:
    system_prompt: str
    user_prompt: str
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None


class LLMClient:
    def __init__(self, model_settings: ModelSettings) -> None:
        self.model_settings = model_settings
        api_key = model_settings.resolve_api_key()
        if not api_key:
            self.provider = None
            self.unavailable_reason = (
                f"Environment variable {model_settings.api_key_env} is not set."
            )
            return

        provider_type = model_settings.provider_type.lower()
        provider_cls = CompatibleProvider
        if provider_type == "openai":
            provider_cls = OpenAIProvider
        elif provider_type not in {"compatible", "openai"}:
            raise LLMUnavailableError(f"Unsupported provider type: {model_settings.provider_type}")

        self.provider = provider_cls(
            model_name=model_settings.model_name,
            api_base_url=model_settings.api_base_url,
            api_key=api_key,
            chat_completions_path=model_settings.chat_completions_path,
            timeout_seconds=model_settings.timeout_seconds,
        )
        self.unavailable_reason = ""

    @property
    def is_available(self) -> bool:
        return self.provider is not None

    def complete_text(
        self,
        prompt: PromptBundle,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        if not self.provider:
            raise LLMUnavailableError(self.unavailable_reason)

        request_payload = ChatRequest(
            messages=[
                ChatMessage(role="system", content=prompt.system_prompt),
                ChatMessage(role="user", content=prompt.user_prompt),
            ],
            temperature=prompt.temperature if prompt.temperature is not None else self.model_settings.temperature,
            max_tokens=prompt.max_tokens if prompt.max_tokens is not None else self.model_settings.max_tokens,
            top_p=prompt.top_p if prompt.top_p is not None else self.model_settings.top_p,
            response_format=response_format,
        )
        return self.provider.chat(request_payload).content

    def complete_json(self, prompt: PromptBundle) -> dict[str, Any]:
        raw_text = self.complete_text(prompt)
        return extract_json_object(raw_text)


def extract_json_object(text: str) -> dict[str, Any]:
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced_match:
        return json.loads(fenced_match.group(1))

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, offset = decoder.raw_decode(text[index:])
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
        except json.JSONDecodeError:
            continue

    raise ValueError("Model output does not contain a valid JSON object.")
