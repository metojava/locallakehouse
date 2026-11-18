from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from .. import __version__
from ..config import get_settings
from ..models.schemas import (
    ConfigDatabaseConnectionResponse,
    ConfigDatabaseListResponse,
    ConfigDatabaseTablesResponse,
    DatabaseConnectionRequest,
    DatabaseConnectionResponse,
    DatabasePreviewRequest,
    DatabasePreviewResponse,
    ExecutePySparkRequest,
    ExecutePySparkResponse,
    ExecuteSqlResponse,
    HealthResponse,
    ImportDatabaseRequest,
    ImportDatabaseResponse,
    ImportFileRequest,
    ImportFileResponse,
    CancelRequest,
    CreateNotebookRequest,
    FilePickResponse,
    JvmRunRequest,
    JvmRunResponse,
    KernelInstallResponse,
    KernelListResponse,
    NotebookDocumentResponse,
    NotebookExecuteRequest,
    NotebookResetRequest,
    SaveTextFileRequest,
    SaveTextFileResponse,
    SparkBrowseResponse,
    SparkConfigResponse,
    SparkDownloadRequest,
    SparkDownloadStatus,
    SparkHomeRequest,
    SqlRequest,
    StorageFileResponse,
    StorageResponse,
    TablesResponse,
    TextFileResponse,
    WorkspaceResponse,
    WorkspaceRootRequest,
)
from ..services.cancellation import cancellation_registry
from ..services.catalog import list_catalogs
from ..services.folder_picker import FolderPickerError, pick_file
from ..services.jvm_runner import JvmRunCancelled, JvmRunError, run_jvm_program
from ..services.kernel_service import (
    KernelCancelledError,
    KernelError,
    install_java_kernel,
    install_scala_kernel,
    is_builtin,
    is_sql_kernel,
    kernel_service,
    list_kernels,
)
from ..services.database_connections import (
    ConnectionNotFoundError,
    ConnectionValidationError,
    create_connection,
    delete_connection,
    get_connection,
    list_connections,
    test_connection,
    update_connection,
)
from ..services.database_config import (
    list_config_databases,
    load_config_connections,
    list_config_tables,
)
from ..services.importer import (
    ImportSourceNotFoundError,
    ImportTableExistsError,
    ImportValidationError,
    import_file,
)
from ..services.jdbc_importer import (
    JdbcImportError,
    import_from_database,
    preview_database_table,
)
from ..services.pyspark_engine import (
    PySparkCancelledError,
    PySparkExecutionError,
    PySparkTimeoutError,
    PySparkValidationError,
    execute_notebook_cell,
    execute_notebook_sql_cell,
    execute_pyspark,
    reset_notebook,
)
from ..services.spark_setup import (
    SparkSetupError,
    browse_for_spark_home,
    clear_spark_home,
    get_download_status,
    get_spark_config,
    set_spark_home,
    start_download,
)
from ..services.sql_engine import (
    InvalidSqlError,
    QueryCancelledError,
    QueryExecutionError,
    QueryTimeoutError,
    execute_sql,
    format_spark_error,
)
from ..services.storage import (
    StorageNotFoundError,
    StoragePathError,
    explore_storage,
    read_storage_file,
    resolve_storage_file,
)
from ..services.workspace import (
    WorkspaceError,
    WorkspaceNotFoundError,
    WorkspacePathError,
    close_workspace,
    create_notebook,
    describe_workspace,
    load_notebook,
    open_workspace,
    pick_workspace,
    read_text_file,
    write_text_file,
)
from ..spark_manager import SparkUnavailableError, spark_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    initialized = spark_manager.is_started

    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=__version__,
        warehouse=str(settings.warehouse_dir.resolve()),
        spark_initialized=initialized,
        spark_version=spark_manager.version if initialized else None,
        time=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/spark/config", response_model=SparkConfigResponse)
def spark_config() -> SparkConfigResponse:
    return SparkConfigResponse(**get_spark_config())


@router.post("/spark/home", response_model=SparkConfigResponse)
def configure_spark_home(payload: SparkHomeRequest) -> SparkConfigResponse:
    try:
        result = set_spark_home(payload.path)
    except SparkSetupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected Spark home configuration failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SparkConfigResponse(**result)


@router.delete("/spark/home", response_model=SparkConfigResponse)
def reset_spark_home() -> SparkConfigResponse:
    try:
        result = clear_spark_home()
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected Spark home reset failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SparkConfigResponse(**result)


@router.post("/spark/browse", response_model=SparkBrowseResponse)
def browse_spark_home() -> SparkBrowseResponse:
    try:
        path = browse_for_spark_home()
    except SparkSetupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected Spark folder picker failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SparkBrowseResponse(path=path, cancelled=path is None)


@router.post("/spark/download", response_model=SparkDownloadStatus)
def download_spark(payload: SparkDownloadRequest) -> SparkDownloadStatus:
    try:
        result = start_download(payload.version, payload.destination)
    except SparkSetupError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected Spark download failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SparkDownloadStatus(**result)


@router.get("/spark/download/status", response_model=SparkDownloadStatus)
def spark_download_status() -> SparkDownloadStatus:
    return SparkDownloadStatus(**get_download_status())


@router.post("/execute-sql", response_model=ExecuteSqlResponse)
def run_sql(payload: SqlRequest) -> ExecuteSqlResponse:
    try:
        result = execute_sql(
            payload.sql,
            max_rows=payload.max_rows,
            timeout_seconds=payload.timeout_seconds,
            target="sql",
        )
    except QueryCancelledError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except QueryTimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    except InvalidSqlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparkUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except QueryExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected SQL execution failure")
        raise HTTPException(
            status_code=500, detail=format_spark_error(exc)
        ) from exc

    return ExecuteSqlResponse(**result)


@router.post("/execute-pyspark", response_model=ExecutePySparkResponse)
def run_pyspark(payload: ExecutePySparkRequest) -> ExecutePySparkResponse:
    try:
        result = execute_pyspark(
            payload.script,
            timeout_seconds=payload.timeout_seconds,
            target="pyspark",
        )
    except PySparkCancelledError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PySparkTimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    except PySparkValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparkUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PySparkExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected PySpark execution failure")
        raise HTTPException(
            status_code=500, detail=format_spark_error(exc)
        ) from exc

    return ExecutePySparkResponse(**result)


@router.post("/import-file", response_model=ImportFileResponse)
def import_data_file(payload: ImportFileRequest) -> ImportFileResponse:
    try:
        result = import_file(
            source_path=payload.path,
            table_name=payload.table_name,
            namespace=payload.namespace,
            table_format=payload.table_format,
            source_format=payload.source_format,
            mode=payload.mode,
            has_header=payload.has_header,
            delimiter=payload.delimiter,
        )
    except ImportSourceNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Import source not found: {exc}"
        ) from exc
    except ImportTableExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ImportValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparkUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected file import failure")
        raise HTTPException(
            status_code=500, detail=format_spark_error(exc)
        ) from exc

    return ImportFileResponse(**result)


@router.get("/tables", response_model=TablesResponse)
def tables(
    include_details: bool = Query(
        default=True,
        description="Run DESCRIBE EXTENDED for each table to resolve format and location.",
    )
) -> TablesResponse:
    try:
        result = list_catalogs(include_details=include_details)
    except SparkUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected catalog listing failure")
        raise HTTPException(
            status_code=500, detail=format_spark_error(exc)
        ) from exc

    return TablesResponse(**result)


@router.get("/storage-explorer", response_model=StorageResponse)
def storage_explorer(
    path: str = Query(
        default="",
        max_length=2_048,
        description="Directory path relative to the lakehouse warehouse root.",
    ),
    depth: Optional[int] = Query(default=None, ge=0, le=12),
    max_entries: Optional[int] = Query(default=None, ge=1, le=50_000),
) -> StorageResponse:
    try:
        result = explore_storage(
            relative_path=path, depth=depth, max_entries=max_entries
        )
    except StorageNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Warehouse path not found: {exc}"
        ) from exc
    except StoragePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Could not read the warehouse: {exc}"
        ) from exc

    return StorageResponse(**result)


@router.get("/storage-explorer/file", response_model=StorageFileResponse)
def storage_file(
    path: str = Query(
        ...,
        min_length=1,
        max_length=2_048,
        description="File path relative to the lakehouse warehouse root.",
    ),
) -> StorageFileResponse:
    try:
        result = read_storage_file(path)
    except StorageNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Warehouse file not found: {exc}"
        ) from exc
    except StoragePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Could not read the warehouse file: {exc}"
        ) from exc

    return StorageFileResponse(**result)


@router.get("/storage-explorer/download")
def storage_download(
    path: str = Query(
        ...,
        min_length=1,
        max_length=2_048,
        description="File path relative to the lakehouse warehouse root.",
    ),
) -> FileResponse:
    try:
        target, _ = resolve_storage_file(path)
    except StorageNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Warehouse file not found: {exc}"
        ) from exc
    except StoragePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(
        path=target,
        media_type="application/octet-stream",
        filename=target.name,
    )


@router.get("/connections", response_model=List[DatabaseConnectionResponse])
def list_database_connections() -> List[DatabaseConnectionResponse]:
    return [conn.to_public_dict() for conn in list_connections()]


@router.post("/connections", response_model=DatabaseConnectionResponse)
def create_database_connection(
    payload: DatabaseConnectionRequest,
) -> DatabaseConnectionResponse:
    try:
        conn = create_connection(
            name=payload.name,
            dialect=payload.dialect,
            host=payload.host,
            port=payload.port,
            database=payload.database,
            username=payload.username,
            password=payload.password,
            properties=payload.properties,
            connection_id=payload.id,
        )
    except ConnectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected connection creation failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return conn.to_public_dict()


@router.put("/connections/{connection_id}", response_model=DatabaseConnectionResponse)
def update_database_connection(
    connection_id: str, payload: DatabaseConnectionRequest
) -> DatabaseConnectionResponse:
    try:
        conn = update_connection(
            connection_id=connection_id,
            name=payload.name,
            dialect=payload.dialect,
            host=payload.host,
            port=payload.port,
            database=payload.database,
            username=payload.username,
            password=payload.password,
            properties=payload.properties,
        )
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConnectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected connection update failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return conn.to_public_dict()


@router.delete("/connections/{connection_id}")
def delete_database_connection(connection_id: str) -> dict:
    try:
        delete_connection(connection_id)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected connection deletion failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"deleted": connection_id}


@router.post("/connections/{connection_id}/test")
def test_database_connection(connection_id: str) -> dict:
    try:
        result = test_connection(connection_id)
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConnectionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected connection test failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@router.post("/connections/{connection_id}/preview", response_model=DatabasePreviewResponse)
def preview_database(
    connection_id: str, payload: DatabasePreviewRequest
) -> DatabasePreviewResponse:
    try:
        result = preview_database_table(
            connection_id=connection_id,
            table=payload.table,
            query=payload.query,
            max_rows=payload.max_rows,
        )
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except JdbcImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparkUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected database preview failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return DatabasePreviewResponse(**result)


@router.post("/import-database", response_model=ImportDatabaseResponse)
def import_database_table(payload: ImportDatabaseRequest) -> ImportDatabaseResponse:
    try:
        result = import_from_database(
            connection_id=payload.connection_id,
            table=payload.table,
            query=payload.query,
            namespace=payload.namespace,
            table_name=payload.table_name,
            table_format=payload.table_format,
            mode=payload.mode,
            max_rows=payload.max_rows,
        )
    except ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportTableExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ImportValidationError, JdbcImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparkUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected database import failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ImportDatabaseResponse(**result)


@router.get("/database-config/connections", response_model=List[ConfigDatabaseConnectionResponse])
def list_config_database_connections() -> List[ConfigDatabaseConnectionResponse]:
    return [conn.to_public_dict() for conn in load_config_connections()]


@router.get("/database-config/connections/{connection_id}/databases", response_model=ConfigDatabaseListResponse)
def list_config_database_schemas(connection_id: str) -> ConfigDatabaseListResponse:
    try:
        result = list_config_databases(connection_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparkUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected database config schemas failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ConfigDatabaseListResponse(**result)


@router.get("/database-config/connections/{connection_id}/tables", response_model=ConfigDatabaseTablesResponse)
def list_config_database_tables(
    connection_id: str,
    database: Optional[str] = Query(default=None, max_length=128),
) -> ConfigDatabaseTablesResponse:
    try:
        tables = list_config_tables(connection_id, database=database)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparkUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected database config tables failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ConfigDatabaseTablesResponse(
        connection_id=connection_id,
        tables=tables,
    )


@router.get("/kernels", response_model=KernelListResponse)
def list_notebook_kernels() -> KernelListResponse:
    return KernelListResponse(**list_kernels())


@router.post("/kernels/java/install", response_model=KernelInstallResponse)
def install_java_notebook_kernel() -> KernelInstallResponse:
    try:
        result = install_java_kernel()
    except KernelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except JvmRunError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected Java kernel install failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return KernelInstallResponse(**result)


@router.post("/kernels/scala/install", response_model=KernelInstallResponse)
def install_scala_notebook_kernel() -> KernelInstallResponse:
    try:
        result = install_scala_kernel()
    except KernelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except JvmRunError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected Scala kernel install failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return KernelInstallResponse(**result)


@router.post("/notebook/execute", response_model=ExecutePySparkResponse)
def run_notebook_cell(payload: NotebookExecuteRequest) -> ExecutePySparkResponse:
    target = f"notebook:{payload.notebook_id}"
    if not is_builtin(payload.kernel_name):
        try:
            result = kernel_service.execute(
                payload.notebook_id,
                payload.kernel_name or "",
                payload.script,
                timeout_seconds=payload.timeout_seconds,
                target=target,
            )
        except KernelCancelledError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KernelError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - safety net
            logger.exception("Unexpected kernel cell failure")
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return ExecutePySparkResponse(**result)

    try:
        if is_sql_kernel(payload.kernel_name):
            result = execute_notebook_sql_cell(
                payload.notebook_id,
                payload.script,
                timeout_seconds=payload.timeout_seconds,
                target=target,
            )
        else:
            result = execute_notebook_cell(
                payload.notebook_id,
                payload.script,
                timeout_seconds=payload.timeout_seconds,
                target=target,
            )
    except PySparkCancelledError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PySparkTimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    except PySparkValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SparkUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PySparkExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected notebook cell failure")
        raise HTTPException(
            status_code=500, detail=format_spark_error(exc)
        ) from exc

    return ExecutePySparkResponse(**result)


@router.post("/notebook/reset")
def reset_notebook_kernel(payload: NotebookResetRequest) -> dict:
    result = reset_notebook(payload.notebook_id)
    result["jupyter_kernels_stopped"] = kernel_service.reset(payload.notebook_id)
    return result


@router.post("/execute-jvm", response_model=JvmRunResponse)
def execute_jvm(payload: JvmRunRequest) -> JvmRunResponse:
    try:
        result = run_jvm_program(
            payload.language,
            payload.source,
            payload.timeout_seconds,
            target=payload.language,
        )
    except JvmRunCancelled as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except JvmRunError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected JVM run failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return JvmRunResponse(**result)


@router.post("/cancel")
def cancel_execution(payload: CancelRequest) -> dict:
    """Cancel the latest command registered for an editor target."""

    cancelled = cancellation_registry.cancel(payload.target)
    logger.info("Cancel requested for %s (cancelled=%s)", payload.target, cancelled)
    return {"cancelled": cancelled, "target": payload.target}


@router.post("/files/pick", response_model=FilePickResponse)
def pick_data_file() -> FilePickResponse:
    try:
        selected = pick_file("Select a data file")
    except FolderPickerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected file picker failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FilePickResponse(path=selected, cancelled=selected is None)


@router.get("/workspace", response_model=WorkspaceResponse)
def workspace_info() -> WorkspaceResponse:
    return WorkspaceResponse(**describe_workspace())


@router.post("/workspace/open", response_model=WorkspaceResponse)
def open_workspace_picker() -> WorkspaceResponse:
    try:
        result = pick_workspace()
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected workspace picker failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return WorkspaceResponse(**result)


@router.post("/workspace/root", response_model=WorkspaceResponse)
def set_workspace_root(payload: WorkspaceRootRequest) -> WorkspaceResponse:
    try:
        result = open_workspace(payload.path)
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected workspace open failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return WorkspaceResponse(**result)


@router.delete("/workspace/root", response_model=WorkspaceResponse)
def clear_workspace_root() -> WorkspaceResponse:
    return WorkspaceResponse(**close_workspace())


@router.get("/workspace/file", response_model=TextFileResponse)
def workspace_read_file(
    path: str = Query(..., min_length=1, max_length=4_096)
) -> TextFileResponse:
    try:
        result = read_text_file(path)
    except WorkspacePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected workspace read failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return TextFileResponse(**result)


@router.put("/workspace/file", response_model=SaveTextFileResponse)
def workspace_write_file(payload: SaveTextFileRequest) -> SaveTextFileResponse:
    try:
        result = write_text_file(payload.path, payload.content)
    except WorkspacePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected workspace save failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SaveTextFileResponse(**result)


@router.get("/workspace/notebook", response_model=NotebookDocumentResponse)
def workspace_read_notebook(
    path: str = Query(..., min_length=1, max_length=4_096)
) -> NotebookDocumentResponse:
    try:
        result = load_notebook(path)
    except WorkspacePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected notebook load failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return NotebookDocumentResponse(**result)


@router.post(
    "/workspace/notebook",
    response_model=NotebookDocumentResponse,
    status_code=201,
)
def workspace_create_notebook(
    payload: CreateNotebookRequest,
) -> NotebookDocumentResponse:
    try:
        result = create_notebook(payload.path)
    except WorkspacePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected notebook creation failure")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return NotebookDocumentResponse(**result)
