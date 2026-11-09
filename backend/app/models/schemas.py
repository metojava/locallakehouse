from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class SqlRequest(BaseModel):
    sql: str = Field(..., min_length=1, max_length=200_000)
    max_rows: Optional[int] = Field(default=None, ge=1, le=100_000)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=3_600)


class ColumnInfo(BaseModel):
    name: str
    type: str


class StatementExecution(BaseModel):
    statement: str
    engine: str
    statement_type: str
    columns: List[ColumnInfo]
    row_count: int
    execution_time_ms: float
    truncated: bool
    max_rows: int


class ExecuteSqlResponse(BaseModel):
    sql: str
    engine: str
    statement_type: str
    columns: List[ColumnInfo]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool
    max_rows: int
    statements: List[StatementExecution]


class ImportFileRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=4_096)
    table_name: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Defaults to a sanitized version of the source file name.",
    )
    namespace: str = Field(default="default", max_length=120)
    table_format: Literal["delta", "iceberg", "spark"] = "delta"
    source_format: Optional[Literal["csv", "json", "parquet", "txt", "orc", "avro"]] = None
    mode: Literal["error", "overwrite", "append"] = "error"
    has_header: bool = True
    delimiter: str = Field(default=",", min_length=1, max_length=4)


class ImportFileResponse(BaseModel):
    source_path: str
    source_format: str
    table: str
    catalog: str
    namespace: str
    table_name: str
    table_format: str
    mode: str
    columns: List[ColumnInfo]
    row_count: int
    location: Optional[str] = None
    duration_ms: float


class DatabaseConnectionRequest(BaseModel):
    id: Optional[str] = Field(default=None, max_length=64)
    name: str = Field(..., min_length=1, max_length=120)
    dialect: Literal["mysql", "postgresql", "sqlserver"]
    host: str = Field(..., min_length=1, max_length=253)
    port: int = Field(..., ge=1, le=65535)
    database: str = Field(..., min_length=1, max_length=128)
    username: str = Field(default="", max_length=128)
    password: str = Field(default="", max_length=256)
    properties: Optional[Dict[str, str]] = Field(default_factory=dict)


class DatabaseConnectionResponse(BaseModel):
    id: str
    name: str
    dialect: str
    host: str
    port: int
    database: str
    username: str
    has_password: bool
    properties: Dict[str, str]


class ImportDatabaseRequest(BaseModel):
    connection_id: str = Field(..., min_length=1, max_length=64)
    table: Optional[str] = Field(default=None, max_length=256)
    query: Optional[str] = Field(default=None, max_length=10_000)
    namespace: str = Field(default="default", max_length=120)
    table_name: Optional[str] = Field(default=None, max_length=120)
    table_format: Literal["delta", "iceberg", "spark"] = "delta"
    mode: Literal["error", "overwrite", "append"] = "error"
    max_rows: Optional[int] = Field(default=None, ge=1, le=10_000_000)


class ImportDatabaseResponse(BaseModel):
    connection_id: str
    source: str
    table: str
    catalog: str
    namespace: str
    table_name: str
    table_format: str
    mode: str
    columns: List[ColumnInfo]
    row_count: int
    location: Optional[str] = None
    duration_ms: float


class DatabasePreviewRequest(BaseModel):
    connection_id: str = Field(..., min_length=1, max_length=64)
    table: Optional[str] = Field(default=None, max_length=256)
    query: Optional[str] = Field(default=None, max_length=10_000)
    max_rows: int = Field(default=100, ge=1, le=1_000)


class DatabasePreviewResponse(BaseModel):
    connection_id: str
    source: str
    columns: List[ColumnInfo]
    rows: List[Dict[str, Any]]
    row_count: int


class ConfigDatabaseConnectionResponse(BaseModel):
    id: str
    name: str
    dialect: str
    host: str
    port: int
    database: str
    username: str


class ConfigDatabaseTableInfo(BaseModel):
    schema: str
    name: str
    full_name: str


class ConfigDatabaseTablesResponse(BaseModel):
    connection_id: str
    tables: List[ConfigDatabaseTableInfo]


class ConfigDatabaseListResponse(BaseModel):
    connection_id: str
    databases: List[str]
    default: str


class TableInfo(BaseModel):
    name: str
    full_name: str
    is_temporary: bool
    format: Optional[str] = None
    location: Optional[str] = None


class NamespaceInfo(BaseModel):
    name: str
    tables: List[TableInfo] = Field(default_factory=list)
    error: Optional[str] = None


class CatalogInfo(BaseModel):
    name: str
    catalog: str
    engine: str
    namespaces: List[NamespaceInfo] = Field(default_factory=list)
    error: Optional[str] = None


class TablesResponse(BaseModel):
    catalogs: List[CatalogInfo]
    generated_at: str


class StorageEntry(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    size: int
    modified: Optional[str] = None
    extension: Optional[str] = None
    category: Optional[str] = None
    children: List["StorageEntry"] = Field(default_factory=list)
    truncated: bool = False


class CategorySummary(BaseModel):
    files: int
    bytes: int


class StorageSummary(BaseModel):
    files: int
    directories: int
    bytes: int
    by_category: Dict[str, CategorySummary]
    truncated: bool
    max_entries: int
    max_depth: int


class StorageResponse(BaseModel):
    root: str
    path: str
    tree: StorageEntry
    summary: StorageSummary


class ExecutePySparkRequest(BaseModel):
    script: str = Field(..., min_length=1, max_length=200_000)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=3_600)


class ExecutePySparkResponse(BaseModel):
    script: str
    engine: str
    columns: List[ColumnInfo]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    truncated: bool
    max_rows: int
    stdout: str
    stderr: str
    result_type: Optional[str] = None
    result_repr: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    warehouse: str
    spark_initialized: bool
    spark_version: Optional[str] = None
    time: str


class SparkHomeInfo(BaseModel):
    path: str
    exists: bool
    valid: bool
    version: Optional[str] = None
    scala_version: Optional[str] = None
    compatible: bool
    reason: Optional[str] = None
    source: str


class SparkConfigResponse(BaseModel):
    pyspark_version: str
    required_spark_version: str
    bundled_home: str
    bundled_version: str
    configured_home: Optional[str] = None
    configured_source: str
    effective: SparkHomeInfo
    download_dir: str
    download_available_version: str
    spark_started: bool
    spark_version: Optional[str] = None


class SparkHomeRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=4_096)


class SparkBrowseResponse(BaseModel):
    path: Optional[str] = None
    cancelled: bool


class SparkDownloadRequest(BaseModel):
    version: Optional[str] = Field(default=None, max_length=32)
    destination: Optional[str] = Field(default=None, max_length=4_096)


class SparkDownloadStatus(BaseModel):
    state: str
    version: Optional[str] = None
    url: Optional[str] = None
    destination: Optional[str] = None
    downloaded_bytes: int = 0
    total_bytes: int = 0
    percent: float = 0.0
    speed_bps: float = 0.0
    message: str = ""
    error: Optional[str] = None
    installed_path: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class NotebookExecuteRequest(BaseModel):
    notebook_id: str = Field(..., min_length=1, max_length=120)
    script: str = Field(..., min_length=1, max_length=200_000)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=3_600)
    kernel_name: Optional[str] = Field(default=None, max_length=120)


class NotebookResetRequest(BaseModel):
    notebook_id: str = Field(..., min_length=1, max_length=120)


class KernelInfo(BaseModel):
    name: str
    display_name: str
    language: str
    builtin: bool = False


class KernelListResponse(BaseModel):
    kernels: List[KernelInfo]
    java_installed: bool


class KernelInstallResponse(BaseModel):
    installed: bool
    already_installed: bool
    message: str


class NotebookOutput(BaseModel):
    kind: Literal["text", "error"]
    text: str


class NotebookCellDocument(BaseModel):
    id: str
    type: Literal["code", "markdown"]
    source: str
    outputs: List[NotebookOutput] = Field(default_factory=list)


class NotebookDocumentResponse(BaseModel):
    path: str
    name: str
    cells: List[NotebookCellDocument]
    kernel_name: str = "python3"
    kernel_display_name: str = "Python 3 (PySpark built-in)"
    kernel_language: str = "python"
    nbformat: Optional[int] = None
    nbformat_minor: Optional[int] = None


class CreateNotebookRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=4_096)


class WorkspaceRootRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=4_096)


class WorkspaceEntry(BaseModel):
    name: str
    path: str
    type: Literal["file", "directory"]
    size: int = 0
    extension: Optional[str] = None
    children: List["WorkspaceEntry"] = Field(default_factory=list)


class WorkspaceResponse(BaseModel):
    root: Optional[str] = None
    name: Optional[str] = None
    exists: bool
    tree: List[WorkspaceEntry] = Field(default_factory=list)
    truncated: bool = False


class TextFileResponse(BaseModel):
    path: str
    name: str
    content: str
    language: str
    size: int


class SaveTextFileRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=4_096)
    content: str = Field(default="", max_length=20_000_000)


class SaveTextFileResponse(BaseModel):
    path: str
    size: int


class FilePickResponse(BaseModel):
    path: Optional[str] = None
    cancelled: bool


class JvmRunRequest(BaseModel):
    language: Literal["java", "scala"]
    source: str = Field(..., min_length=1, max_length=2_000_000)
    timeout_seconds: Optional[int] = Field(default=None, ge=5, le=3600)


class JvmRunResponse(BaseModel):
    language: str
    compile_ok: bool
    compile_output: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    execution_time_ms: float = 0.0


StorageEntry.model_rebuild()
WorkspaceEntry.model_rebuild()
