from __future__ import annotations

import json
from urllib import error, request

from .base import BaseProvider, ChatRequest, ProviderResponse


class CompatibleProvider(BaseProvider):
    def chat(self, request_payload: ChatRequest) -> ProviderResponse:
        payload: dict[str, object] = {
            "model": self.model_name,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in request_payload.messages
            ],
        }

        if request_payload.temperature is not None:
            payload["temperature"] = request_payload.temperature
        if request_payload.max_tokens is not None:
            payload["max_tokens"] = request_payload.max_tokens
        if request_payload.top_p is not None:
            payload["top_p"] = request_payload.top_p
        if request_payload.response_format is not None:
            payload["response_format"] = request_payload.response_format

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        endpoint = f"{self.api_base_url}{self.chat_completions_path}"
        http_request = request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Provider request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Provider request failed: {exc.reason}") from exc

        parsed = json.loads(raw_body)
        content = _extract_message_content(parsed)
        return ProviderResponse(model=self.model_name, content=content, raw=parsed)


def _extract_message_content(response_body: dict[str, object]) -> str:
    choices = response_body.get("choices", [])
    if not choices:
        raise RuntimeError("Provider response does not contain choices.")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise RuntimeError("Provider response choice is malformed.")

    message = first_choice.get("message", {})
    if not isinstance(message, dict):
        raise RuntimeError("Provider response message is malformed.")

    content = message.get("content", "")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)

    return str(content)
