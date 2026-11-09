import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Database,
  Loader2,
  RefreshCw,
  Table2,
  Upload,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ApiError,
  getConfigConnectionDatabases,
  getConfigConnectionTables,
  getConfigConnections,
  importDatabase,
  type ConfigDatabaseConnection,
  type ConfigDatabaseTable,
  type ImportDatabaseResponse,
  type ImportTableFormat,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface DatabasesPageProps {
  online: boolean;
  onImported: () => void;
  onUseTable?: (fullName: string) => void;
}

const TABLE_FORMATS: { value: ImportTableFormat; label: string; hint: string }[] = [
  { value: "delta", label: "Delta", hint: "spark_catalog" },
  { value: "iceberg", label: "Iceberg", hint: "local_iceberg" },
  { value: "spark", label: "Spark", hint: "parquet" },
];

const inputClass =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 font-mono text-xs shadow-sm transition-colors placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const labelClass =
  "mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground";

export function DatabasesPage({
  online,
  onImported,
  onUseTable,
}: DatabasesPageProps) {
  const [connections, setConnections] = useState<ConfigDatabaseConnection[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [databases, setDatabases] = useState<string[]>([]);
  const [selectedDatabase, setSelectedDatabase] = useState<string>("");
  const [databasesLoading, setDatabasesLoading] = useState(false);
  const [tables, setTables] = useState<ConfigDatabaseTable[]>([]);
  const [tablesLoading, setTablesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [importingTable, setImportingTable] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportDatabaseResponse | null>(null);
  const [tableFormat, setTableFormat] = useState<ImportTableFormat>("delta");
  const [namespace, setNamespace] = useState("default");
  const [mode, setMode] = useState<"error" | "overwrite" | "append">("error");

  const loadConnections = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getConfigConnections();
      setConnections(data);
      setSelectedConnectionId((previous) =>
        previous && data.some((conn) => conn.id === previous)
          ? previous
          : (data[0]?.id ?? ""),
      );
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Could not load database connections.",
      );
    } finally {
      setLoading(false);
    }
  };

  const loadTables = async (connectionId: string, database?: string) => {
    if (!connectionId) return;
    setTablesLoading(true);
    setError(null);
    setTables([]);
    try {
      const data = await getConfigConnectionTables(connectionId, database);
      setTables(data.tables);
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Could not load tables.",
      );
    } finally {
      setTablesLoading(false);
    }
  };

  const loadDatabases = async (connectionId: string, preferred?: string) => {
    if (!connectionId) return;
    setDatabasesLoading(true);
    setDatabases([]);
    setSelectedDatabase("");
    try {
      const data = await getConfigConnectionDatabases(connectionId);
      setDatabases(data.databases);
      const chosen =
        preferred && data.databases.includes(preferred)
          ? preferred
          : data.databases.includes(data.default)
            ? data.default
            : (data.databases[0] ?? "");
      setSelectedDatabase(chosen);
      if (chosen) {
        await loadTables(connectionId, chosen);
      }
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Could not load databases.",
      );
    } finally {
      setDatabasesLoading(false);
    }
  };

  const refreshAll = async () => {
    await loadConnections();
    if (selectedConnectionId) {
      await loadDatabases(selectedConnectionId, selectedDatabase);
    }
  };

  useEffect(() => {
    if (online) {
      void loadConnections();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [online]);

  useEffect(() => {
    if (selectedConnectionId) {
      void loadDatabases(selectedConnectionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedConnectionId]);

  const handleImport = async (table: ConfigDatabaseTable) => {
    setImportingTable(table.full_name);
    setImportResult(null);
    setError(null);
    try {
      const result = await importDatabase({
        connection_id: selectedConnectionId,
        table: table.full_name,
        namespace,
        table_format: tableFormat,
        mode,
      });
      setImportResult(result);
      onImported();
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Import failed.",
      );
    } finally {
      setImportingTable(null);
    }
  };

  return (
    <div className="animate-fade-in space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Databases</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Browse tables from databases defined in{" "}
          <span className="font-mono">databases.cfg</span> and import them into the
          lakehouse.
        </p>
      </div>

      {!online ? (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
          <AlertCircle className="size-4" />
          The backend is offline. Start it to browse databases.
        </div>
      ) : null}

      <Card>
        <CardContent className="p-5">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <span className={labelClass}>Connection</span>
              <select
                className={inputClass}
                value={selectedConnectionId}
                onChange={(e) => setSelectedConnectionId(e.target.value)}
                disabled={loading || !online}
              >
                {connections.length === 0 ? (
                  <option value="">No connections configured</option>
                ) : null}
                {connections.map((conn) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.name} ({conn.dialect})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className={labelClass}>Database</span>
              <select
                className={inputClass}
                value={selectedDatabase}
                onChange={(e) => {
                  const next = e.target.value;
                  setSelectedDatabase(next);
                  void loadTables(selectedConnectionId, next);
                }}
                disabled={
                  loading ||
                  databasesLoading ||
                  !online ||
                  databases.length === 0
                }
              >
                {databases.length === 0 ? (
                  <option value="">
                    {databasesLoading ? "Loading…" : "No databases"}
                  </option>
                ) : null}
                {databases.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void refreshAll()}
              disabled={loading || databasesLoading || !online}
            >
              {loading || databasesLoading ? (
                <Loader2 className="animate-spin" />
              ) : (
                <RefreshCw className="size-3.5" />
              )}
              Refresh
            </Button>
          </div>

          <div className="mt-4 grid gap-4 border-t border-border/60 pt-4 md:grid-cols-4">
            <div>
              <span className={labelClass}>Import as</span>
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
              <label className={labelClass}>If target exists</label>
              <select
                className={inputClass}
                value={mode}
                onChange={(e) => setMode(e.target.value as typeof mode)}
              >
                <option value="error">Fail</option>
                <option value="overwrite">Replace</option>
                <option value="append">Append</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-400" />
          <pre className="whitespace-pre-wrap break-words font-mono text-[11px] text-red-200/90">
            {error}
          </pre>
        </div>
      ) : null}

      {importResult ? (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2.5">
          <div className="flex items-center gap-2 text-xs font-medium text-emerald-300">
            <CheckCircle2 className="size-4" />
            Imported {importResult.row_count.toLocaleString()} rows into{" "}
            <span className="font-mono">{importResult.table}</span>
          </div>
          <p className="mt-1 font-mono text-[10px] text-emerald-200/70">
            {importResult.table_format} · {importResult.columns.length} columns ·{" "}
            {Math.round(importResult.duration_ms).toLocaleString()} ms
          </p>
          <p className="mt-1 text-[10px] text-emerald-200/70">
            Find it in Schema Explorer, or query it now:
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {onUseTable ? (
              <Button
                size="sm"
                variant="outline"
                className="h-7"
                onClick={() => onUseTable(importResult.table)}
              >
                <Table2 />
                Query in SQL editor
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      <Card>
        <CardContent className="p-0">
          <div className="flex items-center gap-2 border-b border-border/70 px-5 py-3">
            <Table2 className="size-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Tables</h2>
            {tablesLoading ? <Loader2 className="ml-2 size-3.5 animate-spin text-muted-foreground" /> : null}
          </div>
          {tables.length === 0 && !tablesLoading ? (
            <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center text-muted-foreground">
              <Database className="size-8 opacity-40" />
              <div className="text-sm">
                {connections.length === 0
                  ? "No connections found in databases.cfg."
                  : "No tables found or could not connect."}
              </div>
              <p className="max-w-md text-xs">
                Create{" "}
                <span className="font-mono text-foreground">databases.cfg</span> in the
                repository root with [mysql.myconn], [postgresql.myconn], or
                [sqlserver.myconn] sections.
              </p>
            </div>
          ) : (
            <div className="max-h-[55vh] overflow-auto">
              <table className="w-full text-left text-[13px]">
                <thead>
                  <tr className="border-b border-border/70 bg-muted text-[11px] uppercase tracking-wide text-muted-foreground">
                    <th className="px-4 py-2 font-medium">Schema</th>
                    <th className="px-4 py-2 font-medium">Table</th>
                    <th className="px-4 py-2 font-medium text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {tables.map((table) => (
                    <tr
                      key={table.full_name}
                      className="border-b border-border/40 transition-colors hover:bg-muted/30"
                    >
                      <td className="px-4 py-2 font-mono text-xs">{table.schema}</td>
                      <td className="px-4 py-2 font-mono text-xs">{table.name}</td>
                      <td className="px-4 py-2 text-right">
                        <Button
                          size="sm"
                          onClick={() => void handleImport(table)}
                          disabled={importingTable === table.full_name || !online}
                        >
                          {importingTable === table.full_name ? (
                            <Loader2 className="animate-spin" />
                          ) : (
                            <Upload className="size-3.5" />
                          )}
                          Import
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
