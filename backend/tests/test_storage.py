from __future__ import annotations

import types
from pathlib import Path

import pytest

from app.services import storage


@pytest.fixture()
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    settings = types.SimpleNamespace(
        warehouse_dir=tmp_path,
        storage_max_entries=5_000,
        storage_max_depth=6,
        storage_preview_max_bytes=64,
    )
    monkeypatch.setattr(storage, "get_settings", lambda: settings)
    return tmp_path


def test_read_storage_file_returns_metadata_json(root: Path) -> None:
    metadata = root / "iceberg" / "demo" / "sales" / "metadata"
    metadata.mkdir(parents=True)
    target = metadata / "v1.metadata.json"
    target.write_text('{"format-version": 2}', encoding="utf-8")

    result = storage.read_storage_file("iceberg/demo/sales/metadata/v1.metadata.json")

    assert result["name"] == "v1.metadata.json"
    assert result["path"] == "iceberg/demo/sales/metadata/v1.metadata.json"
    assert result["content"] == '{"format-version": 2}'
    assert result["language"] == "json"
    assert result["binary"] is False
    assert result["truncated"] is False
    assert result["size"] == len('{"format-version": 2}')


def test_read_storage_file_flags_binary_formats(root: Path) -> None:
    target = root / "part-00000.parquet"
    target.write_bytes(b"PAR1\x00\x01\x02")

    result = storage.read_storage_file("part-00000.parquet")

    assert result["binary"] is True
    assert result["content"] == ""
    assert result["size"] == 7


def test_read_storage_file_truncates_large_text(root: Path) -> None:
    target = root / "delta" / "00000000000000000000.json"
    target.parent.mkdir()
    target.write_text("x" * 100, encoding="utf-8")

    result = storage.read_storage_file("delta/00000000000000000000.json")

    assert result["truncated"] is True
    assert result["content"] == "x" * 64
    assert result["size"] == 100
    assert result["max_bytes"] == 64


def test_read_storage_file_rejects_path_escape(root: Path) -> None:
    outside = root.parent / "outside.json"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(storage.StoragePathError):
        storage.read_storage_file("../outside.json")


def test_read_storage_file_rejects_directories(root: Path) -> None:
    (root / "delta").mkdir()

    with pytest.raises(storage.StoragePathError):
        storage.read_storage_file("delta")


def test_read_storage_file_missing_file(root: Path) -> None:
    with pytest.raises(storage.StorageNotFoundError):
        storage.read_storage_file("missing.json")


def test_resolve_storage_file_returns_absolute_path(root: Path) -> None:
    target = root / "iceberg" / "demo" / "metadata" / "v1.metadata.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

    resolved, normalized = storage.resolve_storage_file(
        "iceberg/demo/metadata/v1.metadata.json"
    )

    assert resolved == target.resolve()
    assert normalized == "iceberg/demo/metadata/v1.metadata.json"


def test_resolve_storage_file_rejects_escape(root: Path) -> None:
    outside = root.parent / "download-escape.json"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(storage.StoragePathError):
        storage.resolve_storage_file("../download-escape.json")
