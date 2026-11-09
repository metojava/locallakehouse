from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Dict, List, Optional

from pyspark.sql import DataFrame, SparkSession

from ..config import get_settings
from ..spark_manager import SparkUnavailableError, spark_manager
from .sql_utils import (
    ROW_RETURNING_STATEMENTS,
    classify_engine,
    row_to_jsonable,
    split_sql_statements,
    statement_type,
)

logger = logging.getLogger(__name__)

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


class QueryExecutionError(RuntimeError):
    """Base class for SQL execution failures surfaced by the REST API."""


class InvalidSqlError(QueryExecutionError):
    pass


class QueryTimeoutError(QueryExecutionError):
    pass


def current_catalog(spark: SparkSession) -> Optional[str]:
    try:
        return spark.catalog.currentCatalog()
    except Exception:
        return None


def execute_sql(
    sql: str,
    max_rows: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    settings = get_settings()
    statements = split_sql_statements(sql)
    if not statements:
        raise InvalidSqlError("The request did not contain an executable SQL statement.")

    row_cap = max_rows or settings.max_result_rows
    timeout = timeout_seconds or settings.query_timeout_seconds

    with spark_manager.sql_lock:
        spark = spark_manager.get_session()
        active_catalog = current_catalog(spark)
        executions: List[Dict[str, Any]] = []
        last_result: Optional[Dict[str, Any]] = None

        for statement in statements:
            engine = classify_engine(statement, active_catalog)
            kind = statement_type(statement)
            started = time.perf_counter()
            try:
                result = _run_statement(spark, statement, kind, row_cap, timeout)
            except QueryTimeoutError:
                raise
            except SparkUnavailableError:
                raise
            except Exception as exc:
                message = format_spark_error(exc)
                logger.warning(
                    "SQL statement failed (engine=%s, type=%s): %s",
                    engine,
                    kind,
                    message.splitlines()[0] if message else exc,
                )
                raise QueryExecutionError(message) from exc

            last_result = result
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            executions.append(
                {
                    "statement": statement,
                    "engine": engine,
                    "statement_type": kind,
                    "columns": result["columns"],
                    "row_count": result["row_count"],
                    "execution_time_ms": elapsed_ms,
                    "truncated": result["truncated"],
                    "max_rows": row_cap,
                }
            )

            if kind in {"USE", "SET"}:
                active_catalog = current_catalog(spark)

        assert last_result is not None
        last = executions[-1]
        return {
            "sql": sql,
            "engine": last["engine"],
            "statement_type": last["statement_type"],
            "columns": last["columns"],
            "rows": last_result["rows"],
            "row_count": last["row_count"],
            "execution_time_ms": round(
                sum(execution["execution_time_ms"] for execution in executions), 2
            ),
            "truncated": last["truncated"],
            "max_rows": row_cap,
            "statements": executions,
        }


def _run_statement(
    spark: SparkSession,
    statement: str,
    kind: str,
    max_rows: int,
    timeout_seconds: int,
) -> Dict[str, Any]:
    job_group = f"lakehouse-{uuid.uuid4()}"
    cancelled = threading.Event()

    def task() -> Dict[str, Any]:
        if cancelled.is_set():
            raise QueryTimeoutError("Query cancelled before execution started.")
        spark.sparkContext.setJobGroup(
            job_group,
            f"workbench: {statement[:120]}",
            interruptOnCancel=True,
        )
        if cancelled.is_set():
            spark.sparkContext.cancelJobGroup(job_group)
            raise QueryTimeoutError("Query cancelled before it started running.")
        try:
            return _collect_result(spark, statement, kind, max_rows)
        finally:
            try:
                spark.sparkContext.clearJobGroup()
            except Exception:  # pragma: no cover - best effort cleanup
                pass

    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="spark-sql")
    future = executor.submit(task)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError as exc:
        cancelled.set()
        try:
            spark.sparkContext.cancelJobGroup(job_group)
        except Exception:  # pragma: no cover - best effort cancellation
            pass
        raise QueryTimeoutError(
            f"Query exceeded the {timeout_seconds}s execution timeout and was cancelled."
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _collect_result(
    spark: SparkSession, statement: str, kind: str, max_rows: int
) -> Dict[str, Any]:
    dataframe: DataFrame = spark.sql(statement)
    columns = [
        {"name": field.name, "type": field.dataType.simpleString()}
        for field in dataframe.schema.fields
    ]

    if kind in ROW_RETURNING_STATEMENTS:
        limited = dataframe.limit(max_rows + 1)
        raw_rows = limited.collect()
        truncated = len(raw_rows) > max_rows
        if truncated:
            raw_rows = raw_rows[:max_rows]
        rows = [row_to_jsonable(row.asDict(recursive=True)) for row in raw_rows]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }

    # DDL / DML / management commands must be materialised to trigger the
    # action; their result sets are empty.
    dataframe.collect()
    return {
        "columns": columns,
        "rows": [],
        "row_count": 0,
        "truncated": False,
    }


def format_spark_error(exc: BaseException) -> str:
    text = _ANSI_ESCAPE.sub("", str(exc)).strip()
    if not text:
        return exc.__class__.__name__
    lines = [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("at ")
    ]
    for index, line in enumerate(lines):
        if "Exception:" in line or "Error:" in line:
            return "\n".join(lines[index : index + 10])[:4_000]
    return "\n".join(lines[:10])[:4_000]
