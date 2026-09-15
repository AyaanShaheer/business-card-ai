from packages.common.settings import Settings

from apps.inference.client import QwenInferenceClient


def create_inference_client(
    settings: Settings,
) -> QwenInferenceClient:
    return QwenInferenceClient(
        base_url=settings.inference_base_url,
        model=settings.inference_model,
        api_key=settings.inference_api_key,
        timeout_seconds=settings.inference_timeout_seconds,
    )