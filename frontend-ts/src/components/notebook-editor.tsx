import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import ReactMarkdown from "react-markdown";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Check,
  Code2,
  Database,
  Loader2,
  Play,
  Plus,
  RotateCcw,
  Save,
  SquarePen,
  TextCursorInput,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataSourceDialog } from "@/components/data-source-dialog";
import {
  EDITOR_THEMES,
  useEditorPrefs,
  type EditorTheme,
} from "@/lib/editor-prefs";
import type {
  ExecutePySparkResponse,
  NotebookCellDocument,
  NotebookDocumentResponse,
} from "@/lib/api";
import {
  executeNotebookCell,
  getKernels,
  installJavaKernel,
  resetNotebookKernel,
  type KernelInfo,
} from "@/lib/api";
import { cn, stringifyCell } from "@/lib/utils";

interface NotebookEditorProps {
  notebook: NotebookDocumentResponse;
  onChange: (notebook: NotebookDocumentResponse) => void;
  onSave: () => void;
  saving: boolean;
  dirty: boolean;
  online: boolean;
}

function makeCell(type: "code" | "markdown"): NotebookCellDocument {
  return {
    id: `cell-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type,
    source: "",
    outputs: [],
  };
}

function toErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return "The cell failed to execute.";
}

function AutoTextArea({
  value,
  onChange,
  onRun,
  placeholder,
  minHeight = 70,
  fontSize,
  theme,
}: {
  value: string;
  onChange: (value: string) => void;
  onRun: () => void;
  placeholder?: string;
  minHeight?: number;
  fontSize: number;
  theme: EditorTheme;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.max(el.scrollHeight, minHeight)}px`;
  }, [value, minHeight]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      onRun();
      return;
    }
    if (event.key === "Tab") {
      event.preventDefault();
      const target = event.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      onChange(`${value.slice(0, start)}  ${value.slice(end)}`);
      window.requestAnimationFrame(() => {
        if (ref.current) {
          ref.current.selectionStart = start + 2;
          ref.current.selectionEnd = start + 2;
        }
      });
    }
  };

  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={handleKeyDown}
      spellCheck={false}
      placeholder={placeholder}
      className={cn(
        "w-full resize-none overflow-hidden px-4 py-3 font-mono outline-none",
        EDITOR_THEMES[theme].placeholder,
      )}
      style={{
        fontSize,
        lineHeight: `${Math.round(fontSize * 1.6)}px`,
        backgroundColor: EDITOR_THEMES[theme].background,
        color: EDITOR_THEMES[theme].color,
        caretColor: EDITOR_THEMES[theme].color,
      }}
    />
  );
}

function ResultTable({ result }: { result: ExecutePySparkResponse }) {
  if (!result.columns.length || !result.rows.length) return null;
  return (
    <div className="max-h-[280px] overflow-auto rounded-md border border-border/60">
      <table className="w-full min-w-max border-collapse text-left text-[12px]">
        <thead>
          <tr className="border-b border-border/70 bg-muted text-[10px] uppercase tracking-wide text-muted-foreground">
            {result.columns.map((column) => (
              <th
                key={column.name}
                className="whitespace-nowrap px-3 py-1.5 font-medium"
              >
                {column.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, index) => (
            <tr key={index} className="border-b border-border/30 last:border-0">
              {result.columns.map((column) => (
                <td
                  key={column.name}
                  className="max-w-[360px] truncate whitespace-nowrap px-3 py-1.5 font-mono text-foreground/85"
                  title={stringifyCell(row[column.name])}
                >
                  {row[column.name] === null || row[column.name] === undefined
                    ? "NULL"
                    : stringifyCell(row[column.name])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CellOutputs({
  cell,
  result,
  error,
  running,
}: {
  cell: NotebookCellDocument;
  result: ExecutePySparkResponse | null;
  error: string | null;
  running: boolean;
}) {
  const hasSavedOutputs = cell.outputs.length > 0;

  if (running) {
    return (
      <div className="flex items-center gap-2 border-t border-border/50 bg-muted/10 px-4 py-2 text-xs text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin text-primary" />
        Running on Spark…
      </div>
    );
  }

  if (error) {
    return (
      <div className="border-t border-destructive/30 bg-destructive/10 px-4 py-3">
        <pre className="max-h-[280px] overflow-auto whitespace-pre-wrap break-words font-mono text-[11.5px] leading-5 text-red-300">
          {error}
        </pre>
      </div>
    );
  }

  if (result) {
    const hasText =
      Boolean(result.stdout.trim()) ||
      Boolean(result.stderr.trim()) ||
      Boolean(result.result_repr);
    if (!hasText && !result.rows.length) return null;
    return (
      <div className="space-y-2 border-t border-border/50 bg-muted/10 px-4 py-3">
        {result.result_repr ? (
          <pre className="whitespace-pre-wrap break-words font-mono text-[12px] text-emerald-300">
            {result.result_repr}
          </pre>
        ) : null}
        {result.stdout.trim() ? (
          <pre className="max-h-[240px] overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-5 text-foreground/85">
            {result.stdout}
          </pre>
        ) : null}
        {result.stderr.trim() ? (
          <pre className="max-h-[240px] overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-5 text-red-300">
            {result.stderr}
          </pre>
        ) : null}
        <ResultTable result={result} />
        {result.row_count > 0 ? (
          <p className="text-[10px] text-muted-foreground">
            {result.row_count} row{result.row_count === 1 ? "" : "s"} ·{" "}
            {result.execution_time_ms.toFixed(0)} ms
          </p>
        ) : null}
      </div>
    );
  }

  if (hasSavedOutputs) {
    return (
      <div className="space-y-2 border-t border-border/50 bg-muted/10 px-4 py-3">
        {cell.outputs.map((output, index) => (
          <pre
            key={index}
            className={cn(
              "max-h-[240px] overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-5",
              output.kind === "error" ? "text-red-300" : "text-foreground/85",
            )}
          >
            {output.text}
          </pre>
        ))}
      </div>
    );
  }

  return null;
}

export function NotebookEditor({
  notebook,
  onChange,
  onSave,
  saving,
  dirty,
  online,
}: NotebookEditorProps) {
  const [runningCell, setRunningCell] = useState<string | null>(null);
  const [runningAll, setRunningAll] = useState(false);
  const [editingMarkdown, setEditingMarkdown] = useState<Set<string>>(
    () => new Set(),
  );
  const [results, setResults] = useState<Record<string, ExecutePySparkResponse>>(
    {},
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const { fontSize, theme } = useEditorPrefs();
  const [dataSourceOpen, setDataSourceOpen] = useState(false);
  const [kernels, setKernels] = useState<KernelInfo[]>([]);
  const [javaInstalled, setJavaInstalled] = useState(true);
  const [installingJava, setInstallingJava] = useState(false);

  const loadKernels = useCallback(async () => {
    if (!online) return;
    try {
      const response = await getKernels();
      setKernels(response.kernels);
      setJavaInstalled(response.java_installed);
    } catch {
      // kernel list is optional; the built-in PySpark kernel always works
    }
  }, [online]);

  useEffect(() => {
    void loadKernels();
  }, [loadKernels, notebook.path]);

  const selectKernel = useCallback(
    (kernelName: string) => {
      const info = kernels.find((item) => item.name === kernelName);
      onChange({
        ...notebook,
        kernel_name: kernelName,
        kernel_display_name: info?.display_name ?? kernelName,
        kernel_language: info?.language ?? "python",
      });
    },
    [kernels, notebook, onChange],
  );

  const installJava = useCallback(async () => {
    setInstallingJava(true);
    setNotice(null);
    try {
      const result = await installJavaKernel();
      setNotice(result.message);
      await loadKernels();
    } catch (err) {
      setNotice(
        `Could not install the Java kernel: ${
          err instanceof Error ? err.message : "unknown error"
        }`,
      );
    } finally {
      setInstallingJava(false);
    }
  }, [loadKernels]);

  const busy = runningCell !== null || runningAll;

  useEffect(() => {
    setResults({});
    setErrors({});
    setEditingMarkdown(new Set());
    setNotice(null);
  }, [notebook.path]);

  const updateCells = useCallback(
    (cells: NotebookCellDocument[]) => {
      onChange({ ...notebook, cells });
    },
    [notebook, onChange],
  );

  const updateCell = useCallback(
    (cellId: string, patch: Partial<NotebookCellDocument>) => {
      updateCells(
        notebook.cells.map((cell) =>
          cell.id === cellId ? { ...cell, ...patch } : cell,
        ),
      );
    },
    [notebook.cells, updateCells],
  );

  const runCell = useCallback(
    async (cell: NotebookCellDocument) => {
      if (!online || cell.type !== "code" || !cell.source.trim()) return;
      setRunningCell(cell.id);
      setErrors((prev) => {
        const next = { ...prev };
        delete next[cell.id];
        return next;
      });
      try {
        const result = await executeNotebookCell(notebook.path, cell.source, {
          kernelName: notebook.kernel_name,
        });
        setResults((prev) => ({ ...prev, [cell.id]: result }));
      } catch (err) {
        setResults((prev) => {
          const next = { ...prev };
          delete next[cell.id];
          return next;
        });
        setErrors((prev) => ({ ...prev, [cell.id]: toErrorMessage(err) }));
      } finally {
        setRunningCell(null);
      }
    },
    [notebook.path, online],
  );

  const runAll = useCallback(async () => {
    if (!online || busy) return;
    setRunningAll(true);
    setNotice(null);
    for (const cell of notebook.cells) {
      if (cell.type !== "code" || !cell.source.trim()) continue;
      setRunningCell(cell.id);
      try {
        const result = await executeNotebookCell(notebook.path, cell.source, {
          kernelName: notebook.kernel_name,
        });
        setResults((prev) => ({ ...prev, [cell.id]: result }));
        setErrors((prev) => {
          const next = { ...prev };
          delete next[cell.id];
          return next;
        });
      } catch (err) {
        setResults((prev) => {
          const next = { ...prev };
          delete next[cell.id];
          return next;
        });
        setErrors((prev) => ({ ...prev, [cell.id]: toErrorMessage(err) }));
        break;
      }
    }
    setRunningCell(null);
    setRunningAll(false);
  }, [busy, notebook.cells, notebook.path, online]);

  const addCell = useCallback(
    (type: "code" | "markdown", index?: number) => {
      const cell = makeCell(type);
      const cells = [...notebook.cells];
      const position = index ?? cells.length;
      cells.splice(position, 0, cell);
      updateCells(cells);
      if (type === "markdown") {
        setEditingMarkdown((prev) => new Set(prev).add(cell.id));
      }
    },
    [notebook.cells, updateCells],
  );

  const insertDataSourceCell = useCallback(
    (source: string) => {
      const cell = { ...makeCell("code"), source };
      updateCells([...notebook.cells, cell]);
    },
    [notebook.cells, updateCells],
  );

  const removeCell = useCallback(
    (cellId: string) => {
      updateCells(notebook.cells.filter((cell) => cell.id !== cellId));
      setResults((prev) => {
        const next = { ...prev };
        delete next[cellId];
        return next;
      });
      setErrors((prev) => {
        const next = { ...prev };
        delete next[cellId];
        return next;
      });
    },
    [notebook.cells, updateCells],
  );

  const moveCell = useCallback(
    (cellId: string, direction: -1 | 1) => {
      const index = notebook.cells.findIndex((cell) => cell.id === cellId);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= notebook.cells.length) return;
      const cells = [...notebook.cells];
      const [cell] = cells.splice(index, 1);
      cells.splice(target, 0, cell);
      updateCells(cells);
    },
    [notebook.cells, updateCells],
  );

  const resetKernel = useCallback(async () => {
    try {
      const result = await resetNotebookKernel(notebook.path);
      setResults({});
      setErrors({});
      setNotice(
        result.existed
          ? "Kernel reset. Variables from previous cells were cleared."
          : "Kernel was already fresh.",
      );
    } catch (err) {
      setNotice(toErrorMessage(err));
    }
  }, [notebook.path]);

  const codeCount = useMemo(
    () => notebook.cells.filter((cell) => cell.type === "code").length,
    [notebook.cells],
  );

  return (
    <div className="animate-fade-in space-y-4">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/70 bg-card/60 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <Badge variant="info">Notebook</Badge>
          <span className="truncate text-sm font-medium" title={notebook.path}>
            {notebook.name}
          </span>
          {dirty ? <Badge variant="warning">unsaved</Badge> : null}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Kernel
            </span>
            <select
              value={notebook.kernel_name}
              onChange={(event) => selectKernel(event.target.value)}
              disabled={busy}
              className="h-7 max-w-[220px] rounded border border-input bg-background/60 px-1.5 text-[11px] text-foreground outline-none focus-visible:ring-1 focus-visible:ring-ring"
              title="Language kernel for this notebook"
            >
              {[
                ...kernels,
                ...(kernels.some((item) => item.name === notebook.kernel_name)
                  ? []
                  : [
                      {
                        name: notebook.kernel_name,
                        display_name: `${notebook.kernel_display_name} (not installed)`,
                        language: notebook.kernel_language,
                        builtin: false,
                      },
                    ]),
              ].map((item) => (
                <option key={item.name} value={item.name}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </div>
          {!javaInstalled ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => void installJava()}
              disabled={installingJava || !online}
              title="Download and register the IJava Java kernel"
            >
              {installingJava ? <Loader2 className="animate-spin" /> : <Plus />}
              Install Java kernel
            </Button>
          ) : null}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDataSourceOpen(true)}
            disabled={busy}
            title="Load data from a file or database"
          >
            <Database />
            Data source
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void resetKernel()}
            disabled={busy || !online}
          >
            <RotateCcw />
            Reset kernel
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => addCell("code")}
            disabled={busy}
          >
            <Plus />
            Code
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => addCell("markdown")}
            disabled={busy}
          >
            <TextCursorInput />
            Markdown
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void runAll()}
            disabled={busy || !online || codeCount === 0}
          >
            {runningAll ? <Loader2 className="animate-spin" /> : <Play />}
            Run all
          </Button>
          <Button size="sm" onClick={onSave} disabled={saving || !dirty}>
            {saving ? <Loader2 className="animate-spin" /> : <Save />}
            Save
          </Button>
        </div>
      </div>

      {notice ? (
        <div className="flex items-center gap-2 rounded-lg border border-border/70 bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
          <Check className="size-3.5 text-emerald-400" />
          {notice}
        </div>
      ) : null}

      <div className="space-y-3">
        {notebook.cells.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border/70 px-6 py-10 text-center text-sm text-muted-foreground">
            This notebook is empty. Add a code or markdown cell to get started.
          </div>
        ) : null}

        {notebook.cells.map((cell, index) => {
          const isRunningCell = runningCell === cell.id;
          const isMarkdownEditing = editingMarkdown.has(cell.id);
          return (
            <div
              key={cell.id}
              className={cn(
                "overflow-hidden rounded-xl border border-border/70 bg-card/70 shadow-sm",
                isRunningCell && "ring-1 ring-primary/40",
              )}
            >
              <div className="flex items-center gap-2 border-b border-border/50 bg-muted/20 px-3 py-1.5">
                <span className="font-mono text-[10px] text-muted-foreground">
                  [{index + 1}]
                </span>
                <Badge
                  variant={cell.type === "code" ? "secondary" : "outline"}
                  className="text-[9px]"
                >
                  {cell.type === "code" ? (
                    <>
                      <Code2 className="mr-1 size-2.5" /> code
                    </>
                  ) : (
                    "markdown"
                  )}
                </Badge>
                <div className="ml-auto flex items-center gap-1">
                  {cell.type === "markdown" ? (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title={isMarkdownEditing ? "Preview" : "Edit markdown"}
                      onClick={() =>
                        setEditingMarkdown((prev) => {
                          const next = new Set(prev);
                          if (next.has(cell.id)) next.delete(cell.id);
                          else next.add(cell.id);
                          return next;
                        })
                      }
                    >
                      {isMarkdownEditing ? (
                        <Check />
                      ) : (
                        <SquarePen />
                      )}
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title="Run cell (Ctrl/Cmd + Enter)"
                      onClick={() => void runCell(cell)}
                      disabled={busy || !online || !cell.source.trim()}
                    >
                      {isRunningCell ? (
                        <Loader2 className="animate-spin text-primary" />
                      ) : (
                        <Play />
                      )}
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title="Move up"
                    onClick={() => moveCell(cell.id, -1)}
                    disabled={busy || index === 0}
                  >
                    <ArrowUp />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title="Move down"
                    onClick={() => moveCell(cell.id, 1)}
                    disabled={busy || index === notebook.cells.length - 1}
                  >
                    <ArrowDown />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title="Delete cell"
                    onClick={() => removeCell(cell.id)}
                    disabled={busy}
                  >
                    <Trash2 />
                  </Button>
                </div>
              </div>

              {cell.type === "markdown" ? (
                isMarkdownEditing ? (
                  <AutoTextArea
                    value={cell.source}
                    onChange={(source) => updateCell(cell.id, { source })}
                    onRun={() =>
                      setEditingMarkdown((prev) => {
                        const next = new Set(prev);
                        next.delete(cell.id);
                        return next;
                      })
                    }
                    placeholder="Write markdown…"
                    minHeight={80}
                    fontSize={fontSize}
                    theme={theme}
                  />
                ) : (
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() =>
                      setEditingMarkdown((prev) =>
                        new Set(prev).add(cell.id),
                      )
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        setEditingMarkdown((prev) =>
                          new Set(prev).add(cell.id),
                        );
                      }
                    }}
                    className="markdown-body cursor-text px-4 py-3 text-sm leading-6 text-foreground/90"
                  >
                    {cell.source.trim() ? (
                      <ReactMarkdown>{cell.source}</ReactMarkdown>
                    ) : (
                      <span className="text-muted-foreground/60">
                        Empty markdown cell. Click to edit.
                      </span>
                    )}
                  </div>
                )
              ) : (
                <AutoTextArea
                  value={cell.source}
                  onChange={(source) => updateCell(cell.id, { source })}
                  onRun={() => void runCell(cell)}
                  placeholder="df = spark.range(100)"
                  fontSize={fontSize}
                  theme={theme}
                />
              )}

              {cell.type === "code" ? (
                <CellOutputs
                  cell={cell}
                  result={results[cell.id] ?? null}
                  error={errors[cell.id] ?? null}
                  running={isRunningCell}
                />
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-border/60 px-4 py-2">
        <Button variant="ghost" size="sm" onClick={() => addCell("code")}>
          <Plus />
          Add code cell
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => addCell("markdown")}
        >
          <Plus />
          Add markdown cell
        </Button>
        <span className="ml-auto text-[10px] text-muted-foreground/70">
          Cells share one kernel: variables persist between runs.
        </span>
      </div>

      {!online ? (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-300">
          <AlertTriangle className="size-3.5" />
          The backend is offline. Start it to run notebook cells.
        </div>
      ) : null}

      <DataSourceDialog
        open={dataSourceOpen}
        online={online}
        onClose={() => setDataSourceOpen(false)}
        onInsert={insertDataSourceCell}
      />
    </div>
  );
}
