const DEFAULT_API_BASE = "http://127.0.0.1:8000";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE
).replace(/\/$/, "");
export const API_DOCS_URL = `${API_BASE_URL}/docs`;

export type Engine = "iceberg" | "delta" | "spark" | string;

export interface SqlColumn {
  name: string;
  type: string;
}

export interface StatementExecution {
  statement: string;
  engine: Engine;
  statement_type: string;
  columns: SqlColumn[];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
  max_rows: number;
}

export interface ExecuteSqlResponse {
  sql: string;
  engine: Engine;
  statement_type: string;
  columns: SqlColumn[];
  rows: Record<string, unknown>[];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
  max_rows: number;
  statements: StatementExecution[];
}

export interface TableInfo {
  name: string;
  full_name: string;
  is_temporary: boolean;
  format: string | null;
  location: string | null;
}

export interface NamespaceInfo {
  name: string;
  tables: TableInfo[];
  error: string | null;
}

export interface CatalogInfo {
  name: string;
  catalog: string;
  engine: Engine;
  namespaces: NamespaceInfo[];
  error: string | null;
}

export interface TablesResponse {
  catalogs: CatalogInfo[];
  generated_at: string;
}

export type ImportSourceFormat =
  | "csv"
  | "json"
  | "parquet"
  | "txt"
  | "orc"
  | "avro";
export type ImportTableFormat = "delta" | "iceberg" | "spark";
export type ImportMode = "error" | "overwrite" | "append";

export interface ImportFileRequest {
  path: string;
  table_name?: string;
  namespace?: string;
  table_format?: ImportTableFormat;
  source_format?: ImportSourceFormat;
  mode?: ImportMode;
  has_header?: boolean;
  delimiter?: string;
}

export interface ImportFileResponse {
  source_path: string;
  source_format: string;
  table: string;
  catalog: string;
  namespace: string;
  table_name: string;
  table_format: string;
  mode: string;
  columns: SqlColumn[];
  row_count: number;
  location: string | null;
  duration_ms: number;
}

export type DatabaseDialect = "mysql" | "postgresql" | "sqlserver";

export interface DatabaseConnection {
  id: string;
  name: string;
  dialect: DatabaseDialect;
  host: string;
  port: number;
  database: string;
  username: string;
  has_password: boolean;
  properties: Record<string, string>;
}

export interface DatabaseConnectionRequest {
  id?: string;
  name: string;
  dialect: DatabaseDialect;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  properties: Record<string, string>;
}

export interface ImportDatabaseRequest {
  connection_id: string;
  table?: string;
  query?: string;
  namespace?: string;
  table_name?: string;
  table_format?: ImportTableFormat;
  mode?: ImportMode;
  max_rows?: number;
}

export interface ImportDatabaseResponse {
  connection_id: string;
  source: string;
  table: string;
  catalog: string;
  namespace: string;
  table_name: string;
  table_format: string;
  mode: string;
  columns: SqlColumn[];
  row_count: number;
  location: string | null;
  duration_ms: number;
}

export interface DatabasePreviewRequest {
  connection_id: string;
  table?: string;
  query?: string;
  max_rows?: number;
}

export interface DatabasePreviewResponse {
  connection_id: string;
  source: string;
  columns: SqlColumn[];
  rows: Record<string, unknown>[];
  row_count: number;
}

export interface ConfigDatabaseConnection {
  id: string;
  name: string;
  dialect: DatabaseDialect;
  host: string;
  port: number;
  database: string;
  username: string;
}

export interface ConfigDatabaseTable {
  schema: string;
  name: string;
  full_name: string;
}

export interface ConfigDatabaseTablesResponse {
  connection_id: string;
  tables: ConfigDatabaseTable[];
}

export interface ConfigDatabaseListResponse {
  connection_id: string;
  databases: string[];
  default: string;
}

export interface StorageEntry {
  name: string;
  path: string;
  type: "file" | "directory";
  size: number;
  modified: string | null;
  extension: string | null;
  category: string | null;
  children: StorageEntry[];
  truncated: boolean;
}

export interface CategorySummary {
  files: number;
  bytes: number;
}

export interface StorageSummary {
  files: number;
  directories: number;
  bytes: number;
  by_category: Record<string, CategorySummary>;
  truncated: boolean;
  max_entries: number;
  max_depth: number;
}

export interface StorageResponse {
  root: string;
  path: string;
  tree: StorageEntry;
  summary: StorageSummary;
}

export interface StorageFileResponse {
  path: string;
  name: string;
  content: string;
  language: string;
  size: number;
  binary: boolean;
  truncated: boolean;
  max_bytes: number;
}

export interface ExecutePySparkResponse {
  script: string;
  engine: Engine;
  columns: SqlColumn[];
  rows: Record<string, unknown>[];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
  max_rows: number;
  stdout: string;
  stderr: string;
  result_type: string | null;
  result_repr: string | null;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  warehouse: string;
  spark_initialized: boolean;
  spark_version: string | null;
  time: string;
}

export interface SparkHomeInfo {
  path: string;
  exists: boolean;
  valid: boolean;
  version: string | null;
  scala_version: string | null;
  compatible: boolean;
  reason: string | null;
  source: string;
}

export interface SparkConfigResponse {
  pyspark_version: string;
  required_spark_version: string;
  bundled_home: string;
  bundled_version: string;
  configured_home: string | null;
  configured_source: string;
  effective: SparkHomeInfo;
  download_dir: string;
  download_available_version: string;
  spark_started: boolean;
  spark_version: string | null;
}

export interface SparkDownloadStatus {
  state: string;
  version: string | null;
  url: string | null;
  destination: string | null;
  downloaded_bytes: number;
  total_bytes: number;
  percent: number;
  speed_bps: number;
  message: string;
  error: string | null;
  installed_path: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface NotebookOutput {
  kind: "text" | "error";
  text: string;
}

export interface NotebookCellDocument {
  id: string;
  type: "code" | "markdown";
  source: string;
  outputs: NotebookOutput[];
}

export interface NotebookDocumentResponse {
  path: string;
  name: string;
  cells: NotebookCellDocument[];
  nbformat: number | null;
  nbformat_minor: number | null;
  kernel_name: string;
  kernel_display_name: string;
  kernel_language: string;
}

export interface WorkspaceEntry {
  name: string;
  path: string;
  type: "file" | "directory";
  size: number;
  extension: string | null;
  children: WorkspaceEntry[];
}

export interface WorkspaceResponse {
  root: string | null;
  name: string | null;
  exists: boolean;
  tree: WorkspaceEntry[];
  truncated: boolean;
}

export interface TextFileResponse {
  path: string;
  name: string;
  content: string;
  language: string;
  size: number;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractError(payload: unknown): string {
  if (typeof payload === "string") return payload;
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : JSON.stringify(item),
        )
        .join("\n");
    }
    return JSON.stringify(detail);
  }
  return "The request failed.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      `Cannot reach the backend at ${API_BASE_URL}. Start it with scripts/start-backend.ps1.`,
      0,
    );
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(extractError(payload), response.status);
  }

  return payload as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function cancelExecution(
  target: string,
): Promise<{ cancelled: boolean; target: string }> {
  return request<{ cancelled: boolean; target: string }>("/api/cancel", {
    method: "POST",
    body: JSON.stringify({ target }),
  });
}

export function executeSql(
  sql: string,
  options: { maxRows?: number; timeoutSeconds?: number } = {},
): Promise<ExecuteSqlResponse> {
  return request<ExecuteSqlResponse>("/api/execute-sql", {
    method: "POST",
    body: JSON.stringify({
      sql,
      max_rows: options.maxRows,
      timeout_seconds: options.timeoutSeconds,
    }),
  });
}

export function executePySpark(
  script: string,
  options: { timeoutSeconds?: number } = {},
): Promise<ExecutePySparkResponse> {
  return request<ExecutePySparkResponse>("/api/execute-pyspark", {
    method: "POST",
    body: JSON.stringify({
      script,
      timeout_seconds: options.timeoutSeconds,
    }),
  });
}

export type JvmLanguage = "java" | "scala";

export interface JvmRunResponse {
  language: JvmLanguage;
  compile_ok: boolean;
  compile_output: string;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  execution_time_ms: number;
}

export function executeJvm(
  language: JvmLanguage,
  source: string,
  options: { timeoutSeconds?: number } = {},
): Promise<JvmRunResponse> {
  return request<JvmRunResponse>("/api/execute-jvm", {
    method: "POST",
    body: JSON.stringify({
      language,
      source,
      timeout_seconds: options.timeoutSeconds,
    }),
  });
}

export function getTables(includeDetails = true): Promise<TablesResponse> {
  return request<TablesResponse>(
    `/api/tables?include_details=${includeDetails ? "true" : "false"}`,
  );
}

export function importFile(
  payload: ImportFileRequest,
): Promise<ImportFileResponse> {
  return request<ImportFileResponse>("/api/import-file", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getConnections(): Promise<DatabaseConnection[]> {
  return request<DatabaseConnection[]>("/api/connections");
}

export function createConnection(
  payload: DatabaseConnectionRequest,
): Promise<DatabaseConnection> {
  return request<DatabaseConnection>("/api/connections", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateConnection(
  id: string,
  payload: DatabaseConnectionRequest,
): Promise<DatabaseConnection> {
  return request<DatabaseConnection>(`/api/connections/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteConnection(id: string): Promise<{ deleted: string }> {
  return request<{ deleted: string }>(`/api/connections/${id}`, {
    method: "DELETE",
  });
}

export function testConnection(id: string): Promise<{ ok: boolean; row_count: number }> {
  return request<{ ok: boolean; row_count: number }>(`/api/connections/${id}/test`, {
    method: "POST",
  });
}

export function previewDatabase(
  payload: DatabasePreviewRequest,
): Promise<DatabasePreviewResponse> {
  return request<DatabasePreviewResponse>(`/api/connections/${payload.connection_id}/preview`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function importDatabase(
  payload: ImportDatabaseRequest,
): Promise<ImportDatabaseResponse> {
  return request<ImportDatabaseResponse>("/api/import-database", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getConfigConnections(): Promise<ConfigDatabaseConnection[]> {
  return request<ConfigDatabaseConnection[]>("/api/database-config/connections");
}

export function getConfigConnectionTables(
  connectionId: string,
  database?: string,
): Promise<ConfigDatabaseTablesResponse> {
  const params = new URLSearchParams();
  if (database) params.set("database", database);
  const query = params.toString();
  return request<ConfigDatabaseTablesResponse>(
    `/api/database-config/connections/${connectionId}/tables${query ? `?${query}` : ""}`,
  );
}

export function getConfigConnectionDatabases(
  connectionId: string,
): Promise<ConfigDatabaseListResponse> {
  return request<ConfigDatabaseListResponse>(
    `/api/database-config/connections/${connectionId}/databases`,
  );
}

export function getStorage(
  path = "",
  depth = 3,
  maxEntries = 2000,
): Promise<StorageResponse> {
  const params = new URLSearchParams({
    path,
    depth: String(depth),
    max_entries: String(maxEntries),
  });
  return request<StorageResponse>(`/api/storage-explorer?${params.toString()}`);
}

export function getStorageFile(path: string): Promise<StorageFileResponse> {
  const params = new URLSearchParams({ path });
  return request<StorageFileResponse>(
    `/api/storage-explorer/file?${params.toString()}`,
  );
}

export function getStorageDownloadUrl(path: string): string {
  const params = new URLSearchParams({ path });
  return `${API_BASE_URL}/api/storage-explorer/download?${params.toString()}`;
}

export function getSparkConfig(): Promise<SparkConfigResponse> {
  return request<SparkConfigResponse>("/api/spark/config");
}

export function setSparkHome(path: string): Promise<SparkConfigResponse> {
  return request<SparkConfigResponse>("/api/spark/home", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export function resetSparkHome(): Promise<SparkConfigResponse> {
  return request<SparkConfigResponse>("/api/spark/home", {
    method: "DELETE",
  });
}

export function browseSparkHome(): Promise<{ path: string | null; cancelled: boolean }> {
  return request<{ path: string | null; cancelled: boolean }>("/api/spark/browse", {
    method: "POST",
  });
}

export function startSparkDownload(
  options: { version?: string; destination?: string } = {},
): Promise<SparkDownloadStatus> {
  return request<SparkDownloadStatus>("/api/spark/download", {
    method: "POST",
    body: JSON.stringify({
      version: options.version,
      destination: options.destination,
    }),
  });
}

export function getSparkDownloadStatus(): Promise<SparkDownloadStatus> {
  return request<SparkDownloadStatus>("/api/spark/download/status");
}

export function executeNotebookCell(
  notebookId: string,
  script: string,
  options: { timeoutSeconds?: number; kernelName?: string } = {},
): Promise<ExecutePySparkResponse> {
  return request<ExecutePySparkResponse>("/api/notebook/execute", {
    method: "POST",
    body: JSON.stringify({
      notebook_id: notebookId,
      script,
      timeout_seconds: options.timeoutSeconds,
      kernel_name: options.kernelName,
    }),
  });
}

export interface KernelInfo {
  name: string;
  display_name: string;
  language: string;
  builtin: boolean;
}

export interface KernelListResponse {
  kernels: KernelInfo[];
  java_installed: boolean;
  scala_installed: boolean;
}

export function getKernels(): Promise<KernelListResponse> {
  return request<KernelListResponse>("/api/kernels");
}

export function installJavaKernel(): Promise<{
  installed: boolean;
  already_installed: boolean;
  message: string;
}> {
  return request("/api/kernels/java/install", { method: "POST" });
}

export function installScalaKernel(): Promise<{
  installed: boolean;
  already_installed: boolean;
  message: string;
}> {
  return request("/api/kernels/scala/install", { method: "POST" });
}

export function resetNotebookKernel(
  notebookId: string,
): Promise<{ notebook_id: string; reset: boolean; existed: boolean }> {
  return request<{ notebook_id: string; reset: boolean; existed: boolean }>(
    "/api/notebook/reset",
    {
      method: "POST",
      body: JSON.stringify({ notebook_id: notebookId }),
    },
  );
}

export function getWorkspace(): Promise<WorkspaceResponse> {
  return request<WorkspaceResponse>("/api/workspace");
}

export function openWorkspacePicker(): Promise<WorkspaceResponse> {
  return request<WorkspaceResponse>("/api/workspace/open", { method: "POST" });
}

export function setWorkspaceRoot(path: string): Promise<WorkspaceResponse> {
  return request<WorkspaceResponse>("/api/workspace/root", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}

export function closeWorkspace(): Promise<WorkspaceResponse> {
  return request<WorkspaceResponse>("/api/workspace/root", { method: "DELETE" });
}

export function getWorkspaceFile(path: string): Promise<TextFileResponse> {
  const params = new URLSearchParams({ path });
  return request<TextFileResponse>(`/api/workspace/file?${params.toString()}`);
}

export function saveWorkspaceFile(
  path: string,
  content: string,
): Promise<{ path: string; size: number }> {
  return request<{ path: string; size: number }>("/api/workspace/file", {
    method: "PUT",
    body: JSON.stringify({ path, content }),
  });
}

export function getWorkspaceNotebook(
  path: string,
): Promise<NotebookDocumentResponse> {
  const params = new URLSearchParams({ path });
  return request<NotebookDocumentResponse>(
    `/api/workspace/notebook?${params.toString()}`,
  );
}

export function pickDataFile(): Promise<{ path: string | null; cancelled: boolean }> {
  return request<{ path: string | null; cancelled: boolean }>("/api/files/pick", {
    method: "POST",
  });
}

export function createWorkspaceNotebook(
  path: string,
): Promise<NotebookDocumentResponse> {
  return request<NotebookDocumentResponse>("/api/workspace/notebook", {
    method: "POST",
    body: JSON.stringify({ path }),
  });
}
