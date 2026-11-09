import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Braces,
  ChevronDown,
  ChevronRight,
  Database,
  FileCode,
  FilePlus,
  FileText,
  Folder,
  FolderOpen,
  FolderTree,
  Loader2,
  RefreshCw,
  Save,
  Table2,
  X,
} from "lucide-react";

import { NotebookEditor } from "@/components/notebook-editor";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ApiError,
  closeWorkspace,
  createWorkspaceNotebook,
  getWorkspace,
  getWorkspaceFile,
  getWorkspaceNotebook,
  openWorkspacePicker,
  saveWorkspaceFile,
  setWorkspaceRoot,
  type NotebookDocumentResponse,
  type WorkspaceEntry,
  type WorkspaceResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function toErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "The request failed.";
}

function fileIcon(entry: WorkspaceEntry) {
  if (entry.type === "directory") return Folder;
  switch (entry.extension) {
    case ".ipynb":
      return BookOpen;
    case ".py":
      return FileCode;
    case ".json":
    case ".jsonl":
      return Braces;
    case ".csv":
    case ".tsv":
      return Table2;
    case ".sql":
      return Database;
    default:
      return FileText;
  }
}

function notebookId(notebook: NotebookDocumentResponse): string {
  return notebook.path;
}

function serializeNotebook(notebook: NotebookDocumentResponse): string {
  const payload = {
    cells: notebook.cells.map((cell) =>
      cell.type === "code"
        ? {
            cell_type: "code",
            execution_count: null,
            metadata: {},
            outputs: [],
            source: cell.source,
          }
        : {
            cell_type: "markdown",
            metadata: {},
            source: cell.source,
          },
    ),
    metadata: {
      kernelspec: {
        display_name: notebook.kernel_display_name || "Python 3 (PySpark)",
        language: notebook.kernel_language || "python",
        name: notebook.kernel_name || "python3",
      },
      language_info: { name: notebook.kernel_language || "python" },
    },
    nbformat: notebook.nbformat ?? 4,
    nbformat_minor: notebook.nbformat_minor ?? 5,
  };
  return JSON.stringify(payload, null, 2);
}

interface EntryNodeProps {
  entry: WorkspaceEntry;
  depth: number;
  expanded: Set<string>;
  activePath: string | null;
  onToggle: (path: string) => void;
  onSelect: (entry: WorkspaceEntry) => void;
}

function EntryNode({
  entry,
  depth,
  expanded,
  activePath,
  onToggle,
  onSelect,
}: EntryNodeProps) {
  const isDirectory = entry.type === "directory";
  const isOpen = expanded.has(entry.path);
  const active = activePath === entry.path;
  const Icon = isDirectory ? (isOpen ? FolderOpen : Folder) : fileIcon(entry);

  return (
    <div>
      <button
        type="button"
        onClick={() => (isDirectory ? onToggle(entry.path) : onSelect(entry))}
        className={cn(
          "flex w-full items-center gap-1.5 rounded-md py-1 pr-2 text-left text-[13px] transition-colors",
          active
            ? "bg-primary/10 text-primary ring-1 ring-inset ring-primary/25"
            : "text-foreground/80 hover:bg-accent/60 hover:text-foreground",
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        title={entry.path}
      >
        {isDirectory ? (
          isOpen ? (
            <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
          )
        ) : (
          <span className="w-3.5 shrink-0" />
        )}
        <Icon
          className={cn(
            "size-3.5 shrink-0",
            isDirectory ? "text-amber-300/80" : "text-muted-foreground",
          )}
        />
        <span className="truncate">{entry.name}</span>
      </button>
      {isDirectory && isOpen && entry.children.length > 0 ? (
        <div>
          {entry.children.map((child) => (
            <EntryNode
              key={child.path}
              entry={child}
              depth={depth + 1}
              expanded={expanded}
              activePath={activePath}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function WorkspacePage({ online }: { online: boolean }) {
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [rootInput, setRootInput] = useState("");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<null | "open" | "browse" | "refresh">(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [activePath, setActivePath] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [textName, setTextName] = useState("");
  const [textLanguage, setTextLanguage] = useState("text");
  const [textContent, setTextContent] = useState("");
  const [savedText, setSavedText] = useState("");
  const [savingText, setSavingText] = useState(false);

  const [notebook, setNotebook] = useState<NotebookDocumentResponse | null>(null);
  const [savedNotebook, setSavedNotebook] = useState("");
  const [savingNotebook, setSavingNotebook] = useState(false);
  const [creatingNotebook, setCreatingNotebook] = useState(false);

  const textDirty = activePath !== null && notebook === null && textContent !== savedText;
  const notebookDirty = useMemo(
    () => (notebook ? serializeNotebook(notebook) !== savedNotebook : false),
    [notebook, savedNotebook],
  );
  const dirty = textDirty || notebookDirty;

  const applyWorkspace = useCallback((next: WorkspaceResponse) => {
    setWorkspace(next);
    setRootInput(next.root ?? "");
    setExpanded(new Set(next.tree.map((entry) => entry.path)));
  }, []);

  const refresh = useCallback(
    async (mode: "refresh" | "open" | "browse" = "refresh") => {
      setBusy(mode);
      setError(null);
      try {
        const next =
          mode === "browse" ? await openWorkspacePicker() : await getWorkspace();
        applyWorkspace(next);
        if (mode === "browse" && next.root) {
          setNotice(`Opened ${next.root}`);
        }
      } catch (err) {
        setError(toErrorMessage(err));
      } finally {
        setBusy(null);
        setLoading(false);
      }
    },
    [applyWorkspace],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const confirmDiscard = useCallback(() => {
    if (!dirty) return true;
    return window.confirm(
      "You have unsaved changes in the current file. Discard them and continue?",
    );
  }, [dirty]);

  const resetFileState = useCallback(() => {
    setNotebook(null);
    setTextContent("");
    setSavedText("");
    setTextName("");
    setTextLanguage("text");
    setActivePath(null);
  }, []);

  const openEntry = useCallback(
    async (entry: WorkspaceEntry) => {
      if (entry.type === "directory") return;
      if (!confirmDiscard()) return;
      setError(null);
      setNotice(null);
      setFileLoading(true);
      resetFileState();
      setActivePath(entry.path);
      try {
        if (entry.extension === ".ipynb") {
          const doc = await getWorkspaceNotebook(entry.path);
          setNotebook(doc);
          setSavedNotebook(serializeNotebook(doc));
          setActivePath(doc.path);
        } else {
          const file = await getWorkspaceFile(entry.path);
          setTextName(file.name);
          setTextLanguage(file.language);
          setTextContent(file.content);
          setSavedText(file.content);
          setActivePath(file.path);
        }
      } catch (err) {
        setError(toErrorMessage(err));
        setActivePath(null);
      } finally {
        setFileLoading(false);
      }
    },
    [confirmDiscard, resetFileState],
  );

  const toggleDirectory = useCallback((path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const saveText = useCallback(async () => {
    if (!activePath) return;
    setSavingText(true);
    setError(null);
    try {
      await saveWorkspaceFile(activePath, textContent);
      setSavedText(textContent);
      setNotice(`Saved ${textName}`);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setSavingText(false);
    }
  }, [activePath, textContent, textName]);

  const saveNotebook = useCallback(async () => {
    if (!notebook) return;
    setSavingNotebook(true);
    setError(null);
    try {
      const serialized = serializeNotebook(notebook);
      await saveWorkspaceFile(notebook.path, serialized);
      setSavedNotebook(serialized);
      setNotice(`Saved ${notebook.name}`);
      void refresh();
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setSavingNotebook(false);
    }
  }, [notebook, refresh]);

  const createNotebook = useCallback(async () => {
    if (!workspace?.root) return;
    if (!confirmDiscard()) return;
    const name = window.prompt(
      "New notebook name (relative to the workspace folder)",
      "untitled.ipynb",
    );
    if (name === null || !name.trim()) return;
    setCreatingNotebook(true);
    setError(null);
    setNotice(null);
    try {
      const doc = await createWorkspaceNotebook(name.trim());
      resetFileState();
      setNotebook(doc);
      setSavedNotebook(serializeNotebook(doc));
      setActivePath(doc.path);
      setNotice(`Created ${doc.name}`);
      void refresh();
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setCreatingNotebook(false);
    }
  }, [confirmDiscard, refresh, resetFileState, workspace?.root]);

  const openManual = useCallback(async () => {
    if (!rootInput.trim()) return;
    if (!confirmDiscard()) return;
    setBusy("open");
    setError(null);
    try {
      const next = await setWorkspaceRoot(rootInput.trim());
      applyWorkspace(next);
      resetFileState();
      setNotice(`Opened ${next.root}`);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }, [applyWorkspace, confirmDiscard, resetFileState, rootInput]);

  const closeFolder = useCallback(async () => {
    if (!confirmDiscard()) return;
    try {
      const next = await closeWorkspace();
      applyWorkspace(next);
      resetFileState();
      setNotice(null);
    } catch (err) {
      setError(toErrorMessage(err));
    }
  }, [applyWorkspace, confirmDiscard, resetFileState]);

  const totalFiles = useMemo(() => {
    let count = 0;
    const walk = (entries: WorkspaceEntry[]) => {
      for (const entry of entries) {
        if (entry.type === "file") count += 1;
        else walk(entry.children);
      }
    };
    walk(workspace?.tree ?? []);
    return count;
  }, [workspace]);

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow="Files"
        title="Workspace"
        description="Open any folder on this machine, browse it in the explorer, edit text files, and run Jupyter notebooks against the local Spark session."
        actions={
          <>
            <Badge variant="info">PySpark kernels</Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void createNotebook()}
              disabled={
                !online ||
                !workspace?.root ||
                busy !== null ||
                creatingNotebook
              }
              title="Create a new notebook in the workspace folder"
            >
              {creatingNotebook ? (
                <Loader2 className="animate-spin" />
              ) : (
                <FilePlus />
              )}
              New notebook
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void refresh("refresh")}
              disabled={loading || !online || busy !== null}
            >
              <RefreshCw className={cn(busy === "refresh" && "animate-spin")} />
              Refresh
            </Button>
          </>
        }
      />

      <Card>
        <CardContent className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <FolderTree className="size-4 text-primary" />
            <span className="hidden sm:inline">Folder</span>
          </div>
          <input
            value={rootInput}
            onChange={(event) => setRootInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void openManual();
            }}
            placeholder="C:\\path\\to\\your\\project"
            spellCheck={false}
            className="h-9 min-w-0 flex-1 rounded-md border border-input bg-background/60 px-3 font-mono text-xs outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-primary/60 focus:ring-1 focus:ring-primary/30"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-9"
              onClick={() => void refresh("browse")}
              disabled={!online || busy !== null}
            >
              {busy === "browse" ? (
                <Loader2 className="animate-spin" />
              ) : (
                <FolderOpen />
              )}
              Browse…
            </Button>
            <Button
              size="sm"
              className="h-9"
              onClick={() => void openManual()}
              disabled={!online || busy !== null || !rootInput.trim()}
            >
              {busy === "open" ? <Loader2 className="animate-spin" /> : <FolderOpen />}
              Open
            </Button>
            {workspace?.root ? (
              <Button
                variant="ghost"
                size="sm"
                className="h-9"
                onClick={() => void closeFolder()}
                title="Close folder"
              >
                <X />
                Close
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-red-300">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span className="whitespace-pre-wrap">{error}</span>
        </div>
      ) : null}

      {notice ? (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-300">
          {notice}
        </div>
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 px-2 py-8 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading workspace…
        </div>
      ) : !workspace?.root ? (
        <div className="rounded-xl border border-dashed border-border/70 px-6 py-14 text-center">
          <div className="mx-auto mb-3 grid size-12 place-items-center rounded-2xl bg-muted/60 text-muted-foreground">
            <FolderTree className="size-5" />
          </div>
          <p className="text-sm font-medium">No folder is open</p>
          <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
            Choose a folder with scripts, CSV files, or Jupyter notebooks. The
            folder is opened by the local backend, so it must exist on this
            machine.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
          <Card className="overflow-hidden">
            <div className="flex items-center gap-2 border-b border-border/70 px-4 py-3">
              <FolderOpen className="size-4 text-primary" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {workspace.name ?? "Workspace"}
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {totalFiles} file{totalFiles === 1 ? "" : "s"}
                  {workspace.truncated ? " · truncated" : ""}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="size-7 shrink-0 p-0"
                onClick={() => void createNotebook()}
                disabled={creatingNotebook || busy !== null}
                title="New notebook"
              >
                {creatingNotebook ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <FilePlus />
                )}
              </Button>
            </div>
            <div className="max-h-[68vh] overflow-auto p-2">
              {workspace.tree.length === 0 ? (
                <p className="px-2 py-4 text-xs text-muted-foreground">
                  No supported files found in this folder.
                </p>
              ) : (
                workspace.tree.map((entry) => (
                  <EntryNode
                    key={entry.path}
                    entry={entry}
                    depth={0}
                    expanded={expanded}
                    activePath={activePath}
                    onToggle={toggleDirectory}
                    onSelect={(item) => void openEntry(item)}
                  />
                ))
              )}
            </div>
            <div className="border-t border-border/60 px-4 py-2">
              <p className="truncate font-mono text-[10px] text-muted-foreground/70" title={workspace.root}>
                {workspace.root}
              </p>
            </div>
          </Card>

          <div className="min-w-0">
            {fileLoading ? (
              <Card>
                <CardContent className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" />
                  Opening file…
                </CardContent>
              </Card>
            ) : notebook ? (
              <NotebookEditor
                key={notebookId(notebook)}
                notebook={notebook}
                onChange={setNotebook}
                onSave={() => void saveNotebook()}
                saving={savingNotebook}
                dirty={notebookDirty}
                online={online}
              />
            ) : activePath ? (
              <Card className="overflow-hidden">
                <div className="flex flex-wrap items-center gap-2 border-b border-border/70 px-4 py-3">
                  <FileText className="size-4 text-primary" />
                  <span className="truncate text-sm font-medium" title={activePath}>
                    {textName}
                  </span>
                  <Badge variant="outline" className="text-[9px] uppercase">
                    {textLanguage}
                  </Badge>
                  {textDirty ? <Badge variant="warning">unsaved</Badge> : null}
                  <Button
                    size="sm"
                    className="ml-auto"
                    onClick={() => void saveText()}
                    disabled={savingText || !textDirty}
                  >
                    {savingText ? <Loader2 className="animate-spin" /> : <Save />}
                    Save
                  </Button>
                </div>
                <textarea
                  value={textContent}
                  onChange={(event) => setTextContent(event.target.value)}
                  spellCheck={false}
                  className="h-[62vh] w-full resize-none bg-card px-4 py-3 font-mono text-[13px] leading-6 text-foreground outline-none"
                />
                <div className="flex items-center justify-between border-t border-border/60 px-4 py-2 text-[10px] text-muted-foreground">
                  <span className="truncate font-mono" title={activePath}>
                    {activePath}
                  </span>
                  <span>{textContent.split("\n").length} lines</span>
                </div>
              </Card>
            ) : (
              <Card>
                <CardContent className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
                  <div className="grid size-11 place-items-center rounded-2xl bg-muted/60 text-muted-foreground">
                    <FileText className="size-5" />
                  </div>
                  <p className="text-sm font-medium">Select a file</p>
                  <p className="max-w-sm text-xs text-muted-foreground">
                    Pick a text file to edit it, or open a{" "}
                    <span className="font-mono">.ipynb</span> notebook to run
                    cells with a shared PySpark kernel.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
