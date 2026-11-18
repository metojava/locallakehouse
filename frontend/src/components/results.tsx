import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Database,
  Loader2,
  Sparkles,
  Table2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ExecuteSqlResponse, SqlColumn } from "@/lib/api";
import {
  cn,
  formatMs,
  formatNumber,
  stringifyCell,
} from "@/lib/utils";

const ROW_RETURNING = new Set([
  "SELECT",
  "SHOW",
  "DESCRIBE",
  "DESC",
  "EXPLAIN",
  "WITH",
  "VALUES",
  "TABLE",
]);

const NUMERIC_TYPE =
  /^(tinyint|smallint|int|integer|bigint|long|short|byte|float|double|decimal)/i;

function engineVariant(engine: string): "info" | "warning" | "secondary" {
  if (engine === "iceberg") return "info";
  if (engine === "delta") return "warning";
  return "secondary";
}

interface ResultsPanelProps {
  result: ExecuteSqlResponse | null;
  error: string | null;
  running: boolean;
  stdout?: string;
  stderr?: string;
  resultRepr?: string | null;
}

export function ResultsPanel({
  result,
  error,
  running,
  stdout,
  stderr,
  resultRepr,
}: ResultsPanelProps) {
  if (running) return <RunningState />;
  if (error) return <ErrorState message={error} />;
  if (!result) return <EmptyState />;

  return (
    <ResultCard
      result={result}
      stdout={stdout}
      stderr={stderr}
      resultRepr={resultRepr}
    />
  );
}

function RunningState() {
  return (
    <Card className="animate-fade-in overflow-hidden">
      <CardContent className="flex flex-col gap-4 p-6">
        <div className="flex items-center gap-3">
          <div className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
            <Loader2 className="size-4 animate-spin" />
          </div>
          <div>
            <p className="text-sm font-medium">Executing on local Spark…</p>
            <p className="text-xs text-muted-foreground">
              The first query in a session can take longer while Spark starts and
              resolves the Delta/Iceberg jars.
            </p>
          </div>
        </div>
        <div className="space-y-2">
          <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-muted" />
          <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
        </div>
      </CardContent>
    </Card>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <Card className="animate-fade-in overflow-hidden border-destructive/40">
      <CardContent className="p-5">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-destructive/15 text-red-400">
            <AlertCircle className="size-4" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-base font-semibold text-red-400">Query failed</p>
            <pre className="mt-2 max-h-[320px] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-destructive/20 bg-destructive/5 p-3 font-mono text-[13.5px] leading-5 text-red-200/90">
              {message}
            </pre>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState() {
  return (
    <Card className="overflow-hidden border-dashed">
      <CardContent className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
        <div className="grid size-12 place-items-center rounded-2xl bg-muted/60 text-muted-foreground">
          <Database className="size-5" />
        </div>
        <div>
          <p className="text-sm font-medium">Results will appear here</p>
          <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
            Write a query above and press{" "}
            <span className="rounded border bg-muted px-1 py-0.5 font-mono text-[10px]">
              Ctrl
            </span>{" "}
            +{" "}
            <span className="rounded border bg-muted px-1 py-0.5 font-mono text-[10px]">
              Enter
            </span>
            . Seed the demo tables with{" "}
            <code className="font-mono text-[11px] text-primary">
              python seed_demo.py
            </code>{" "}
            to explore Iceberg and Delta immediately.
          </p>
        </div>
        <div className="mt-1 flex flex-wrap justify-center gap-2 text-[10px] text-muted-foreground">
          <span className="inline-flex items-center gap-1 rounded-full border px-2 py-1">
            <Sparkles className="size-3 text-primary" />
            Local Spark 4.1
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border px-2 py-1">
            <Table2 className="size-3 text-sky-400" />
            Iceberg + Delta
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function ResultCard({
  result,
  stdout,
  stderr,
  resultRepr,
}: {
  result: ExecuteSqlResponse;
  stdout?: string;
  stderr?: string;
  resultRepr?: string | null;
}) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<number | null>(null);
  const hasOutput = Boolean(stdout?.trim() || stderr?.trim() || resultRepr);

  useEffect(
    () => () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    },
    [],
  );

  const copyRows = async () => {
    try {
      await navigator.clipboard.writeText(
        JSON.stringify(result.rows, null, 2),
      );
      setCopied(true);
      if (timerRef.current) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => setCopied(false), 1_800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Card className="animate-fade-in overflow-hidden">
      <Tabs defaultValue={hasOutput ? "output" : "table"}>
        <div className="flex flex-wrap items-center gap-2 border-b border-border/70 px-5 py-3">
          <div className="flex items-center gap-2">
            <Badge variant={engineVariant(result.engine)}>
              {result.engine.toUpperCase()}
            </Badge>
            <Badge variant="secondary">{result.statement_type}</Badge>
          </div>

          <div className="ml-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <Table2 className="size-3" />
              {formatNumber(result.row_count)} rows
            </span>
            <span className="inline-flex items-center gap-1">
              <Clock className="size-3" />
              {formatMs(result.execution_time_ms)}
            </span>
            <span className="hidden lg:inline">
              row cap {formatNumber(result.max_rows)}
            </span>
            {result.truncated ? <Badge variant="warning">truncated</Badge> : null}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={copyRows}
              title="Copy rows as JSON"
            >
              {copied ? <Check className="text-emerald-400" /> : <Copy />}
            </Button>
            <TabsList>
              {hasOutput ? <TabsTrigger value="output">Output</TabsTrigger> : null}
              <TabsTrigger value="table">Table</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
            </TabsList>
          </div>
        </div>

        {result.statements.length > 1 ? (
          <div className="no-scrollbar flex gap-2 overflow-x-auto border-b border-border/60 bg-muted/15 px-5 py-2">
            {result.statements.map((statement, index) => (
              <span
                key={`${index}-${statement.statement_type}`}
                title={statement.statement}
                className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border/60 bg-background/40 px-2 py-1 text-[10px] text-muted-foreground"
              >
                <span className="font-semibold text-foreground">
                  {index + 1}
                </span>
                <span>{statement.statement_type}</span>
                <span>·</span>
                <span>{statement.engine}</span>
                <span>·</span>
                <span>{formatMs(statement.execution_time_ms)}</span>
              </span>
            ))}
          </div>
        ) : null}

        {hasOutput ? (
          <TabsContent value="output" className="m-0">
            <div className="max-h-[55vh] overflow-auto bg-muted/10 p-5 font-mono text-sm leading-6 text-foreground/90">
              {resultRepr ? (
                <div className="mb-4 border-b border-border/40 pb-4">
                  <span className="mb-1 block text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Returned value
                  </span>
                  <code className="block whitespace-pre-wrap break-words text-emerald-300">
                    {resultRepr}
                  </code>
                </div>
              ) : null}
              {stdout?.trim() ? (
                <pre className="whitespace-pre-wrap break-words">{stdout}</pre>
              ) : null}
              {stderr?.trim() ? (
                <pre className="mt-2 whitespace-pre-wrap break-words text-red-300">
                  {stderr}
                </pre>
              ) : null}
            </div>
          </TabsContent>
        ) : null}

        <TabsContent value="table" className="m-0">
          <ResultsGrid
            columns={result.columns}
            rows={result.rows}
            statementType={result.statement_type}
          />
        </TabsContent>
        <TabsContent value="json" className="m-0">
          <pre className="max-h-[55vh] overflow-auto bg-muted/10 p-5 font-mono text-sm leading-6 text-foreground/90">
            {JSON.stringify(result.rows, null, 2)}
          </pre>
        </TabsContent>
      </Tabs>
    </Card>
  );
}

interface ResultsGridProps {
  columns: SqlColumn[];
  rows: Record<string, unknown>[];
  statementType: string;
}

export function ResultsGrid({ columns, rows, statementType }: ResultsGridProps) {
  if (rows.length === 0) {
    const rowReturning = ROW_RETURNING.has(statementType);
    return (
      <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
        <div className="grid size-10 place-items-center rounded-full bg-emerald-500/10 text-emerald-400">
          <CheckCircle2 className="size-5" />
        </div>
        <p className="text-sm font-medium">
          {rowReturning
            ? "Query completed with no rows."
            : "Statement executed successfully."}
        </p>
        <p className="max-w-md text-xs text-muted-foreground">
          {rowReturning
            ? "The query is valid but the result set is empty."
            : "The catalog or table metadata was updated. Refresh the schema and storage views to inspect the changes."}
        </p>
      </div>
    );
  }

  return (
    <div className="max-h-[55vh] overflow-auto">
      <table className="w-full min-w-max border-collapse text-left text-[15px]">
        <thead>
          <tr className="border-b border-border/70 bg-muted text-[13px] uppercase tracking-wide text-muted-foreground">
            <th className="sticky left-0 top-0 z-30 w-12 border-r border-border/60 bg-muted px-3 py-2 text-right font-medium">
              #
            </th>
            {columns.map((column) => (
              <th
                key={column.name}
                className="sticky top-0 z-20 whitespace-nowrap border-b border-border/60 bg-muted px-3 py-2 font-medium"
              >
                <span className="block text-foreground/90">{column.name}</span>
                <span className="block font-mono text-[11.5px] font-normal normal-case text-muted-foreground/70">
                  {column.type}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className="group border-b border-border/40 transition-colors hover:bg-muted/30"
            >
              <td className="sticky left-0 z-10 border-r border-border/40 bg-card px-3 py-2 text-right font-mono text-[12px] text-white group-hover:bg-muted">
                {rowIndex + 1}
              </td>
              {columns.map((column) => {
                const value = row[column.name];
                const isNull = value === null || value === undefined;
                const isObject =
                  typeof value === "object" && value !== null;
                const text = stringifyCell(value);
                return (
                  <td
                    key={column.name}
                    className={cn(
                      "whitespace-nowrap px-3 py-2 align-top",
                      NUMERIC_TYPE.test(column.type) && "text-right",
                    )}
                  >
                    <span
                      title={text}
                      className={cn(
                        "block max-w-[360px] truncate font-mono text-[14px]",
                        isNull && "italic text-muted-foreground/50",
                        isObject && "text-sky-300",
                        typeof value === "boolean" && "text-violet-300",
                      )}
                    >
                      {isNull ? "NULL" : text}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
