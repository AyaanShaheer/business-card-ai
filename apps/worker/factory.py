from apps.inference.factory import create_inference_client
from apps.inference.client import QwenInferenceClient
from apps.worker.application import WorkerApplication
from apps.worker.processor import DocumentProcessor
from apps.worker.worker import Worker
from packages.common.db import create_db_engine
from packages.common.settings import Settings
from packages.common.storage import LocalObjectReader


def create_worker_application(
    *,
    settings: Settings,
    queue,
) -> WorkerApplication:
    engine = create_db_engine(
        str(settings.database_url)
    )

    object_reader = LocalObjectReader()

    inference_client: QwenInferenceClient = create_inference_client(
        settings
    )

    processor = DocumentProcessor(
        engine=engine,
        object_reader=object_reader,
        inference_client=inference_client,
    )

    worker = Worker(
        queue=queue,
        processor=processor,
    )

    return WorkerApplication(
        worker=worker,
        engine=engine,
        inference_client=inference_client,
    )