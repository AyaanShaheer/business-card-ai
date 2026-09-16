import base64
import json
from typing import Any

import httpx


class QwenInferenceClient:
    """
    Client for a Qwen vision-language model exposed through an
    OpenAI-compatible API such as vLLM.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.model_name = model
        self.model_version = model

        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            transport=transport,
            timeout=timeout_seconds,
        )

    def extract(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
    ) -> dict[str, Any]:
        image_data = base64.b64encode(image_bytes).decode("ascii")

        image_url = (
            f"data:{mime_type};base64,{image_data}"
        )

        payload = {
            "model": self.model_name,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract the business card information. "
                                "Return ONLY valid JSON with these fields: "
                                "first_name, last_name, job_title, company, "
                                "location, phone_number, email_address. "
                                "Use null for fields that are not visible."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        },
                    ],
                }
            ],
        }

        try:
            response = self._client.post(
                "/chat/completions",
                json=payload,
            )
            response.raise_for_status()

        except httpx.HTTPError as exc:
            raise RuntimeError(
                "inference request failed"
            ) from exc

        try:
            response_body = response.json()

            content = response_body["choices"][0]["message"]["content"]

            if isinstance(content, list):
                text_parts = []

                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        text_parts.append(item["text"])

                content = "".join(text_parts)

            content = content.strip()
            if content.startswith("```"):
                lines = content.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

            return json.loads(content)

        except (
            KeyError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "invalid JSON inference response"
            ) from exc

    def close(self) -> None:
        self._client.close()