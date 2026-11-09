from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pyspark.sql import Row, SparkSession

from ..spark_manager import spark_manager

logger = logging.getLogger(__name__)

CATALOGS = (
    {"name": "delta", "catalog": "spark_catalog", "engine": "delta"},
    {"name": "local_iceberg", "catalog": "local_iceberg", "engine": "iceberg"},
)


def _quote(identifier: str) -> str:
    return "`" + identifier.replace("`", "``") + "`"


def _qualified(*parts: str) -> str:
    return ".".join(_quote(part) for part in parts)


def _show_namespaces(spark: SparkSession, catalog_name: str) -> List[Row]:
    try:
        return spark.sql(f"SHOW NAMESPACES IN {_quote(catalog_name)}").collect()
    except Exception:
        if catalog_name != "spark_catalog":
            raise
        # Some session-catalog versions only expose the unqualified form.
        return spark.sql("SHOW NAMESPACES").collect()


def _show_tables(
    spark: SparkSession, catalog_name: str, namespace: str
) -> List[Row]:
    try:
        return spark.sql(
            f"SHOW TABLES IN {_qualified(catalog_name, namespace)}"
        ).collect()
    except Exception:
        if catalog_name != "spark_catalog":
            raise
        return spark.sql(f"SHOW TABLES IN {_quote(namespace)}").collect()


def _first_present(row: Row, candidates: List[str], fallback_index: int = 0) -> Any:
    for name in candidates:
        if name in row.asDict():
            return row[name]
    return row[fallback_index]


def list_catalogs(include_details: bool = True) -> Dict[str, Any]:
    with spark_manager.sql_lock:
        spark = spark_manager.get_session()
        catalogs = [
            _describe_catalog(spark, descriptor, include_details)
            for descriptor in CATALOGS
        ]

    return {
        "catalogs": catalogs,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _describe_catalog(
    spark: SparkSession, descriptor: Dict[str, str], include_details: bool
) -> Dict[str, Any]:
    catalog_name = descriptor["catalog"]
    result: Dict[str, Any] = {
        "name": descriptor["name"],
        "catalog": catalog_name,
        "engine": descriptor["engine"],
        "namespaces": [],
        "error": None,
    }
    try:
        namespace_rows = _show_namespaces(spark, catalog_name)
    except Exception as exc:
        message = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
        logger.warning("Could not list namespaces for %s: %s", catalog_name, message)
        result["error"] = message
        return result

    for namespace_row in namespace_rows:
        namespace = str(
            _first_present(namespace_row, ["namespace", "databaseName", "database"])
        )
        namespace_result: Dict[str, Any] = {
            "name": namespace,
            "tables": [],
            "error": None,
        }
        try:
            table_rows = _show_tables(spark, catalog_name, namespace)
        except Exception as exc:
            namespace_result["error"] = (
                str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            )
            result["namespaces"].append(namespace_result)
            continue

        for table_row in table_rows:
            table_name = str(_first_present(table_row, ["tableName", "table"]))
            is_temporary = bool(
                table_row["isTemporary"] if "isTemporary" in table_row.asDict() else False
            )
            full_name = ".".join((catalog_name, namespace, table_name))
            details: Dict[str, Optional[str]] = {"format": None, "location": None}
            if include_details:
                details = _describe_table(spark, full_name)
            namespace_result["tables"].append(
                {
                    "name": table_name,
                    "full_name": full_name,
                    "is_temporary": is_temporary,
                    "format": details.get("format") or descriptor["engine"],
                    "location": details.get("location"),
                }
            )

        namespace_result["tables"].sort(key=lambda item: item["name"].lower())
        result["namespaces"].append(namespace_result)

    result["namespaces"].sort(key=lambda item: item["name"].lower())
    return result


def _describe_table(spark: SparkSession, full_name: str) -> Dict[str, Optional[str]]:
    details: Dict[str, Optional[str]] = {"format": None, "location": None}
    try:
        rows = spark.sql(f"DESCRIBE EXTENDED {full_name}").collect()
    except Exception as exc:
        logger.debug("DESCRIBE EXTENDED failed for %s: %s", full_name, exc)
        return details

    for row in rows:
        values = row.asDict()
        key = str(values.get("col_name") or "").strip().lower()
        value = values.get("data_type")
        if not key:
            continue
        if key == "provider":
            details["format"] = str(value).lower() if value else None
        elif key == "location":
            details["location"] = str(value) if value else None
    return details
