from apps.inference.client import QwenInferenceClient
from apps.inference.factory import create_inference_client
from packages.common.settings import Settings


def test_factory_creates_qwen_client(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@localhost:5432/db",
    )
    monkeypatch.setenv(
        "INFERENCE_BASE_URL",
        "http://qwen:8000/v1",
    )
    monkeypatch.setenv(
        "INFERENCE_MODEL",
        "Qwen/Qwen3-VL-8B-Instruct",
    )
    monkeypatch.setenv(
        "INFERENCE_API_KEY",
        "test-key",
    )

    settings = Settings()

    client = create_inference_client(settings)

    assert isinstance(client, QwenInferenceClient)
    assert client.model_name == "Qwen/Qwen3-VL-8B-Instruct"

    client.close()