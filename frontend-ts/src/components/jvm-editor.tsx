import {
  AlertTriangle,
  Clock,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
  Square,
  Terminal,
} from "lucide-react";

import { BufferTabs } from "@/components/buffer-tabs";
import { CodeEditor } from "@/components/code-editor";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { JvmLanguage, JvmRunResponse } from "@/lib/api";
import type { EditorBuffers } from "@/lib/editor-buffers";
import { DEFAULT_JAVA, DEFAULT_SCALA } from "@/lib/samples";
import { cn, formatMs } from "@/lib/utils";

interface JvmEditorProps {
  tabs: EditorBuffers;
  language: JvmLanguage;
  source: string;
  onSourceChange: (source: string) => void;
  onRun: () => void;
  onStop: () => void;
  running: boolean;
  result: JvmRunResponse | null;
  error: string | null;
}

const LANGUAGE_INFO: Record<
  JvmLanguage,
  { title: string; description: string; fileName: string; defaultSource: string }
> = {
  java: {
    title: "Java Editor",
    description:
      "Compile and run a Java program with the local Spark jars. Define public class Main with a main method. Each run is a separate Spark job, so variables do not carry between runs.",
    fileName: "Main.java",
    defaultSource: DEFAULT_JAVA,
  },
  scala: {
    title: "Scala Editor",
    description:
      "Compile and run a Scala 2.13 program with the local Spark jars. Define object Main with a main method. Each run is a separate Spark job, so variables do not carry between runs.",
    fileName: "Main.scala",
    defaultSource: DEFAULT_SCALA,
  },
};

function OutputBlock({
  label,
  text,
  tone,
}: {
  label: string;
  text: string;
  tone?: "error";
}) {
  if (!text.trim()) return null;
  return (
    <div className="space-y-1">
      <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/80">
        {label}
      </p>
      <pre
        className={cn(
          "max-h-[360px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border/60 bg-muted/30 p-3 font-mono text-[13.5px] leading-5 text-foreground/90",
          tone === "error" && "border-destructive/30 text-red-300",
        )}
      >
        {text}
      </pre>
    </div>
  );
}

export function JvmEditor({
  tabs,
  language,
  source,
  onSourceChange,
  onRun,
  onStop,
  running,
  result,
  error,
}: JvmEditorProps) {
  const info = LANGUAGE_INFO[language];

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow="Script workspace"
        title={info.title}
        description={info.description}
        actions={
          <>
            <Badge variant="success">{language === "java" ? "Java 17" : "Scala 2.13"}</Badge>
            <Badge variant="info">Spark jobs</Badge>
            <Badge variant="warning">Separate JVM per run</Badge>
          </>
        }
      />

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b border-border/70 px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 items-center gap-1.5 rounded-md bg-muted px-2 text-[11px] font-medium text-foreground/90">
              <Terminal className="size-3.5 text-primary" />
              {info.fileName}
            </div>
            <span className="hidden text-[11px] text-muted-foreground sm:inline">
              spark-submit · in-memory catalog · Delta and Iceberg by path
            </span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSourceChange(info.defaultSource)}
              disabled={running}
            >
              <RotateCcw />
              Reset
            </Button>
            <Button
              onClick={onRun}
              disabled={running || !source.trim()}
              className="min-w-[132px] shadow-lg shadow-primary/20"
            >
              {running ? <Loader2 className="animate-spin" /> : <Play />}
              {running ? "Running…" : "Run program"}
            </Button>
            {running ? (
              <Button
                variant="destructive"
                onClick={onStop}
                className="shadow-lg shadow-destructive/20"
                title="Cancel the running program"
              >
                <Square className="fill-current" />
                Stop
              </Button>
            ) : null}
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
            value={source}
            onChange={onSourceChange}
            onRun={onRun}
            language={language}
          />

          <div className="flex flex-wrap items-center gap-2 border-t border-border/60 px-4 py-3">
            <span className="mr-1 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/70">
              <Sparkles className="size-3" />
              Note
            </span>
            <span className="text-[11px] text-muted-foreground">
              Runs take longer than PySpark cells (compile + JVM start, typically 20–40 s).
              Use the Spark session from the PySpark editor for interactive work.
            </span>
            <span className="ml-auto hidden text-[10px] text-muted-foreground/70 md:inline">
              Ctrl/Cmd + Enter to run
            </span>
          </div>
        </CardContent>
      </Card>

      <div>
        <div className="mb-2 flex items-center justify-between px-1">
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground/80">
            Program output
          </h2>
          {result ? (
            <span className="flex items-center gap-1 text-[10px] text-muted-foreground/70">
              <Clock className="size-3" />
              {formatMs(result.execution_time_ms)}
              {result.exit_code !== null ? ` · exit ${result.exit_code}` : ""}
            </span>
          ) : null}
        </div>

        {error ? (
          <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-base text-red-300">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span className="whitespace-pre-wrap">{error}</span>
          </div>
        ) : null}

        {result ? (
          <Card>
            <CardContent className="space-y-4 p-4">
              {result.compile_ok ? null : (
                <div className="flex items-center gap-2 text-sm font-medium text-red-300">
                  <AlertTriangle className="size-3.5" />
                  Compilation failed. The program was not run.
                </div>
              )}
              <OutputBlock
                label="Compiler"
                text={result.compile_output}
                tone={result.compile_ok ? undefined : "error"}
              />
              <OutputBlock label="stdout" text={result.stdout} />
              <OutputBlock label="stderr" text={result.stderr} tone="error" />
              {result.compile_ok &&
              !result.stdout.trim() &&
              !result.stderr.trim() ? (
                <p className="text-xs text-muted-foreground">
                  The program finished without output.
                </p>
              ) : null}
            </CardContent>
          </Card>
        ) : !error && !running ? (
          <p className="px-1 text-xs text-muted-foreground">
            Run the program to see compiler and program output here.
          </p>
        ) : null}
      </div>
    </div>
  );
}
