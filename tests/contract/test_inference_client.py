import base64

import httpx
import pytest

from apps.inference.client import QwenInferenceClient


def test_client_builds_multimodal_request():
    captured_request = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["json"] = request.read()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"first_name":"Ahmed",'
                                '"last_name":"Khan",'
                                '"job_title":"CEO",'
                                '"company":"Acme",'
                                '"location":"Dubai",'
                                '"phone_number":"+971501234567",'
                                '"email_address":"ahmed@acme.com"}'
                            )
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)

    client = QwenInferenceClient(
        base_url="http://qwen:8000/v1",
        model="Qwen/Qwen3-VL-8B-Instruct",
        api_key="test-key",
        transport=transport,
    )

    result = client.extract(
        image_bytes=b"fake-image",
        mime_type="image/jpeg",
    )

    assert result["first_name"] == "Ahmed"
    assert result["company"] == "Acme"


def test_client_rejects_invalid_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "not-valid-json"
                        }
                    }
                ]
            },
        )

    client = QwenInferenceClient(
        base_url="http://qwen:8000/v1",
        model="Qwen/Qwen3-VL-8B-Instruct",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        client.extract(
            image_bytes=b"fake-image",
            mime_type="image/jpeg",
        )


def test_client_rejects_failed_http_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"error": "inference failed"},
        )

    client = QwenInferenceClient(
        base_url="http://qwen:8000/v1",
        model="Qwen/Qwen3-VL-8B-Instruct",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError, match="inference request failed"):
        client.extract(
            image_bytes=b"fake-image",
            mime_type="image/jpeg",
        )


def test_client_converts_image_to_data_url():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["body"] = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "{}"
                        }
                    }
                ]
            },
        )

    client = QwenInferenceClient(
        base_url="http://qwen:8000/v1",
        model="Qwen/Qwen3-VL-8B-Instruct",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    client.extract(
        image_bytes=b"abc",
        mime_type="image/png",
    )

    content = captured["body"]["messages"][0]["content"]

    image_item = next(
        item
        for item in content
        if item["type"] == "image_url"
    )

    image_url = image_item["image_url"]["url"]

    expected = (
        "data:image/png;base64,"
        + base64.b64encode(b"abc").decode("ascii")
    )

    assert image_url == expected