import { useState } from "react";

import { Code2, Loader2, Play, RotateCcw, Sparkles, Upload } from "lucide-react";

import { BufferTabs } from "@/components/buffer-tabs";
import { CodeEditor } from "@/components/code-editor";
import { ImportPanel } from "@/components/import-panel";
import { PageHeader } from "@/components/page-header";
import { ResultsPanel } from "@/components/results";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ExecuteSqlResponse } from "@/lib/api";
import type { EditorBuffers } from "@/lib/editor-buffers";
import { DEFAULT_SQL, SQL_SAMPLES } from "@/lib/samples";

interface SqlEditorProps {
  tabs: EditorBuffers;
  sql: string;
  onSqlChange: (sql: string) => void;
  onRun: () => void;
  running: boolean;
  result: ExecuteSqlResponse | null;
  error: string | null;
  online: boolean;
  onImported: () => void;
}

export function SqlEditor({
  tabs,
  sql,
  onSqlChange,
  onRun,
  running,
  result,
  error,
  online,
  onImported,
}: SqlEditorProps) {
  const [showImport, setShowImport] = useState(false);
  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow="Query workspace"
        title="SQL Editor"
        description="Execute Spark SQL against the local Delta session catalog and the Hadoop-backed Iceberg catalog. Use fully qualified names such as local_iceberg.demo.sales or demo.customers."
        actions={
          <>
            <Badge variant="success">Spark SQL</Badge>
            <Badge variant="info">Iceberg</Badge>
            <Badge variant="warning">Delta</Badge>
          </>
        }
      />

      {showImport ? (
        <ImportPanel
          online={online}
          onImported={() => {
            setShowImport(false);
            onImported();
          }}
          onClose={() => setShowImport(false)}
        />
      ) : null}

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-border/70 px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 items-center gap-1.5 rounded-md bg-muted px-2 text-[11px] font-medium text-foreground/90">
              <Code2 className="size-3.5 text-primary" />
              Spark SQL
            </div>
            <span className="hidden text-[11px] text-muted-foreground sm:inline">
              Iceberg + Delta extensions loaded
            </span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowImport((value) => !value)}
              disabled={running}
            >
              <Upload />
              Import file
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSqlChange(DEFAULT_SQL)}
              disabled={running}
            >
              <RotateCcw />
              Reset
            </Button>
            <Button
              onClick={onRun}
              disabled={running || !sql.trim()}
              className="min-w-[132px] shadow-lg shadow-primary/20"
            >
              {running ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Play />
              )}
              {running ? "Running…" : "Run Query"}
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
          <CodeEditor value={sql} onChange={onSqlChange} onRun={onRun} />

          <div className="flex flex-wrap items-center gap-2 border-t border-border/60 px-4 py-3">
            <span className="mr-1 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/70">
              <Sparkles className="size-3" />
              Samples
            </span>
            {SQL_SAMPLES.map((sample) => (
              <Button
                key={sample.id}
                variant="outline"
                size="sm"
                title={sample.description}
                disabled={running}
                onClick={() => onSqlChange(sample.sql)}
                className="h-7 px-2.5 text-[11px] font-normal"
              >
                {sample.label}
              </Button>
            ))}
            <span className="ml-auto hidden text-[10px] text-muted-foreground/70 md:inline">
              Ctrl/Cmd + Enter to execute · multiple statements run in order
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
              {result.rows.length > 0
                ? `${result.rows.length} row${result.rows.length === 1 ? "" : "s"} materialised`
                : "No rows materialised"}
            </span>
          ) : null}
        </div>
        <ResultsPanel result={result} error={error} running={running} />
      </div>
    </div>
  );
}
