from __future__ import annotations

import ast
import io
import logging
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Dict, Optional

from pyspark.sql import DataFrame, SparkSession

from ..config import get_settings
from ..spark_manager import spark_manager
from .cancellation import cancellation_registry
from .sql_engine import format_spark_error
from .sql_utils import (
    ROW_RETURNING_STATEMENTS,
    row_to_jsonable,
    split_sql_statements,
    statement_type,
)

logger = logging.getLogger(__name__)

_MAX_NOTEBOOKS = 32
_NOTEBOOK_LOCK = threading.RLock()
_NOTEBOOK_NAMESPACES: Dict[str, Dict[str, Any]] = {}


class PySparkExecutionError(RuntimeError):
    """Base class for PySpark script execution failures."""


class PySparkTimeoutError(PySparkExecutionError):
    pass


class PySparkCancelledError(PySparkExecutionError):
    pass


class PySparkValidationError(PySparkExecutionError):
    pass


def _dataframe_preview(df: DataFrame, max_rows: int) -> Dict[str, Any]:
    columns = [
        {"name": field.name, "type": field.dataType.simpleString()}
        for field in df.schema.fields
    ]
    limited = df.limit(max_rows + 1)
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


def _repr_result(value: Any) -> str:
    try:
        return repr(value)
    except Exception as exc:  # pragma: no cover
        return f"<unrepresentable: {exc}>"


def _result_type(value: Any) -> Optional[str]:
    try:
        return f"{type(value).__module__}.{type(value).__name__}"
    except Exception:  # pragma: no cover
        return None


_SQL_MAGIC = re.compile(r"^(%%?)sql(?![A-Za-z0-9_])(.*)$", re.IGNORECASE)


def extract_sql_source(script: str) -> Optional[str]:
    """Return the SQL body of a ``%sql``/``%%sql`` cell, or ``None``.

    Only the first non-empty line is inspected, so ordinary Python and other
    IPython magics such as ``%sqlite`` are left untouched. Everything after the
    magic line (and anything on the same line) becomes the SQL script.
    """

    lines = script.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        match = _SQL_MAGIC.match(stripped)
        if match is None:
            return None

        inline = match.group(2).lstrip()
        remainder = "\n".join(lines[index + 1 :])
        # Both line and cell magics accept SQL on the magic line or below it.
        parts = [part for part in (inline, remainder) if part.strip()]
        return "\n".join(parts).strip()
    return None


def _run_sql_statements(
    spark: SparkSession, sql: str, max_rows: int
) -> tuple[Dict[str, Any], Optional[str]]:
    """Execute one or more Spark SQL statements and preview the last result."""

    statements = [
        statement for statement in split_sql_statements(sql) if statement.strip()
    ]
    if not statements:
        raise PySparkValidationError(
            "The cell did not contain an executable SQL statement."
        )

    preview: Dict[str, Any] = {
        "columns": [],
        "rows": [],
        "row_count": 0,
        "truncated": False,
    }
    result_repr: Optional[str] = None
    last_kind = "UNKNOWN"

    for statement in statements:
        last_kind = statement_type(statement)
        try:
            dataframe = spark.sql(statement)
            if last_kind in ROW_RETURNING_STATEMENTS:
                preview = _dataframe_preview(dataframe, max_rows)
                result_repr = (
                    None if preview["row_count"] else "Query returned 0 rows."
                )
            else:
                # DDL/DML/management statements only take effect once the
                # DataFrame is materialised; their result set is empty.
                dataframe.collect()
                preview = {
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "truncated": False,
                }
                result_repr = f"{last_kind} statement executed."
        except PySparkExecutionError:
            raise
        except Exception as exc:
            message = format_spark_error(exc)
            logger.warning(
                "Notebook SQL statement failed (%s): %s", last_kind, message
            )
            raise PySparkExecutionError(message) from exc

    if len(statements) > 1 and result_repr:
        result_repr = f"{len(statements)} statements executed; {result_repr}"

    return preview, result_repr


def _get_notebook_namespace(notebook_id: str) -> Dict[str, Any]:
    with _NOTEBOOK_LOCK:
        namespace = _NOTEBOOK_NAMESPACES.get(notebook_id)
        if namespace is None:
            namespace = {"__name__": "__spark_notebook__"}
            _NOTEBOOK_NAMESPACES[notebook_id] = namespace
            while len(_NOTEBOOK_NAMESPACES) > _MAX_NOTEBOOKS:
                oldest = next(iter(_NOTEBOOK_NAMESPACES))
                if oldest == notebook_id:
                    break
                _NOTEBOOK_NAMESPACES.pop(oldest, None)
        return namespace


def reset_notebook(notebook_id: str) -> Dict[str, Any]:
    with _NOTEBOOK_LOCK:
        existed = _NOTEBOOK_NAMESPACES.pop(notebook_id, None) is not None
    logger.info("Reset notebook kernel %s (existed=%s)", notebook_id, existed)
    return {"notebook_id": notebook_id, "reset": True, "existed": existed}


def read_data_file(path: str) -> DataFrame:
    """Load a data file from the workspace (or an absolute path) as a DataFrame.

    Relative paths are treated as logical paths inside the open workspace
    folder. The reader is chosen from the file extension.
    """

    from .workspace import resolve_data_path

    resolved = resolve_data_path(path)
    spark = spark_manager.get_session()
    suffix = Path(resolved).suffix.lower()

    if suffix in (".csv", ".tsv"):
        separator = "\t" if suffix == ".tsv" else ","
        return (
            spark.read.option("header", "true")
            .option("inferSchema", "true")
            .option("sep", separator)
            .csv(resolved)
        )
    if suffix in (".parquet", ""):
        return spark.read.parquet(resolved)
    if suffix in (".json", ".jsonl"):
        return spark.read.json(resolved)
    if suffix == ".orc":
        return spark.read.orc(resolved)
    if suffix == ".avro":
        return spark.read.format("avro").load(resolved)
    if suffix == ".text":
        return spark.read.text(resolved)
    raise ValueError(
        f"Unsupported data file type '{suffix or resolved}'. "
        "Use CSV, TSV, JSON, Parquet, ORC, Avro, or text."
    )


def read_database(
    connection_id: str, table: str, database: Optional[str] = None
) -> DataFrame:
    """Load a table from a configured database (databases.cfg) over JDBC.

    Credentials stay in the backend configuration and are never written into
    the notebook file.
    """

    from .database_config import get_config_connection

    conn = get_config_connection(connection_id)
    dbtable = table
    if database and "." not in table:
        dbtable = f"{database}.{table}"

    return (
        spark_manager.get_session()
        .read.format("jdbc")
        .option("url", conn.jdbc_url())
        .option("driver", conn.driver_class())
        .option("user", conn.username)
        .option("password", conn.password)
        .option("dbtable", dbtable)
        .load()
    )


def _execute(
    script: str,
    timeout_seconds: Optional[int],
    max_rows: Optional[int],
    namespace: Optional[Dict[str, Any]],
    notebook_mode: bool,
    target: str,
    sql_mode: bool = False,
) -> Dict[str, Any]:
    settings = get_settings()
    timeout = timeout_seconds or settings.query_timeout_seconds
    row_cap = max_rows or settings.max_result_rows
    token = cancellation_registry.begin(target)
    label = "SQL cell" if sql_mode else "PySpark script"

    try:
        with spark_manager.sql_lock:
            spark = spark_manager.get_session()
            job_group = f"lakehouse-pyspark-{uuid.uuid4()}"
            cancelled = threading.Event()

            def request_cancel() -> None:
                cancelled.set()
                try:
                    spark.sparkContext.cancelJobGroup(job_group)
                except Exception:  # pragma: no cover - best effort cancellation
                    pass

            token.add_callback(request_cancel)

            def task() -> Dict[str, Any]:
                if cancelled.is_set() or token.cancelled:
                    raise PySparkCancelledError(
                        f"{label} cancelled before execution started."
                    )
                spark.sparkContext.setJobGroup(
                    job_group,
                    "workbench: sql cell" if sql_mode else "workbench: pyspark script",
                    interruptOnCancel=True,
                )
                if cancelled.is_set() or token.cancelled:
                    spark.sparkContext.cancelJobGroup(job_group)
                    raise PySparkCancelledError(
                        f"{label} cancelled before it started running."
                    )
                try:
                    return _run_script(
                        spark, script, row_cap, namespace, notebook_mode, sql_mode
                    )
                finally:
                    try:
                        spark.sparkContext.clearJobGroup()
                    except Exception:  # pragma: no cover - best effort cleanup
                        pass

            executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="spark-pyspark"
            )
            started = time.perf_counter()
            future = executor.submit(task)
            try:
                try:
                    result = future.result(timeout=timeout)
                except FutureTimeoutError as exc:
                    if token.cancelled:
                        raise PySparkCancelledError(
                            f"{label} cancelled by user."
                        ) from exc
                    cancelled.set()
                    try:
                        spark.sparkContext.cancelJobGroup(job_group)
                    except Exception:  # pragma: no cover - best effort cancellation
                        pass
                    raise PySparkTimeoutError(
                        f"{label} exceeded the {timeout}s execution timeout and was cancelled."
                    ) from exc
                except Exception:
                    if token.cancelled:
                        raise PySparkCancelledError(
                            f"{label} cancelled by user."
                        )
                    raise
                if token.cancelled:
                    raise PySparkCancelledError(
                        f"{label} cancelled by user."
                    )
            finally:
                token.remove_callback(request_cancel)
                executor.shutdown(wait=False, cancel_futures=True)

            result["execution_time_ms"] = round(
                (time.perf_counter() - started) * 1000, 2
            )
            return result
    finally:
        cancellation_registry.finish(token)


def execute_pyspark(
    script: str,
    timeout_seconds: Optional[int] = None,
    max_rows: Optional[int] = None,
    target: str = "pyspark",
) -> Dict[str, Any]:
    """Execute a PySpark script with a fresh namespace."""

    return _execute(
        script,
        timeout_seconds,
        max_rows,
        None,
        notebook_mode=False,
        target=target,
    )


def execute_notebook_cell(
    notebook_id: str,
    script: str,
    timeout_seconds: Optional[int] = None,
    max_rows: Optional[int] = None,
    target: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a notebook cell in a namespace persisted per ``notebook_id``.

    Variables (DataFrames, imports, temp views) stay available to later cells
    so a notebook behaves like a Jupyter kernel. The trailing expression of a
    cell is evaluated and previewed when it yields a DataFrame.
    """

    namespace = _get_notebook_namespace(notebook_id)
    return _execute(
        script,
        timeout_seconds,
        max_rows,
        namespace,
        notebook_mode=True,
        target=target or f"notebook:{notebook_id}",
    )


def execute_notebook_sql_cell(
    notebook_id: str,
    script: str,
    timeout_seconds: Optional[int] = None,
    max_rows: Optional[int] = None,
    target: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a cell as Spark SQL inside the shared backend session.

    The SQL kernel has no per-notebook state of its own; tables and temp views
    live in the Spark session, so later cells see what earlier cells created.
    """

    return _execute(
        script,
        timeout_seconds,
        max_rows,
        None,
        notebook_mode=False,
        target=target or f"notebook:{notebook_id}",
        sql_mode=True,
    )


def _exec_with_trailing_expression(script: str, namespace: Dict[str, Any]) -> None:
    filename = "<pyspark-notebook>"
    tree = ast.parse(script, filename, "exec")
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        head = ast.Module(body=tree.body[:-1], type_ignores=[])
        last = ast.Expression(tree.body[-1].value)
        if head.body:
            exec(compile(head, filename, "exec"), namespace)  # noqa: S102
        value = eval(compile(last, filename, "eval"), namespace)  # noqa: S307
        namespace["__result__"] = value
    else:
        exec(compile(tree, filename, "exec"), namespace)  # noqa: S102


def _run_script(
    spark: SparkSession,
    script: str,
    max_rows: int,
    namespace: Optional[Dict[str, Any]] = None,
    notebook_mode: bool = False,
    sql_mode: bool = False,
) -> Dict[str, Any]:
    if namespace is None:
        namespace = {"spark": spark, "__name__": "__spark_workspace__"}
    else:
        namespace["spark"] = spark
        namespace.setdefault("__name__", "__spark_notebook__")
        namespace.pop("__result__", None)
        if notebook_mode:
            namespace.setdefault("read_data_file", read_data_file)
            namespace.setdefault("read_database", read_database)

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    sql_source = extract_sql_source(script)
    if sql_mode and sql_source is None:
        # A SQL-kernel cell may omit the magic and contain SQL directly.
        sql_source = script
    if sql_source is not None:
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                preview, result_repr = _run_sql_statements(
                    spark, sql_source, max_rows
                )
        except PySparkExecutionError:
            raise
        except Exception as exc:
            message = format_spark_error(exc)
            stderr_capture.write("\n" + traceback.format_exc())
            logger.warning("SQL cell failed: %s", message)
            raise PySparkExecutionError(message) from exc

        return {
            "script": script,
            "engine": "sql",
            "columns": preview["columns"],
            "rows": preview["rows"],
            "row_count": preview["row_count"],
            "execution_time_ms": 0.0,
            "truncated": preview["truncated"],
            "max_rows": max_rows,
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
            "result_type": "spark.sql.DataFrame",
            "result_repr": result_repr,
        }

    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            if notebook_mode:
                _exec_with_trailing_expression(script, namespace)
            else:
                compiled = compile(script, "<pyspark-script>", "exec")
                exec(compiled, namespace)  # noqa: S102 - intentional local script execution
    except Exception as exc:
        message = format_spark_error(exc)
        stderr_capture.write("\n" + traceback.format_exc())
        logger.warning("PySpark script failed: %s", message)
        raise PySparkExecutionError(message) from exc

    result_value = namespace.get("__result__", None)
    if result_value is None and not notebook_mode:
        # Try to use the last assigned variable as a convenience.
        local_vars = {
            key: value
            for key, value in namespace.items()
            if not key.startswith("__") and key != "spark"
        }
        if local_vars:
            result_value = next(reversed(local_vars.values()))

    preview: Dict[str, Any] = {
        "columns": [],
        "rows": [],
        "row_count": 0,
        "truncated": False,
    }
    result_type: Optional[str] = None
    result_repr: Optional[str] = None

    if isinstance(result_value, DataFrame):
        preview = _dataframe_preview(result_value, max_rows)
        result_type = _result_type(result_value)
        result_repr = f"DataFrame[{', '.join(f.name for f in result_value.schema.fields)}]"
    elif result_value is not None:
        result_type = _result_type(result_value)
        result_repr = _repr_result(result_value)

    return {
        "script": script,
        "engine": "pyspark",
        "columns": preview["columns"],
        "rows": preview["rows"],
        "row_count": preview["row_count"],
        "execution_time_ms": 0.0,
        "truncated": preview["truncated"],
        "max_rows": max_rows,
        "stdout": stdout_capture.getvalue(),
        "stderr": stderr_capture.getvalue(),
        "result_type": result_type,
        "result_repr": result_repr,
    }
