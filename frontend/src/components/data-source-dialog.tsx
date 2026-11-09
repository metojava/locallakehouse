import { useEffect, useMemo, useState } from "react";
import { Database, FileText, FolderSearch, Loader2, Table2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  getConfigConnectionDatabases,
  getConfigConnectionTables,
  getConfigConnections,
  getWorkspace,
  pickDataFile,
  type ConfigDatabaseConnection,
  type ConfigDatabaseTable,
  type WorkspaceEntry,
  type WorkspaceResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const DATA_EXTENSIONS = new Set([
  ".csv",
  ".tsv",
  ".json",
  ".jsonl",
  ".parquet",
  ".avro",
  ".orc",
  ".txt",
  ".text",
]);

interface DataFileEntry {
  name: string;
  path: string;
  extension: string;
}

function flattenDataFiles(
  entries: WorkspaceEntry[],
  out: DataFileEntry[] = [],
): DataFileEntry[] {
  for (const entry of entries) {
    if (entry.type === "directory") {
      flattenDataFiles(entry.children, out);
    } else if (entry.extension && DATA_EXTENSIONS.has(entry.extension)) {
      out.push({
        name: entry.name,
        path: entry.path,
        extension: entry.extension,
      });
    }
  }
  return out;
}

function quote(value: string): string {
  return JSON.stringify(value);
}

function fileSnippet(path: string): string {
  return `df = read_data_file(${quote(path)})\ndf.show(10)`;
}

function databaseSnippet(
  connectionId: string,
  table: ConfigDatabaseTable,
): string {
  return `df = read_database(${quote(connectionId)}, ${quote(table.name)}, database=${quote(table.schema)})\ndf.show(10)`;
}

function toErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return "The request failed.";
}

interface DataSourceDialogProps {
  open: boolean;
  online: boolean;
  onClose: () => void;
  onInsert: (snippet: string) => void;
}

export function DataSourceDialog({
  open,
  online,
  onClose,
  onInsert,
}: DataSourceDialogProps) {
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [manualPath, setManualPath] = useState("");
  const [picking, setPicking] = useState(false);

  const [connections, setConnections] = useState<ConfigDatabaseConnection[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [connectionId, setConnectionId] = useState("");
  const [databases, setDatabases] = useState<string[]>([]);
  const [database, setDatabase] = useState("");
  const [loadingDatabases, setLoadingDatabases] = useState(false);
  const [tables, setTables] = useState<ConfigDatabaseTable[]>([]);
  const [loadingTables, setLoadingTables] = useState(false);
  const [tableError, setTableError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let active = true;

    setLoadingFiles(true);
    setFileError(null);
    setManualPath("");
    getWorkspace()
      .then((next) => {
        if (active) setWorkspace(next);
      })
      .catch((err) => {
        if (active) setFileError(toErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoadingFiles(false);
      });

    setLoadingConnections(true);
    setConnectionError(null);
    getConfigConnections()
      .then((next) => {
        if (!active) return;
        setConnections(next);
        if (next.length > 0) {
          setConnectionId(next[0].id);
          setDatabase(next[0].database);
        } else {
          setConnectionId("");
          setDatabase("");
        }
      })
      .catch((err) => {
        if (active) setConnectionError(toErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoadingConnections(false);
      });

    return () => {
      active = false;
    };
  }, [open]);

  useEffect(() => {
    if (!open || !connectionId) {
      setDatabases([]);
      setTables([]);
      return;
    }
    let active = true;
    setLoadingDatabases(true);
    setTableError(null);
    getConfigConnectionDatabases(connectionId)
      .then((result) => {
        if (!active) return;
        setDatabases(result.databases);
        setDatabase((current) =>
          result.databases.includes(current)
            ? current
            : result.default || result.databases[0] || "",
        );
      })
      .catch((err) => {
        if (active) setTableError(toErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoadingDatabases(false);
      });
    return () => {
      active = false;
    };
  }, [open, connectionId]);

  useEffect(() => {
    if (!open || !connectionId || !database) {
      setTables([]);
      return;
    }
    let active = true;
    setLoadingTables(true);
    setTableError(null);
    getConfigConnectionTables(connectionId, database)
      .then((result) => {
        if (active) setTables(result.tables);
      })
      .catch((err) => {
        if (active) setTableError(toErrorMessage(err));
      })
      .finally(() => {
        if (active) setLoadingTables(false);
      });
    return () => {
      active = false;
    };
  }, [open, connectionId, database]);

  const files = useMemo(
    () => flattenDataFiles(workspace?.tree ?? []),
    [workspace],
  );

  if (!open) return null;

  const insert = (snippet: string) => {
    onInsert(snippet);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Load data"
        className="w-full max-w-2xl overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
      >
        <div className="flex items-center gap-2 border-b border-border/70 px-5 py-3">
          <Database className="size-4 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Load data into a new cell</p>
            <p className="text-[11px] text-muted-foreground">
              Read from a workspace file (logical path) or a table in a
              configured database.
            </p>
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose}>
            <X />
          </Button>
        </div>

        <div className="p-5">
          <Tabs defaultValue="files">
            <TabsList>
              <TabsTrigger value="files">
                <FolderSearch className="mr-1 size-3.5" />
                Files
              </TabsTrigger>
              <TabsTrigger value="database">
                <Database className="mr-1 size-3.5" />
                Database
              </TabsTrigger>
            </TabsList>

            <TabsContent value="files">
              <div className="flex flex-col gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-9 self-start"
                  disabled={!online || picking}
                  onClick={async () => {
                    setPicking(true);
                    setFileError(null);
                    try {
                      const result = await pickDataFile();
                      if (result.path) insert(fileSnippet(result.path));
                    } catch (err) {
                      setFileError(toErrorMessage(err));
                    } finally {
                      setPicking(false);
                    }
                  }}
                >
                  {picking ? <Loader2 className="animate-spin" /> : <FolderSearch />}
                  Browse file system…
                </Button>
              </div>

              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <input
                  value={manualPath}
                  onChange={(event) => setManualPath(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && manualPath.trim()) {
                      insert(fileSnippet(manualPath.trim()));
                    }
                  }}
                  placeholder="logical/path/data.csv or C:\\data\\file.parquet"
                  spellCheck={false}
                  className="h-9 min-w-0 flex-1 rounded-md border border-input bg-background/60 px-3 font-mono text-xs outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-primary/60 focus:ring-1 focus:ring-primary/30"
                />
                <Button
                  size="sm"
                  className="h-9"
                  onClick={() => insert(fileSnippet(manualPath.trim()))}
                  disabled={!manualPath.trim()}
                >
                  Use path
                </Button>
              </div>

              <p className="mt-1 text-[10px] text-muted-foreground">
                Browse picks any file on this machine. Relative paths resolve
                inside the open workspace folder. The list below shows only
                files in that folder.
              </p>

              {fileError ? (
                <p className="mt-2 text-xs text-red-300">{fileError}</p>
              ) : null}

              <div className="mt-3 max-h-64 overflow-auto rounded-lg border border-border/60">
                {loadingFiles ? (
                  <div className="flex items-center gap-2 px-3 py-4 text-xs text-muted-foreground">
                    <Loader2 className="size-3.5 animate-spin" />
                    Loading workspace files…
                  </div>
                ) : files.length === 0 ? (
                  <p className="px-3 py-4 text-xs text-muted-foreground">
                    {workspace?.root
                      ? "No CSV, TSV, JSON, or text files found in this folder. You can still type a logical or absolute path above."
                      : "No workspace folder is open. Type an absolute path above or open a folder in the Workspace view."}
                  </p>
                ) : (
                  files.map((file) => (
                    <button
                      key={file.path}
                      type="button"
                      onClick={() => insert(fileSnippet(file.path))}
                      className="flex w-full items-center gap-2 border-b border-border/40 px-3 py-2 text-left text-xs last:border-b-0 hover:bg-accent/60"
                      title={file.path}
                    >
                      <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                      <span className="truncate font-mono">{file.path}</span>
                      <span className="ml-auto shrink-0 text-[10px] uppercase text-muted-foreground/70">
                        {file.extension}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </TabsContent>

            <TabsContent value="database">
              {loadingConnections ? (
                <div className="flex items-center gap-2 px-1 py-4 text-xs text-muted-foreground">
                  <Loader2 className="size-3.5 animate-spin" />
                  Loading connections…
                </div>
              ) : connectionError ? (
                <p className="text-xs text-red-300">{connectionError}</p>
              ) : connections.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No connections found in databases.cfg. Add one on the
                  Databases page first.
                </p>
              ) : (
                <div className="space-y-3">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label className="flex flex-col gap-1 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                      Connection
                      <select
                        value={connectionId}
                        onChange={(event) => {
                          setConnectionId(event.target.value);
                          setDatabases([]);
                          setTables([]);
                          setDatabase("");
                        }}
                        className="h-8 rounded-md border border-input bg-background/60 px-2 text-xs normal-case tracking-normal text-foreground outline-none focus:border-primary/60"
                      >
                        {connections.map((item) => (
                          <option key={item.id} value={item.id}>
                            {item.name} ({item.dialect})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="flex flex-col gap-1 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                      Database
                      <select
                        value={database}
                        onChange={(event) => setDatabase(event.target.value)}
                        disabled={loadingDatabases || databases.length === 0}
                        className="h-8 rounded-md border border-input bg-background/60 px-2 text-xs normal-case tracking-normal text-foreground outline-none focus:border-primary/60 disabled:opacity-50"
                      >
                        {databases.length === 0 ? (
                          <option value="">
                            {loadingDatabases ? "Loading…" : "No databases"}
                          </option>
                        ) : (
                          databases.map((name) => (
                            <option key={name} value={name}>
                              {name}
                            </option>
                          ))
                        )}
                      </select>
                    </label>
                  </div>

                  {tableError ? (
                    <p className="text-xs text-red-300">{tableError}</p>
                  ) : null}

                  <div className="max-h-64 overflow-auto rounded-lg border border-border/60">
                    {loadingTables ? (
                      <div className="flex items-center gap-2 px-3 py-4 text-xs text-muted-foreground">
                        <Loader2 className="size-3.5 animate-spin" />
                        Loading tables…
                      </div>
                    ) : tables.length === 0 ? (
                      <p className="px-3 py-4 text-xs text-muted-foreground">
                        {database
                          ? "No tables found in this database."
                          : "Choose a database to list its tables."}
                      </p>
                    ) : (
                      tables.map((table) => (
                        <button
                          key={table.full_name}
                          type="button"
                          onClick={() =>
                            insert(
                              databaseSnippet(
                                connectionId,
                                table,
                              ),
                            )
                          }
                          className={cn(
                            "flex w-full items-center gap-2 border-b border-border/40 px-3 py-2 text-left text-xs last:border-b-0 hover:bg-accent/60",
                          )}
                          title={table.full_name}
                        >
                          <Table2 className="size-3.5 shrink-0 text-muted-foreground" />
                          <span className="truncate font-mono">
                            {table.full_name}
                          </span>
                        </button>
                      ))
                    )}
                  </div>

                  <p className="text-[10px] text-muted-foreground">
                    Inserts{" "}
                    <span className="font-mono">read_database(connection, table, database)</span>{" "}
                    — credentials stay in the backend config.
                  </p>
                </div>
              )}
            </TabsContent>
          </Tabs>

          {!online ? (
            <p className="mt-3 text-[10px] text-amber-300/80">
              The backend is offline. Start it before loading data.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
