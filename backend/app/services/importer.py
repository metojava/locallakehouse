from __future__ import annotations

import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from pyspark.sql import SparkSession

from ..config import PROJECT_ROOT, get_settings
from ..spark_manager import spark_manager
from .sql_engine import format_spark_error

logger = logging.getLogger(__name__)

SUPPORTED_SOURCE_FORMATS = ("csv", "json", "parquet", "txt", "orc", "avro")
SUPPORTED_TABLE_FORMATS = ("delta", "iceberg", "spark")
SUPPORTED_MODES = ("error", "overwrite", "append")

_CATALOG_BY_TABLE_FORMAT = {
    "delta": "spark_catalog",
    "spark": "spark_catalog",
    "iceberg": "local_iceberg",
}
_PROVIDER_BY_TABLE_FORMAT = {
    "delta": "delta",
    "spark": "parquet",
    "iceberg": "iceberg",
}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INVALID_NAME_CHARS = re.compile(r"[^A-Za-z0-9_]+")


class ImportValidationError(ValueError):
    """The import request is malformed or points at an unsupported file."""


class ImportSourceNotFoundError(FileNotFoundError):
    """The source file does not exist on the local filesystem."""


class ImportTableExistsError(RuntimeError):
    """The target table already exists and the import mode is ``error``."""


def _quote(identifier: str) -> str:
    return "`" + identifier.replace("`", "``") + "`"


def _qualified(*parts: str) -> str:
    return ".".join(_quote(part) for part in parts)


def validate_identifier(value: str, label: str) -> str:
    if not value or not _IDENTIFIER.match(value):
        raise ImportValidationError(
            f"{label} must start with a letter or underscore and contain only "
            "letters, digits, and underscores."
        )
    return value


def sanitize_table_name(stem: str) -> str:
    """Derive a safe table identifier from a file name."""

    name = _INVALID_NAME_CHARS.sub("_", stem).strip("_").lower()
    if not name:
        name = "imported_table"
    if name[0].isdigit():
        name = f"t_{name}"
    return name[:120]


def detect_source_format(path: Path, explicit: Optional[str]) -> str:
    if explicit:
        source_format = explicit.lower()
        if source_format not in SUPPORTED_SOURCE_FORMATS:
            raise ImportValidationError(
                "source_format must be one of: " + ", ".join(SUPPORTED_SOURCE_FORMATS)
            )
        return source_format
    candidate = _sample_file(path)
    if candidate is None:
        raise ImportValidationError(
            "Could not detect the file format from the source path. Pass "
            "source_format as csv, json, or parquet."
        )
    suffix = candidate.suffix.lower().lstrip(".")
    if suffix in {"jsonl", "ndjson"}:
        return "json"
    if suffix not in SUPPORTED_SOURCE_FORMATS:
        raise ImportValidationError(
            "Could not detect the file format from its extension. Pass "
            "source_format as csv, json, parquet, txt, orc, or avro."
        )
    return suffix


def _sample_file(path: Path) -> Optional[Path]:
    if path.is_file():
        return path
    if not path.is_dir():
        return path if path.suffix else None
    try:
        for child in sorted(path.iterdir()):
            if child.is_file() and not child.name.startswith("."):
                return child
    except OSError:
        return None
    return None


def resolve_source_path(raw_path: str) -> Path:
    settings = get_settings()
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    else:
        path = path.resolve()
    if not path.exists():
        raise ImportSourceNotFoundError(str(path))
    if not path.is_file() and not path.is_dir():
        raise ImportValidationError(f"Import source is not a file or directory: {path}")
    if path.is_file() and path.stat().st_size == 0:
        raise ImportValidationError(f"Import source is empty: {path}")
    if path.is_dir() and _sample_file(path) is None:
        raise ImportValidationError(f"Import source directory is empty: {path}")
    try:
        path.relative_to(settings.spark_metastore_dir.resolve())
    except ValueError:
        return path
    raise ImportValidationError("The Spark metastore directory cannot be imported.")


def _json_is_multiline_array(path: Path) -> bool:
    candidate = _sample_file(path)
    if candidate is None or not candidate.is_file():
        return False
    try:
        with candidate.open("rb") as handle:
            while True:
                chunk = handle.read(1)
                if not chunk:
                    return False
                if chunk not in b" \t\r\n":
                    return chunk == b"["
    except OSError:
        return False


def _table_exists(spark: SparkSession, full_name: str) -> bool:
    try:
        return bool(spark.catalog.tableExists(full_name))
    except Exception:
        try:
            spark.sql(f"DESCRIBE EXTENDED {full_name}").collect()
            return True
        except Exception:
            return False


def _ensure_namespace(spark: SparkSession, catalog: str, namespace: str) -> None:
    if catalog == "spark_catalog":
        try:
            spark.sql(f"CREATE DATABASE IF NOT EXISTS {_qualified(catalog, namespace)}")
            return
        except Exception:
            spark.sql(f"CREATE DATABASE IF NOT EXISTS {_quote(namespace)}")
            return
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {_qualified(catalog, namespace)}")


def _table_location(spark: SparkSession, full_name: str) -> Optional[str]:
    try:
        rows = spark.sql(f"DESCRIBE EXTENDED {full_name}").collect()
    except Exception:
        return None
    for row in rows:
        values = row.asDict()
        key = str(values.get("col_name") or "").strip().lower()
        if key == "location":
            value = values.get("data_type")
            return str(value) if value else None
    return None


def _read_source(
    spark: SparkSession,
    path: Path,
    source_format: str,
    has_header: bool,
    delimiter: str,
):
    reader = spark.read
    if source_format in ("csv", "txt"):
        reader = (
            reader.option("header", "true" if has_header else "false")
            .option("inferSchema", "true")
            .option("delimiter", delimiter or ",")
        )
        return reader.format("csv").load(path.as_uri())
    if source_format == "json":
        reader = reader.option(
            "multiLine", "true" if _json_is_multiline_array(path) else "false"
        )
    return reader.format(source_format).load(path.as_uri())


def import_file(
    source_path: str,
    table_name: Optional[str] = None,
    namespace: str = "default",
    table_format: str = "delta",
    source_format: Optional[str] = None,
    mode: str = "error",
    has_header: bool = True,
    delimiter: str = ",",
) -> Dict[str, Any]:
    started = time.perf_counter()

    table_format = (table_format or "delta").lower()
    if table_format not in SUPPORTED_TABLE_FORMATS:
        raise ImportValidationError(
            "table_format must be one of: " + ", ".join(SUPPORTED_TABLE_FORMATS)
        )
    if mode not in SUPPORTED_MODES:
        raise ImportValidationError(
            "mode must be one of: " + ", ".join(SUPPORTED_MODES)
        )

    path = resolve_source_path(source_path)
    detected_format = detect_source_format(path, source_format)
    namespace = validate_identifier(namespace or "default", "namespace")
    resolved_table_name = validate_identifier(
        table_name or sanitize_table_name(path.stem), "table_name"
    )
    catalog = _CATALOG_BY_TABLE_FORMAT[table_format]
    full_name = _qualified(catalog, namespace, resolved_table_name)
    using = _PROVIDER_BY_TABLE_FORMAT[table_format]

    with spark_manager.sql_lock:
        spark = spark_manager.get_session()
        _ensure_namespace(spark, catalog, namespace)
        exists = _table_exists(spark, full_name)

        if exists and mode == "error":
            raise ImportTableExistsError(
                f"Table {catalog}.{namespace}.{resolved_table_name} already exists. "
                "Use mode=overwrite or mode=append."
            )

        view_name = f"_lakehouse_import_{uuid.uuid4().hex}"
        try:
            dataframe = _read_source(
                spark, path, detected_format, has_header, delimiter
            )
            dataframe.createOrReplaceTempView(view_name)

            if exists and mode == "append":
                spark.sql(f"INSERT INTO {full_name} SELECT * FROM {_quote(view_name)}")
            elif exists and mode == "overwrite":
                spark.sql(
                    f"CREATE OR REPLACE TABLE {full_name} USING {using} "
                    f"AS SELECT * FROM {_quote(view_name)}"
                )
            else:
                spark.sql(
                    f"CREATE TABLE {full_name} USING {using} "
                    f"AS SELECT * FROM {_quote(view_name)}"
                )
        except Exception as exc:
            message = format_spark_error(exc)
            logger.warning("Import into %s failed: %s", full_name, message)
            raise ImportValidationError(message) from exc
        finally:
            try:
                spark.catalog.dropTempView(view_name)
            except Exception:  # pragma: no cover - best effort cleanup
                pass

        table = spark.table(full_name)
        columns = [
            {"name": field.name, "type": field.dataType.simpleString()}
            for field in table.schema.fields
        ]
        row_count = table.count()
        location = _table_location(spark, full_name)

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "Imported %s (%s) into %s as %s rows=%d",
        path,
        detected_format,
        full_name,
        table_format,
        row_count,
    )
    return {
        "source_path": str(path),
        "source_format": detected_format,
        "table": f"{catalog}.{namespace}.{resolved_table_name}",
        "catalog": catalog,
        "namespace": namespace,
        "table_name": resolved_table_name,
        "table_format": table_format,
        "mode": mode,
        "columns": columns,
        "row_count": row_count,
        "location": location,
        "duration_ms": elapsed_ms,
    }
