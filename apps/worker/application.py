from sqlalchemy.engine import Engine

from apps.inference.client import QwenInferenceClient
from apps.worker.worker import Worker


class WorkerApplication:
    """Owns worker dependencies and their lifecycle."""

    def __init__(
        self,
        *,
        worker: Worker,
        engine: Engine,
        inference_client: QwenInferenceClient,
    ) -> None:
        self.worker = worker
        self._engine = engine
        self._inference_client = inference_client

    def close(self) -> None:
        self._inference_client.close()
        self._engine.dispose()