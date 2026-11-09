import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Database,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  Upload,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  ApiError,
  createConnection,
  deleteConnection,
  getConnections,
  importDatabase,
  previewDatabase,
  testConnection,
  updateConnection,
  type DatabaseConnection,
  type DatabaseDialect,
  type ImportDatabaseResponse,
  type ImportMode,
  type ImportTableFormat,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface DatabaseImportPanelProps {
  online: boolean;
  onImported: () => void;
}

const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;

const DIALECTS: { value: DatabaseDialect; label: string; defaultPort: number }[] = [
  { value: "mysql", label: "MySQL", defaultPort: 3306 },
  { value: "postgresql", label: "PostgreSQL", defaultPort: 5432 },
  { value: "sqlserver", label: "SQL Server", defaultPort: 1433 },
];

const TABLE_FORMATS: { value: ImportTableFormat; label: string; hint: string }[] = [
  { value: "delta", label: "Delta Lake", hint: "spark_catalog" },
  { value: "iceberg", label: "Apache Iceberg", hint: "local_iceberg" },
  { value: "spark", label: "Spark table", hint: "parquet" },
];

const inputClass =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 font-mono text-xs shadow-sm transition-colors placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const labelClass =
  "mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground";

export function DatabaseImportPanel({
  online,
  onImported,
}: DatabaseImportPanelProps) {
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(false);

  const [editing, setEditing] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [dialect, setDialect] = useState<DatabaseDialect>("postgresql");
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState(5432);
  const [database, setDatabase] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [sourceTable, setSourceTable] = useState("");
  const [sourceQuery, setSourceQuery] = useState("");
  const [namespace, setNamespace] = useState("default");
  const [tableName, setTableName] = useState("");
  const [tableFormat, setTableFormat] = useState<ImportTableFormat>("delta");
  const [mode, setMode] = useState<ImportMode>("error");
  const [maxRows, setMaxRows] = useState<number | "">("");

  const [running, setRunning] = useState(false);
  const [testing, setTesting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportDatabaseResponse | null>(null);
  const [preview, setPreview] = useState<
    { columns: { name: string; type: string }[]; rows: Record<string, unknown>[] } | null
  >(null);

  const loadConnections = async () => {
    setLoadingConnections(true);
    try {
      const data = await getConnections();
      setConnections(data);
      if (data.length > 0 && !selectedConnectionId) {
        setSelectedConnectionId(data[0].id);
      }
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Could not load connections.",
      );
    } finally {
      setLoadingConnections(false);
    }
  };

  useEffect(() => {
    if (online) {
      void loadConnections();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online]);

  const resetForm = () => {
    setEditing(false);
    setEditId(null);
    setName("");
    setDialect("postgresql");
    setHost("localhost");
    setPort(5432);
    setDatabase("");
    setUsername("");
    setPassword("");
  };

  const startEdit = (conn: DatabaseConnection) => {
    setEditing(true);
    setEditId(conn.id);
    setName(conn.name);
    setDialect(conn.dialect);
    setHost(conn.host);
    setPort(conn.port);
    setDatabase(conn.database);
    setUsername(conn.username);
    setPassword("");
  };

  const saveConnection = async () => {
    if (!name.trim()) {
      setError("Connection name is required.");
      return;
    }
    if (!host.trim() || !database.trim()) {
      setError("Host and database are required.");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const payload = {
        id: editId ?? undefined,
        name: name.trim(),
        dialect,
        host: host.trim(),
        port,
        database: database.trim(),
        username: username.trim(),
        password,
        properties: {},
      };
      if (editId) {
        await updateConnection(editId, payload);
      } else {
        await createConnection(payload);
      }
      await loadConnections();
      resetForm();
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Could not save connection.",
      );
    } finally {
      setRunning(false);
    }
  };

  const removeConnection = async (id: string) => {
    if (!window.confirm("Delete this connection?")) return;
    try {
      await deleteConnection(id);
      await loadConnections();
      if (selectedConnectionId === id) setSelectedConnectionId("");
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Could not delete connection.",
      );
    }
  };

  const handleTest = async () => {
    if (!selectedConnectionId) {
      setError("Select a connection first.");
      return;
    }
    setTesting(true);
    setError(null);
    try {
      await testConnection(selectedConnectionId);
      setError(null);
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Connection test failed.",
      );
    } finally {
      setTesting(false);
    }
  };

  const handlePreview = async () => {
    if (!selectedConnectionId) {
      setError("Select a connection first.");
      return;
    }
    if (!sourceTable.trim() && !sourceQuery.trim()) {
      setError("Enter a source table or a custom SELECT query.");
      return;
    }
    setPreviewing(true);
    setError(null);
    setPreview(null);
    try {
      const data = await previewDatabase({
        connection_id: selectedConnectionId,
        table: sourceTable.trim() || undefined,
        query: sourceQuery.trim() || undefined,
        max_rows: 20,
      });
      setPreview({ columns: data.columns, rows: data.rows });
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Preview failed.",
      );
    } finally {
      setPreviewing(false);
    }
  };

  const handleImport = async () => {
    if (!selectedConnectionId) {
      setError("Select a connection first.");
      return;
    }
    if (!sourceTable.trim() && !sourceQuery.trim()) {
      setError("Enter a source table or a custom SELECT query.");
      return;
    }
    if (!IDENTIFIER.test(namespace.trim())) {
      setError(
        "Namespace must start with a letter or underscore and use only letters, digits, and underscores.",
      );
      return;
    }
    if (tableName.trim() && !IDENTIFIER.test(tableName.trim())) {
      setError(
        "Table name must start with a letter or underscore and use only letters, digits, and underscores.",
      );
      return;
    }

    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const response = await importDatabase({
        connection_id: selectedConnectionId,
        table: sourceTable.trim() || undefined,
        query: sourceQuery.trim() || undefined,
        namespace: namespace.trim(),
        table_name: tableName.trim() || undefined,
        table_format: tableFormat,
        mode,
        max_rows: maxRows ? Number(maxRows) : undefined,
      });
      setResult(response);
      onImported();
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "The import failed.",
      );
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          Saved connections
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            resetForm();
            setEditing(true);
          }}
          disabled={!online || loadingConnections}
        >
          <Plus className="size-3.5" />
          Add connection
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void loadConnections()}
          disabled={!online || loadingConnections}
        >
          <RefreshCw className="size-3.5" />
          Refresh
        </Button>
      </div>

      {connections.length === 0 && !editing ? (
        <div className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
          <Database className="mx-auto mb-2 size-5 text-muted-foreground/60" />
          No database connections yet. Add one to import from MySQL, PostgreSQL,
          or SQL Server.
        </div>
      ) : (
        <div className="grid gap-2">
          {connections.map((conn) => (
            <div
              key={conn.id}
              className={cn(
                "flex items-center justify-between gap-3 rounded-md border px-3 py-2 transition-colors",
                selectedConnectionId === conn.id
                  ? "border-primary bg-primary/5"
                  : "border-border bg-background/40 hover:bg-muted/30",
              )}
            >
              <button
                type="button"
                onClick={() => setSelectedConnectionId(conn.id)}
                className="flex min-w-0 flex-1 flex-col text-left"
              >
                <span className="truncate text-xs font-medium">{conn.name}</span>
                <span className="truncate font-mono text-[10px] text-muted-foreground">
                  {conn.dialect} · {conn.host}:{conn.port}/{conn.database}
                </span>
              </button>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  title="Edit"
                  onClick={() => startEdit(conn)}
                >
                  <Save className="size-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  title="Delete"
                  onClick={() => void removeConnection(conn.id)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing ? (
        <div className="rounded-lg border border-border bg-background/40 p-4">
          <h3 className="mb-3 text-xs font-semibold">
            {editId ? "Edit connection" : "New connection"}
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <label className={labelClass}>Name</label>
              <input
                className={inputClass}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Local PostgreSQL"
              />
            </div>
            <div>
              <label className={labelClass}>Dialect</label>
              <select
                className={inputClass}
                value={dialect}
                onChange={(e) => {
                  const next = e.target.value as DatabaseDialect;
                  setDialect(next);
                  setPort(DIALECTS.find((d) => d.value === next)?.defaultPort ?? 5432);
                }}
              >
                {DIALECTS.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClass}>Port</label>
              <input
                type="number"
                className={inputClass}
                value={port}
                onChange={(e) => setPort(Number(e.target.value))}
              />
            </div>
            <div>
              <label className={labelClass}>Host</label>
              <input
                className={inputClass}
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="localhost"
              />
            </div>
            <div>
              <label className={labelClass}>Database</label>
              <input
                className={inputClass}
                value={database}
                onChange={(e) => setDatabase(e.target.value)}
                placeholder="mydb"
              />
            </div>
            <div>
              <label className={labelClass}>Username</label>
              <input
                className={inputClass}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div>
              <label className={labelClass}>Password</label>
              <input
                type="password"
                className={inputClass}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={editId ? "Leave blank to keep existing" : ""}
              />
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2">
            <Button size="sm" onClick={() => void saveConnection()} disabled={running}>
              {running ? <Loader2 className="animate-spin" /> : <Save className="size-3.5" />}
              Save
            </Button>
            <Button variant="ghost" size="sm" onClick={resetForm}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      {connections.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <label className={labelClass}>Source table</label>
            <input
              className={inputClass}
              value={sourceTable}
              onChange={(e) => setSourceTable(e.target.value)}
              placeholder="public.users"
              spellCheck={false}
            />
          </div>

          <div className="md:col-span-2">
            <label className={labelClass}>Or custom SELECT query</label>
            <textarea
              className="min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 font-mono text-xs shadow-sm transition-colors placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={sourceQuery}
              onChange={(e) => setSourceQuery(e.target.value)}
              placeholder="SELECT * FROM public.users WHERE active = true"
              spellCheck={false}
            />
          </div>

          <div>
            <span className={labelClass}>Table format</span>
            <div className="grid grid-cols-3 gap-1 rounded-md border border-input p-1">
              {TABLE_FORMATS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setTableFormat(option.value)}
                  className={cn(
                    "rounded px-2 py-1.5 text-center transition-colors",
                    tableFormat === option.value
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted/50",
                  )}
                >
                  <span className="block text-[11px] font-medium">{option.label}</span>
                  <span className="block font-mono text-[9px] opacity-70">
                    {option.hint}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className={labelClass}>Namespace</label>
            <input
              className={inputClass}
              value={namespace}
              onChange={(e) => setNamespace(e.target.value)}
              spellCheck={false}
            />
          </div>

          <div>
            <label className={labelClass}>Target table name (optional)</label>
            <input
              className={inputClass}
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              placeholder="Derived from source table or query"
              spellCheck={false}
            />
          </div>

          <div>
            <label className={labelClass}>If target exists</label>
            <select
              className={inputClass}
              value={mode}
              onChange={(e) => setMode(e.target.value as ImportMode)}
            >
              <option value="error">Fail the import</option>
              <option value="overwrite">Replace the table</option>
              <option value="append">Append rows</option>
            </select>
          </div>

          <div>
            <label className={labelClass}>Max rows (optional)</label>
            <input
              type="number"
              className={inputClass}
              value={maxRows}
              onChange={(e) =>
                setMaxRows(e.target.value === "" ? "" : Number(e.target.value))
              }
              placeholder="Unlimited"
            />
          </div>
        </div>
      ) : null}

      {preview ? (
        <div className="rounded-lg border border-border bg-background/40 p-3">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Preview ({preview.rows.length} rows)
          </p>
          <div className="max-h-[180px] overflow-auto">
            <table className="w-full text-left text-[11px]">
              <thead>
                <tr className="border-b border-border/60 text-muted-foreground">
                  {preview.columns.map((col) => (
                    <th key={col.name} className="px-2 py-1 font-medium">
                      {col.name}
                      <span className="ml-1 font-mono text-[9px] opacity-70">
                        {col.type}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, idx) => (
                  <tr key={idx} className="border-b border-border/30">
                    {preview.columns.map((col) => (
                      <td key={col.name} className="px-2 py-1 font-mono">
                        {String(row[col.name] ?? "NULL")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-400" />
          <pre className="whitespace-pre-wrap break-words font-mono text-[11px] text-red-200/90">
            {error}
          </pre>
        </div>
      ) : null}

      {result ? (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2.5">
          <div className="flex items-center gap-2 text-xs font-medium text-emerald-300">
            <CheckCircle2 className="size-4" />
            Imported {result.row_count.toLocaleString()} rows into{" "}
            <span className="font-mono">{result.table}</span>
          </div>
          <p className="mt-1 font-mono text-[10px] text-emerald-200/70">
            {result.table_format} · {result.columns.length} columns ·{" "}
            {Math.round(result.duration_ms).toLocaleString()} ms
          </p>
        </div>
      ) : null}

      {connections.length > 0 ? (
        <div className="flex items-center gap-2">
          <Button onClick={() => void handleImport()} disabled={running || !online}>
            {running ? <Loader2 className="animate-spin" /> : <Upload className="size-4" />}
            {running ? "Importing…" : "Import from database"}
          </Button>
          <Button
            variant="outline"
            onClick={() => void handlePreview()}
            disabled={previewing || !online}
          >
            {previewing ? <Loader2 className="animate-spin" /> : <Play className="size-4" />}
            Preview
          </Button>
          <Button
            variant="ghost"
            onClick={() => void handleTest()}
            disabled={testing || !online}
          >
            {testing ? <Loader2 className="animate-spin" /> : <Database className="size-4" />}
            Test connection
          </Button>
        </div>
      ) : null}
    </div>
  );
}
