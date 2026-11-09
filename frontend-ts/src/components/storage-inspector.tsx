import { useEffect, useState } from "react";
import {
  AlertCircle,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  Database,
  File,
  FileArchive,
  FileJson,
  FileText,
  Folder,
  FolderOpen,
  HardDrive,
  RefreshCw,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ApiError,
  getStorage,
  type StorageEntry,
  type StorageResponse,
} from "@/lib/api";
import {
  cn,
  formatBytes,
  formatDate,
  formatNumber,
  shortPath,
} from "@/lib/utils";

interface StorageInspectorProps {
  online: boolean;
}

const CATEGORY_BADGE: Record<
  string,
  "success" | "warning" | "violet" | "info" | "outline"
> = {
  parquet: "success",
  json: "warning",
  avro: "violet",
  database: "info",
  checksum: "outline",
  log: "outline",
  csv: "success",
};

const CATEGORY_COLOR: Record<string, string> = {
  parquet: "text-emerald-400",
  json: "text-amber-400",
  avro: "text-violet-400",
  database: "text-sky-400",
  archive: "text-orange-400",
  checksum: "text-muted-foreground/60",
  log: "text-muted-foreground/60",
};

function fileIcon(category: string | null): LucideIcon {
  switch (category) {
    case "json":
      return FileJson;
    case "parquet":
    case "avro":
      return FileText;
    case "database":
      return Database;
    case "archive":
      return FileArchive;
    default:
      return File;
  }
}

export function StorageInspector({ online }: StorageInspectorProps) {
  const [path, setPath] = useState("");
  const [depth, setDepth] = useState(3);
  const [data, setData] = useState<StorageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStorage = async (nextPath: string, nextDepth: number) => {
    setLoading(true);
    setError(null);
    try {
      const response = await getStorage(nextPath, nextDepth, 2000);
      setData(response);
      setPath(response.path);
    } catch (err) {
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Could not inspect the warehouse.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (online) void fetchStorage("", 3);
  }, [online]);

  const navigate = (nextPath: string) => {
    if (nextPath === path && !error) return;
    void fetchStorage(nextPath, depth);
  };

  const goUp = () => {
    const segments = path.split("/").filter(Boolean);
    segments.pop();
    void fetchStorage(segments.join("/"), depth);
  };

  const changeDepth = (nextDepth: number) => {
    setDepth(nextDepth);
    void fetchStorage(path, nextDepth);
  };

  const activePath = data?.path ?? path;
  const segments = activePath.split("/").filter(Boolean);
  const crumbs = [
    { label: "warehouse", path: "" },
    ...segments.map((segment, index) => ({
      label: segment,
      path: segments.slice(0, index + 1).join("/"),
    })),
  ];

  const categories = Object.entries(data?.summary.by_category ?? {}).sort(
    (a, b) => b[1].bytes - a[1].bytes,
  );

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow="Filesystem"
        title="Physical Storage Inspector"
        description="Inspect the real files behind the lakehouse: Parquet data files, Delta transaction logs, and Iceberg manifests and metadata JSON."
        actions={
          <>
            <Badge variant="outline">read-only</Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void fetchStorage(path, depth)}
              disabled={loading || !online}
            >
              <RefreshCw className={cn(loading && "animate-spin")} />
              Refresh
            </Button>
          </>
        }
      />

      {!online ? (
        <Card className="border-amber-500/30 bg-amber-500/5 p-4">
          <div className="flex items-center gap-2 text-xs text-amber-300">
            <AlertCircle className="size-4" />
            The backend is offline. Start the FastAPI server to inspect the
            warehouse directory.
          </div>
        </Card>
      ) : null}

      <div className="flex items-center gap-2 rounded-lg border border-border/70 bg-card/50 px-3 py-2 text-xs">
        <HardDrive className="size-3.5 shrink-0 text-primary" />
        <span className="hidden text-muted-foreground sm:inline">
          Warehouse root
        </span>
        <code
          className="min-w-0 flex-1 truncate font-mono text-[11px] text-foreground/80"
          title={data?.root}
        >
          {data?.root ?? "—"}
        </code>
        <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
          /{activePath}
        </span>
      </div>

      {data ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            icon={FileText}
            label="Files"
            value={formatNumber(data.summary.files)}
            detail={`within ${data.summary.max_depth} levels`}
          />
          <StatCard
            icon={HardDrive}
            label="Total size"
            value={formatBytes(data.summary.bytes)}
            detail="scanned subtree"
          />
          <StatCard
            icon={Folder}
            label="Directories"
            value={formatNumber(data.summary.directories)}
            detail="namespaces, logs, metadata"
          />
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center gap-2">
                <div className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
                  <Database className="size-4" />
                </div>
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  File types
                </p>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {categories.length === 0 ? (
                  <span className="text-xs text-muted-foreground">—</span>
                ) : (
                  categories.slice(0, 5).map(([category, summary]) => (
                    <Badge
                      key={category}
                      variant={CATEGORY_BADGE[category] ?? "outline"}
                    >
                      {category} · {summary.files}
                    </Badge>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {error ? (
        <Card className="border-destructive/40 p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-400" />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-red-400">
                Storage scan failed
              </p>
              <pre className="mt-1 whitespace-pre-wrap break-words font-mono text-[11px] text-red-200/80">
                {error}
              </pre>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="shrink-0"
              onClick={() => void fetchStorage(path, depth)}
              disabled={!online}
            >
              Retry
            </Button>
          </div>
        </Card>
      ) : null}

      {data?.summary.truncated ? (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-[11px] text-amber-300">
          <AlertCircle className="size-3.5" />
          The directory contains more entries than the scan limit; increase the
          depth or narrow the path for a complete view.
        </div>
      ) : null}

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-2 border-b border-border/70 px-4 py-3">
          <nav className="flex min-w-0 flex-wrap items-center gap-1 text-[11px]">
            {crumbs.map((crumb, index) => (
              <span key={crumb.path || "root"} className="flex items-center gap-1">
                {index > 0 ? (
                  <ChevronRight className="size-3 text-muted-foreground/50" />
                ) : null}
                <button
                  type="button"
                  onClick={() => navigate(crumb.path)}
                  className={cn(
                    "max-w-[220px] truncate rounded px-1.5 py-0.5 font-mono hover:bg-muted",
                    index === crumbs.length - 1
                      ? "text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                  title={crumb.path || "/"}
                >
                  {crumb.label}
                </button>
              </span>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={goUp}
              disabled={loading || segments.length === 0}
              title="Go to parent directory"
            >
              <ArrowUp />
              Up
            </Button>
            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              Depth
              <select
                value={depth}
                onChange={(event) => changeDepth(Number(event.target.value))}
                className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground outline-none focus:ring-2 focus:ring-ring"
              >
                {[1, 2, 3, 4, 5, 6].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => void fetchStorage(path, depth)}
              disabled={loading}
              title="Refresh directory"
            >
              <RefreshCw className={cn(loading && "animate-spin")} />
            </Button>
          </div>
        </div>

        {loading && !data ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2, 3, 4].map((index) => (
              <div
                key={index}
                className="h-7 animate-pulse rounded bg-muted"
                style={{ width: `${90 - index * 9}%` }}
              />
            ))}
          </div>
        ) : null}

        {data ? (
          <div className="p-2">
            {data.tree.children.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
                <div className="grid size-11 place-items-center rounded-2xl bg-muted/60 text-muted-foreground">
                  <FolderOpen className="size-5" />
                </div>
                <p className="text-sm font-medium">This directory is empty</p>
                <p className="max-w-md text-xs text-muted-foreground">
                  Create a Delta or Iceberg table, or seed the demo data with{" "}
                  <code className="font-mono text-primary">
                    python seed_demo.py
                  </code>{" "}
                  from the backend directory.
                </p>
              </div>
            ) : (
              data.tree.children.map((child) => (
                <StorageNode
                  key={child.path}
                  node={child}
                  depth={0}
                  onNavigate={navigate}
                />
              ))
            )}
          </div>
        ) : null}
      </Card>

      <p className="px-1 text-[10px] text-muted-foreground/60">
        Showing <span className="font-mono">/{activePath || ""}</span> ·{" "}
        {data ? shortPath(data.root, 90) : "local filesystem"} · entry limit{" "}
        {formatNumber(data?.summary.max_entries ?? 2000)}
      </p>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="truncate text-lg font-semibold tabular-nums">{value}</p>
          <p className="truncate text-[10px] text-muted-foreground/70">
            {detail}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

interface StorageNodeProps {
  node: StorageEntry;
  depth: number;
  onNavigate: (path: string) => void;
}

function StorageNode({ node, depth, onNavigate }: StorageNodeProps) {
  const [open, setOpen] = useState(depth < 1);

  if (node.type === "directory") {
    return (
      <div>
        <div className="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/40">
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="grid size-5 shrink-0 place-items-center rounded text-muted-foreground hover:bg-muted"
            title={open ? "Collapse" : "Expand"}
          >
            {open ? (
              <ChevronDown className="size-3.5" />
            ) : (
              <ChevronRight className="size-3.5" />
            )}
          </button>
          {open ? (
            <FolderOpen className="size-4 shrink-0 text-primary/80" />
          ) : (
            <Folder className="size-4 shrink-0 text-primary/70" />
          )}
          <button
            type="button"
            onClick={() => onNavigate(node.path)}
            className="min-w-0 flex-1 truncate text-left font-mono text-xs hover:text-primary"
            title={`Open /${node.path}`}
          >
            {node.name}
          </button>
          {node.truncated ? (
            <Badge variant="warning">partial</Badge>
          ) : null}
          <span className="w-16 shrink-0 text-right font-mono text-[10.5px] tabular-nums text-muted-foreground">
            {node.size > 0 ? formatBytes(node.size) : "—"}
          </span>
          <span className="hidden w-32 shrink-0 text-right text-[10px] text-muted-foreground/70 md:block">
            {formatDate(node.modified)}
          </span>
        </div>

        {open ? (
          node.children.length > 0 ? (
            <div className="ml-5 border-l border-border/50 pl-2">
              {node.children.map((child) => (
                <StorageNode
                  key={child.path}
                  node={child}
                  depth={depth + 1}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          ) : (
            <p className="ml-12 py-1 text-[10px] italic text-muted-foreground/60">
              empty directory
            </p>
          )
        ) : null}
      </div>
    );
  }

  const Icon = fileIcon(node.category);
  return (
    <div className="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/40">
      <span className="size-5 shrink-0" />
      <Icon
        className={cn(
          "size-4 shrink-0",
          CATEGORY_COLOR[node.category ?? ""] ?? "text-muted-foreground",
        )}
      />
      <span
        className="min-w-0 flex-1 truncate font-mono text-xs"
        title={node.path}
      >
        {node.name}
      </span>
      <Badge
        variant={CATEGORY_BADGE[node.category ?? ""] ?? "outline"}
        className="hidden shrink-0 sm:inline-flex"
      >
        {node.category}
      </Badge>
      <span className="w-16 shrink-0 text-right font-mono text-[10.5px] tabular-nums text-muted-foreground">
        {formatBytes(node.size)}
      </span>
      <span className="hidden w-32 shrink-0 text-right text-[10px] text-muted-foreground/70 md:block">
        {formatDate(node.modified)}
      </span>
    </div>
  );
}
