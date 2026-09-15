from pathlib import Path

import pytest

from packages.common.storage import LocalObjectReader


def test_local_object_reader_reads_object(tmp_path):
    storage_dir = tmp_path / "objects"
    storage_dir.mkdir()

    source = storage_dir / "card.jpg"
    source.write_bytes(b"business-card-image")

    reader = LocalObjectReader(
        base_dir=str(storage_dir),
    )

    content = reader.read(
        source_uri=f"local://{source.as_posix()}",
    )

    assert content == b"business-card-image"


def test_local_object_reader_rejects_unknown_uri(tmp_path):
    reader = LocalObjectReader(
        base_dir=str(tmp_path),
    )

    with pytest.raises(FileNotFoundError):
        reader.read(
            source_uri="local:///does/not/exist.jpg",
        )


def test_local_object_reader_rejects_unsupported_scheme(tmp_path):
    reader = LocalObjectReader(
        base_dir=str(tmp_path),
    )

    with pytest.raises(ValueError, match="unsupported storage URI"):
        reader.read(
            source_uri="s3://bucket/card.jpg",
        )