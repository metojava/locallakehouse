import { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Database,
  FileUp,
  FolderSearch,
  Loader2,
  Upload,
  X,
} from "lucide-react";

import { DatabaseImportPanel } from "@/components/database-import-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  ApiError,
  importFile,
  pickDataFile,
  type ImportFileResponse,
  type ImportMode,
  type ImportSourceFormat,
  type ImportTableFormat,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface ImportPanelProps {
  online: boolean;
  onImported: () => void;
  onClose: () => void;
}

const IDENTIFIER = /^[A-Za-z_][A-Za-z0-9_]*$/;

const TABLE_FORMATS: { value: ImportTableFormat; label: string; hint: string }[] = [
  { value: "delta", label: "Delta Lake", hint: "spark_catalog" },
  { value: "iceberg", label: "Apache Iceberg", hint: "local_iceberg" },
  { value: "spark", label: "Spark table", hint: "parquet" },
];

const inputClass =
  "h-9 w-full rounded-md border border-input bg-transparent px-3 font-mono text-xs shadow-sm transition-colors placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const labelClass =
  "mb-1.5 block text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground";

export function ImportPanel({ online, onImported, onClose }: ImportPanelProps) {
  const [activeTab, setActiveTab] = useState<"file" | "database">("file");

  const [path, setPath] = useState("");
  const [tableName, setTableName] = useState("");
  const [namespace, setNamespace] = useState("default");
  const [tableFormat, setTableFormat] = useState<ImportTableFormat>("delta");
  const [sourceFormat, setSourceFormat] = useState<"auto" | ImportSourceFormat>(
    "auto",
  );
  const [mode, setMode] = useState<ImportMode>("error");
  const [hasHeader, setHasHeader] = useState(true);
  const [delimiter, setDelimiter] = useState(",");
  const [running, setRunning] = useState(false);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportFileResponse | null>(null);

  const csvMode =
    sourceFormat === "csv" ||
    sourceFormat === "txt" ||
    sourceFormat === "auto";

  const browseFile = async () => {
    setActiveTab("file");
    if (!online || picking) return;
    setPicking(true);
    setError(null);
    try {
      const selection = await pickDataFile();
      if (selection.path) setPath(selection.path);
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "The file picker could not be opened.",
      );
    } finally {
      setPicking(false);
    }
  };

  const submit = async () => {
    const trimmedPath = path.trim();
    if (!trimmedPath) {
      setError("Enter the full path to a local CSV, JSON, or Parquet file.");
      return;
    }
    if (tableName.trim() && !IDENTIFIER.test(tableName.trim())) {
      setError(
        "Table name must start with a letter or underscore and use only letters, digits, and underscores.",
      );
      return;
    }
    if (!IDENTIFIER.test(namespace.trim())) {
      setError(
        "Namespace must start with a letter or underscore and use only letters, digits, and underscores.",
      );
      return;
    }

    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const response = await importFile({
        path: trimmedPath,
        table_name: tableName.trim() || undefined,
        namespace: namespace.trim(),
        table_format: tableFormat,
        source_format: sourceFormat === "auto" ? undefined : sourceFormat,
        mode,
        has_header: hasHeader,
        delimiter: delimiter || ",",
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
    <Card className="border-primary/20 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold">Import data</h2>
          <p className="mt-1 max-w-2xl text-xs text-muted-foreground">
            Register a local file or import from a database as a Delta, Iceberg,
            or Spark table.
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} title="Close">
          <X />
        </Button>
      </div>

      <div className="mt-4 flex gap-2 border-b border-border/60 pb-3">
        <button
          type="button"
          onClick={() => void browseFile()}
          disabled={!online || picking}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-60",
            activeTab === "file"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted/50",
          )}
        >
          {picking ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <FileUp className="size-3.5" />
          )}
          {picking ? "Waiting for picker…" : "Local file"}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("database")}
          className={cn(
            "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
            activeTab === "database"
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-muted/50",
          )}
        >
          <Database className="size-3.5" />
          Database
        </button>
      </div>

      {activeTab === "database" ? (
        <div className="mt-4">
          <DatabaseImportPanel online={online} onImported={onImported} />
        </div>
      ) : null}

      {activeTab === "file" ? (
        <>
          {!online ? (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-300">
          <AlertCircle className="size-4" />
          The backend is offline. Start it before importing files.
        </div>
      ) : null}

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <label className={labelClass} htmlFor="import-path">
            Source path
          </label>
          <div className="flex gap-2">
            <input
              id="import-path"
              className={cn(inputClass, "min-w-0 flex-1")}
              value={path}
              onChange={(event) => setPath(event.target.value)}
              placeholder="C:\data\customers.csv or data_warehouse\staging\events.json"
              spellCheck={false}
            />
            <Button
              type="button"
              variant="outline"
              className="h-9 shrink-0"
              onClick={() => void browseFile()}
              disabled={!online || picking}
            >
              {picking ? (
                <Loader2 className="animate-spin" />
              ) : (
                <FolderSearch />
              )}
              Browse…
            </Button>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground/70">
            Absolute paths are used as-is; relative paths resolve from the
            repository root.
          </p>
        </div>

        <div>
          <label className={labelClass} htmlFor="import-source-format">
            Source format
          </label>
          <select
            id="import-source-format"
            className={inputClass}
            value={sourceFormat}
            onChange={(event) =>
              setSourceFormat(event.target.value as "auto" | ImportSourceFormat)
            }
          >
            <option value="auto">Detect from extension</option>
            <option value="csv">CSV</option>
            <option value="json">JSON</option>
            <option value="parquet">Parquet</option>
            <option value="txt">Text (CSV)</option>
            <option value="orc">ORC</option>
            <option value="avro">Avro</option>
          </select>
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
                <span className="block text-[11px] font-medium">
                  {option.label}
                </span>
                <span className="block font-mono text-[9px] opacity-70">
                  {option.hint}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className={labelClass} htmlFor="import-namespace">
            Namespace
          </label>
          <input
            id="import-namespace"
            className={inputClass}
            value={namespace}
            onChange={(event) => setNamespace(event.target.value)}
            spellCheck={false}
          />
        </div>

        <div>
          <label className={labelClass} htmlFor="import-table-name">
            Table name (optional)
          </label>
          <input
            id="import-table-name"
            className={inputClass}
            value={tableName}
            onChange={(event) => setTableName(event.target.value)}
            placeholder="Derived from the file name"
            spellCheck={false}
          />
        </div>

        <div>
          <label className={labelClass} htmlFor="import-mode">
            If the table exists
          </label>
          <select
            id="import-mode"
            className={inputClass}
            value={mode}
            onChange={(event) => setMode(event.target.value as ImportMode)}
          >
            <option value="error">Fail the import</option>
            <option value="overwrite">Replace the table</option>
            <option value="append">Append rows</option>
          </select>
        </div>

        {csvMode ? (
          <div className="flex items-end gap-4 md:col-span-2">
            <label className="flex h-9 items-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                className="size-3.5 accent-primary"
                checked={hasHeader}
                onChange={(event) => setHasHeader(event.target.checked)}
              />
              First row is a header
            </label>
            <div className="w-28">
              <label className={labelClass} htmlFor="import-delimiter">
                Delimiter
              </label>
              <input
                id="import-delimiter"
                className={inputClass}
                value={delimiter}
                onChange={(event) => setDelimiter(event.target.value)}
                maxLength={4}
              />
            </div>
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="mt-4 flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-400" />
          <pre className="whitespace-pre-wrap break-words font-mono text-[11px] text-red-200/90">
            {error}
          </pre>
        </div>
      ) : null}

      {result ? (
        <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2.5">
          <div className="flex items-center gap-2 text-xs font-medium text-emerald-300">
            <CheckCircle2 className="size-4" />
            Imported {result.row_count.toLocaleString()} rows into{" "}
            <span className="font-mono">{result.table}</span>
          </div>
          <p className="mt-1 font-mono text-[10px] text-emerald-200/70">
            {result.table_format} · {result.columns.length} columns ·{" "}
            {Math.round(result.duration_ms).toLocaleString()} ms
          </p>
          {result.location ? (
            <p
              className="mt-1 truncate font-mono text-[10px] text-muted-foreground"
              title={result.location}
            >
              {result.location}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 flex items-center gap-2">
          <Button onClick={() => void submit()} disabled={running || !online}>
            {running ? <Loader2 className="animate-spin" /> : <Upload />}
            {running ? "Importing…" : "Import file"}
          </Button>
          <Button variant="ghost" onClick={onClose} disabled={running}>
            Cancel
          </Button>
          <span className="ml-auto text-[10px] text-muted-foreground/60">
            Tables appear in the catalog after a successful import.
          </span>
        </div>
      </>
    ) : null}
    </Card>
  );
}
