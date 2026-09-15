from unittest.mock import Mock

import pytest

from apps.worker.runtime import WorkerRuntime


class FakeWorker:
    def __init__(self, results: list[bool]) -> None:
        self.results = results
        self.calls = 0

    def process_one(self) -> bool:
        self.calls += 1

        if self.results:
            return self.results.pop(0)

        return False


def test_runtime_processes_available_messages():
    worker = FakeWorker(
        [True, True, False],
    )

    runtime = WorkerRuntime(
        worker=worker,
        idle_sleep_seconds=0,
    )

    processed = runtime.run_once()

    assert processed == 2
    assert worker.calls == 3


def test_runtime_stops_when_stop_requested():
    worker = FakeWorker([True])

    runtime = WorkerRuntime(
        worker=worker,
        idle_sleep_seconds=0,
    )

    runtime.stop()

    processed = runtime.run_once()

    assert processed == 0
    assert worker.calls == 0


def test_runtime_propagates_worker_failure():
    worker = Mock()
    worker.process_one.side_effect = RuntimeError(
        "processing failed"
    )

    runtime = WorkerRuntime(
        worker=worker,
        idle_sleep_seconds=0,
    )

    with pytest.raises(
        RuntimeError,
        match="processing failed",
    ):
        runtime.run_once()

    worker.process_one.assert_called_once()


def test_runtime_rejects_negative_sleep():
    worker = FakeWorker([])

    with pytest.raises(
        ValueError,
        match="idle_sleep_seconds",
    ):
        WorkerRuntime(
            worker=worker,
            idle_sleep_seconds=-1,
        )