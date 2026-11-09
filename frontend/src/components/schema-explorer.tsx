import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Database,
  FolderTree,
  Play,
  RefreshCw,
  Table2,
  Upload,
  Zap,
} from "lucide-react";

import { ImportPanel } from "@/components/import-panel";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  ApiError,
  getTables,
  type CatalogInfo,
  type NamespaceInfo,
  type TablesResponse,
} from "@/lib/api";
import { cn, formatDate, shortPath } from "@/lib/utils";

interface SchemaExplorerProps {
  onUseTable: (fullName: string) => void;
  online: boolean;
}

function formatVariant(format: string | null): "info" | "warning" | "violet" {
  if (format === "iceberg") return "info";
  if (format === "delta") return "warning";
  return "violet";
}

export function SchemaExplorer({ onUseTable, online }: SchemaExplorerProps) {
  const [data, setData] = useState<TablesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [showImport, setShowImport] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getTables(true);
      setData(response);
      setExpanded((previous) => {
        const next = new Set(previous);
        response.catalogs.forEach((catalog) =>
          next.add(`catalog:${catalog.catalog}`),
        );
        return next;
      });
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Could not load the catalogs.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (online) void load();
  }, [load, online]);

  const toggle = (key: string) =>
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const totalTables =
    data?.catalogs.reduce(
      (total, catalog) =>
        total +
        catalog.namespaces.reduce(
          (namespaceTotal, namespace) =>
            namespaceTotal + namespace.tables.length,
          0,
        ),
      0,
    ) ?? 0;

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow="Metadata"
        title="Schema Explorer"
        description="Browse the Delta-backed session catalog (spark_catalog) and the local Iceberg Hadoop catalog. Select a table to load a preview query into the SQL editor."
        actions={
          <>
            <Badge variant="outline">{totalTables} tables</Badge>
            <Button
              variant={showImport ? "secondary" : "default"}
              size="sm"
              onClick={() => setShowImport((previous) => !previous)}
              disabled={!online}
            >
              <Upload />
              Import file
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void load()}
              disabled={loading || !online}
            >
              <RefreshCw className={cn(loading && "animate-spin")} />
              Refresh
            </Button>
          </>
        }
      />

      {showImport ? (
        <ImportPanel
          online={online}
          onImported={() => void load()}
          onClose={() => setShowImport(false)}
        />
      ) : null}

      {!online ? (
        <Card className="border-amber-500/30 bg-amber-500/5 p-4">
          <div className="flex items-center gap-2 text-xs text-amber-300">
            <AlertCircle className="size-4" />
            The backend is offline. Start the FastAPI server to inspect catalogs.
          </div>
        </Card>
      ) : null}

      {error ? (
        <Card className="border-destructive/40 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-400" />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-red-400">
                Catalog lookup failed
              </p>
              <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-[11px] text-red-200/80">
                {error}
              </pre>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="ml-auto shrink-0"
              onClick={() => void load()}
              disabled={!online}
            >
              Retry
            </Button>
          </div>
        </Card>
      ) : null}

      {loading && !data ? (
        <div className="space-y-3">
          {[0, 1].map((index) => (
            <Card key={index} className="p-5">
              <div className="flex items-center gap-3">
                <div className="size-9 animate-pulse rounded-lg bg-muted" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 w-40 animate-pulse rounded bg-muted" />
                  <div className="h-2.5 w-64 animate-pulse rounded bg-muted" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : null}

      {data ? (
        <div className="space-y-3">
          {data.catalogs.map((catalog) => (
            <CatalogCard
              key={catalog.catalog}
              catalog={catalog}
              expanded={expanded}
              onToggle={toggle}
              onUseTable={onUseTable}
            />
          ))}
          <p className="px-1 text-right text-[10px] text-muted-foreground/60">
            Catalog snapshot {formatDate(data.generated_at)}
          </p>
        </div>
      ) : null}
    </div>
  );
}

interface CatalogCardProps {
  catalog: CatalogInfo;
  expanded: Set<string>;
  onToggle: (key: string) => void;
  onUseTable: (fullName: string) => void;
}

function CatalogCard({
  catalog,
  expanded,
  onToggle,
  onUseTable,
}: CatalogCardProps) {
  const catalogKey = `catalog:${catalog.catalog}`;
  const isOpen = expanded.has(catalogKey);
  const tableCount = catalog.namespaces.reduce(
    (total, namespace) => total + namespace.tables.length,
    0,
  );
  const isIceberg = catalog.engine === "iceberg";
  const CatalogIcon = isIceberg ? Database : Zap;

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={() => onToggle(catalogKey)}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/20"
      >
        {isOpen ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        )}
        <div
          className={cn(
            "grid size-9 shrink-0 place-items-center rounded-lg ring-1 ring-inset",
            isIceberg
              ? "bg-sky-500/10 text-sky-400 ring-sky-500/20"
              : "bg-amber-500/10 text-amber-400 ring-amber-500/20",
          )}
        >
          <CatalogIcon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">{catalog.name}</span>
            <Badge variant={isIceberg ? "info" : "warning"}>
              {catalog.engine}
            </Badge>
            <Badge variant="outline" className="font-mono">
              {catalog.catalog}
            </Badge>
          </div>
          <p className="mt-0.5 truncate font-mono text-[10.5px] text-muted-foreground">
            {catalog.namespaces.length} namespaces · {tableCount} tables
          </p>
        </div>
        {catalog.error ? (
          <Badge variant="destructive">error</Badge>
        ) : (
          <Badge variant="outline">{tableCount}</Badge>
        )}
      </button>

      {isOpen ? (
        <div className="border-t border-border/60">
          {catalog.error ? (
            <div className="flex items-start gap-2 bg-destructive/5 px-4 py-3 text-[11px] text-red-300">
              <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
              <span className="whitespace-pre-wrap break-words">
                {catalog.error}
              </span>
            </div>
          ) : null}

          {catalog.namespaces.length === 0 && !catalog.error ? (
            <p className="px-4 py-4 text-xs italic text-muted-foreground">
              No namespaces yet. Create one with{" "}
              <code className="font-mono text-primary">
                CREATE NAMESPACE {catalog.catalog}.demo
              </code>
              .
            </p>
          ) : null}

          {catalog.namespaces.map((namespace) => (
            <NamespaceRow
              key={`${catalog.catalog}.${namespace.name}`}
              catalog={catalog}
              namespace={namespace}
              expanded={expanded}
              onToggle={onToggle}
              onUseTable={onUseTable}
            />
          ))}
        </div>
      ) : null}
    </Card>
  );
}

interface NamespaceRowProps {
  catalog: CatalogInfo;
  namespace: NamespaceInfo;
  expanded: Set<string>;
  onToggle: (key: string) => void;
  onUseTable: (fullName: string) => void;
}

function NamespaceRow({
  catalog,
  namespace,
  expanded,
  onToggle,
  onUseTable,
}: NamespaceRowProps) {
  const key = `namespace:${catalog.catalog}.${namespace.name}`;
  const isOpen = expanded.has(key);

  return (
    <div>
      <button
        type="button"
        onClick={() => onToggle(key)}
        className="flex w-full items-center gap-2 border-b border-border/40 px-4 py-2.5 text-left transition-colors hover:bg-muted/20"
      >
        {isOpen ? (
          <ChevronDown className="size-3.5 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-3.5 text-muted-foreground" />
        )}
        <FolderTree className="size-3.5 text-muted-foreground" />
        <span className="font-mono text-xs font-medium">{namespace.name}</span>
        <Badge variant="outline" className="ml-1">
          {namespace.tables.length}
        </Badge>
        {namespace.error ? (
          <Badge variant="destructive" className="ml-auto">
            error
          </Badge>
        ) : null}
      </button>

      {isOpen ? (
        <div className="bg-muted/10">
          {namespace.error ? (
            <p className="px-12 py-2 text-[11px] text-red-300">
              {namespace.error}
            </p>
          ) : null}
          {namespace.tables.length === 0 && !namespace.error ? (
            <p className="px-12 py-2.5 text-[11px] italic text-muted-foreground">
              No tables in this namespace.
            </p>
          ) : null}
          {namespace.tables.map((table) => (
            <div
              key={table.full_name}
              className="group flex items-center gap-2.5 border-b border-border/30 px-4 py-2 pl-12 last:border-b-0 hover:bg-muted/30"
            >
              <Table2 className="size-3.5 shrink-0 text-muted-foreground" />
              <button
                type="button"
                onClick={() => onUseTable(table.full_name)}
                className="min-w-0 flex-1 text-left"
                title="Load SELECT preview in SQL editor"
              >
                <div className="flex items-center gap-2">
                  <span className="truncate font-mono text-xs">
                    {table.name}
                  </span>
                  <Badge variant={formatVariant(table.format)}>
                    {table.format ?? "table"}
                  </Badge>
                  {table.is_temporary ? (
                    <Badge variant="outline">temp</Badge>
                  ) : null}
                </div>
                <p
                  className="truncate font-mono text-[9.5px] text-muted-foreground/70"
                  title={table.location ?? table.full_name}
                >
                  {table.location
                    ? shortPath(table.location, 96)
                    : table.full_name}
                </p>
              </button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 shrink-0 px-2 text-[10px] opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
                onClick={() => onUseTable(table.full_name)}
              >
                <Play className="size-3" />
                Query
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
