from pathlib import Path

import pytest

from app.services.importer import (
    ImportValidationError,
    detect_source_format,
    sanitize_table_name,
    validate_identifier,
)


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("customers", "customers"),
        ("Sales 2026.Q1", "sales_2026_q1"),
        ("2026-events", "t_2026_events"),
        ("...", "imported_table"),
    ],
)
def test_sanitize_table_name(stem: str, expected: str) -> None:
    assert sanitize_table_name(stem) == expected


@pytest.mark.parametrize(
    ("value", "label", "valid"),
    [
        ("default", "namespace", True),
        ("_private", "namespace", True),
        ("my_db2", "namespace", True),
        ("2bad", "namespace", False),
        ("has space", "namespace", False),
        ("semi;colon", "namespace", False),
        ("", "namespace", False),
    ],
)
def test_validate_identifier(value: str, label: str, valid: bool) -> None:
    if valid:
        assert validate_identifier(value, label) == value
    else:
        with pytest.raises(ImportValidationError):
            validate_identifier(value, label)


def test_detect_source_format_variants(tmp_path: Path) -> None:
    assert detect_source_format(tmp_path / "a.csv", None) == "csv"
    assert detect_source_format(tmp_path / "a.json", None) == "json"
    assert detect_source_format(tmp_path / "a.jsonl", None) == "json"
    assert detect_source_format(tmp_path / "a.ndjson", None) == "json"
    assert detect_source_format(tmp_path / "a.parquet", None) == "parquet"
    assert detect_source_format(tmp_path / "a.txt", None) == "txt"
    assert detect_source_format(tmp_path / "a.orc", None) == "orc"
    assert detect_source_format(tmp_path / "a.avro", None) == "avro"
    assert detect_source_format(tmp_path / "a.data", "csv") == "csv"

    with pytest.raises(ImportValidationError):
        detect_source_format(tmp_path / "a.csv", "xml")
    with pytest.raises(ImportValidationError):
        detect_source_format(tmp_path / "a.bin", None)
