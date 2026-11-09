from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from pyspark.sql import SparkSession

from ..spark_manager import spark_manager
from .database_connections import resolve_connection
from .importer import (
    ImportTableExistsError,
    ImportValidationError,
    _ensure_namespace,
    _quote,
    _qualified,
    _table_exists,
    _table_location,
)
from .sql_engine import format_spark_error

logger = logging.getLogger(__name__)

SUPPORTED_TABLE_FORMATS = ("delta", "iceberg", "spark")
SUPPORTED_MODES = ("error", "overwrite", "append")
_PROVIDER_BY_TABLE_FORMAT = {
    "delta": "delta",
    "spark": "parquet",
    "iceberg": "iceberg",
}
_CATALOG_BY_TABLE_FORMAT = {
    "delta": "spark_catalog",
    "spark": "spark_catalog",
    "iceberg": "local_iceberg",
}


class JdbcImportError(RuntimeError):
    pass


def _quote_identifier(value: str) -> str:
    # Be conservative: only allow simple identifiers.
    if not value or not value.replace("_", "").replace(".", "").isalnum():
        raise ImportValidationError(f"Invalid identifier: {value}")
    return value


def _build_dbtable(
    table: Optional[str], query: Optional[str], dialect: str
) -> str:
    if query:
        stripped = query.strip()
        if stripped.rstrip(";").upper().startswith("SELECT "):
            return f"({stripped.rstrip(';')}) AS lakehouse_import_query"
        raise ImportValidationError(
            "The custom query must be a single SELECT statement."
        )
    if not table:
        raise ImportValidationError("Either table or query is required.")
    return _quote_identifier(table)


def import_from_database(
    connection_id: str,
    table: Optional[str] = None,
    query: Optional[str] = None,
    namespace: str = "default",
    table_name: Optional[str] = None,
    table_format: str = "delta",
    mode: str = "error",
    max_rows: Optional[int] = None,
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

    conn = resolve_connection(connection_id)
    dbtable = _build_dbtable(table, query, conn.dialect)
    resolved_table_name = (
        table_name or table or "imported_query"
    ).rsplit(".", 1)[-1]
    resolved_table_name = "".join(
        c if c.isalnum() or c == "_" else "_" for c in resolved_table_name
    ).strip("_")[:120]
    if not resolved_table_name or resolved_table_name[0].isdigit():
        resolved_table_name = "imported_query"

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

        view_name = f"_lakehouse_jdbc_import_{uuid.uuid4().hex}"
        try:
            reader = (
                spark.read.format("jdbc")
                .option("url", conn.jdbc_url())
                .option("driver", conn.driver_class())
                .option("user", conn.username)
                .option("password", conn.password)
                .option("dbtable", dbtable)
            )
            if max_rows:
                reader = reader.option("fetchsize", str(min(max_rows, 10_000)))
            dataframe = reader.load()

            if max_rows:
                dataframe = dataframe.limit(max_rows)
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
            logger.warning("JDBC import into %s failed: %s", full_name, message)
            raise JdbcImportError(message) from exc
        finally:
            try:
                spark.catalog.dropTempView(view_name)
            except Exception:  # pragma: no cover - best effort cleanup
                pass

        result_table = spark.table(full_name)
        columns = [
            {"name": field.name, "type": field.dataType.simpleString()}
            for field in result_table.schema.fields
        ]
        row_count = result_table.count()
        location = _table_location(spark, full_name)

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "Imported JDBC from %s (%s) into %s as %s rows=%d",
        connection_id,
        dbtable,
        full_name,
        table_format,
        row_count,
    )
    return {
        "connection_id": connection_id,
        "source": dbtable,
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


def preview_database_table(
    connection_id: str,
    table: Optional[str] = None,
    query: Optional[str] = None,
    max_rows: int = 100,
) -> Dict[str, Any]:
    conn = resolve_connection(connection_id)
    dbtable = _build_dbtable(table, query, conn.dialect)

    with spark_manager.sql_lock:
        spark = spark_manager.get_session()
        try:
            df = (
                spark.read.format("jdbc")
                .option("url", conn.jdbc_url())
                .option("driver", conn.driver_class())
                .option("user", conn.username)
                .option("password", conn.password)
                .option("dbtable", dbtable)
                .load()
                .limit(max_rows)
            )
            columns = [
                {"name": field.name, "type": field.dataType.simpleString()}
                for field in df.schema.fields
            ]
            rows = [row.asDict(recursive=True) for row in df.collect()]
            return {
                "connection_id": connection_id,
                "source": dbtable,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
            }
        except Exception as exc:
            message = format_spark_error(exc)
            logger.warning("JDBC preview failed for %s: %s", connection_id, message)
            raise JdbcImportError(message) from exc
