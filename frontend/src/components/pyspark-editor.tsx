import { Loader2, Play, RotateCcw, Sparkles, Terminal } from "lucide-react";

import { BufferTabs } from "@/components/buffer-tabs";
import { CodeEditor } from "@/components/code-editor";
import { PageHeader } from "@/components/page-header";
import { ResultsPanel } from "@/components/results";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ExecutePySparkResponse } from "@/lib/api";
import type { EditorBuffers } from "@/lib/editor-buffers";
import { DEFAULT_PYSPARK, PYSPARK_SAMPLES } from "@/lib/samples";

interface PySparkEditorProps {
  tabs: EditorBuffers;
  script: string;
  onScriptChange: (script: string) => void;
  onRun: () => void;
  running: boolean;
  result: ExecutePySparkResponse | null;
  error: string | null;
}

export function PySparkEditor({
  tabs,
  script,
  onScriptChange,
  onRun,
  running,
  result,
  error,
}: PySparkEditorProps) {
  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow="Script workspace"
        title="PySpark Editor"
        description="Execute PySpark scripts using the local Spark session. The variable spark is already bound to the shared SparkSession. Return or assign a DataFrame to see a preview."
        actions={
          <>
            <Badge variant="success">PySpark</Badge>
            <Badge variant="info">Iceberg</Badge>
            <Badge variant="warning">Delta</Badge>
          </>
        }
      />

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-border/70 px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 items-center gap-1.5 rounded-md bg-muted px-2 text-[11px] font-medium text-foreground/90">
              <Terminal className="size-3.5 text-primary" />
              PySpark
            </div>
            <span className="hidden text-[11px] text-muted-foreground sm:inline">
              Local SparkSession via spark variable
            </span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onScriptChange(DEFAULT_PYSPARK)}
              disabled={running}
            >
              <RotateCcw />
              Reset
            </Button>
            <Button
              onClick={onRun}
              disabled={running || !script.trim()}
              className="min-w-[132px] shadow-lg shadow-primary/20"
            >
              {running ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Play />
              )}
              {running ? "Running…" : "Run Script"}
            </Button>
          </div>
        </div>

        <CardContent className="p-0">
          <BufferTabs
            buffers={tabs.buffers}
            activeId={tabs.activeId}
            onSelect={tabs.select}
            onAdd={tabs.add}
            onClose={tabs.close}
          />
          <CodeEditor
            value={script}
            onChange={onScriptChange}
            onRun={onRun}
            language="python"
          />

          <div className="flex flex-wrap items-center gap-2 border-t border-border/60 px-4 py-3">
            <span className="mr-1 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/70">
              <Sparkles className="size-3" />
              Samples
            </span>
            {PYSPARK_SAMPLES.map((sample) => (
              <Button
                key={sample.id}
                variant="outline"
                size="sm"
                title={sample.description}
                disabled={running}
                onClick={() => onScriptChange(sample.script)}
                className="h-7 px-2.5 text-[11px] font-normal"
              >
                {sample.label}
              </Button>
            ))}
            <span className="ml-auto hidden text-[10px] text-muted-foreground/70 md:inline">
              Ctrl/Cmd + Enter to execute
            </span>
          </div>
        </CardContent>
      </Card>

      <div>
        <div className="mb-2 flex items-center justify-between px-1">
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground/80">
            Execution result
          </h2>
          {result ? (
            <span className="text-[10px] text-muted-foreground/70">
              {result.row_count > 0
                ? `${result.row_count} row${result.row_count === 1 ? "" : "s"} materialised`
                : result.result_repr
                  ? "Value returned"
                  : "No rows materialised"}
            </span>
          ) : null}
        </div>
        <ResultsPanel
          result={
            result
              ? {
                  ...result,
                  sql: result.script,
                  statement_type: "PYSPARK",
                  statements: [],
                }
              : null
          }
          error={error}
          running={running}
          stdout={result?.stdout}
          stderr={result?.stderr}
          resultRepr={result?.result_repr ?? null}
        />
      </div>
    </div>
  );
}
