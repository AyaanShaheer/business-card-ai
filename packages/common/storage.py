from pathlib import Path
from uuid import UUID


class ObjectStorage:
    """
    Local development object-storage writer.

    The interface is intentionally small so a production S3
    implementation can replace it later.
    """

    def __init__(self, base_dir: str = "local_storage") -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def put(
        self,
        *,
        job_id: UUID,
        document_id: UUID,
        filename: str,
        content: bytes,
    ) -> str:
        job_dir = self._base_dir / str(job_id)

        job_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = job_dir / f"{document_id}_{filename}"

        destination.write_bytes(content)

        return f"local://{destination.as_posix()}"


class LocalObjectReader:
    """
    Reads objects from local development storage.

    The source URI must use:
        local://<absolute-or-relative-path>
    """

    def __init__(self, base_dir: str = "local_storage") -> None:
        self._base_dir = Path(base_dir).resolve()

    def read(self, *, source_uri: str) -> bytes:
        if not source_uri.startswith("local://"):
            raise ValueError(
                f"unsupported storage URI: {source_uri}"
            )

        path = Path(source_uri.removeprefix("local://"))

        if not path.is_absolute():
            path = self._base_dir / path

        path = path.resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"object not found: {path}"
            )

        if not path.is_file():
            raise FileNotFoundError(
                f"object is not a file: {path}"
            )

        return path.read_bytes()