import {
  Coffee,
  Cpu,
  Database,
  ExternalLink,
  FolderOpen,
  FolderTree,
  HardDrive,
  Layers,
  Server,
  Sigma,
  Terminal,
  Workflow,
} from "lucide-react";

import { API_BASE_URL, API_DOCS_URL, type HealthResponse } from "@/lib/api";
import { cn, shortPath } from "@/lib/utils";

export type WorkbenchView =
  | "sql"
  | "pyspark"
  | "java"
  | "scala"
  | "workspace"
  | "databases"
  | "schema"
  | "storage"
  | "spark";

interface SidebarProps {
  view: WorkbenchView;
  onViewChange: (view: WorkbenchView) => void;
  health: HealthResponse | null;
  online: boolean;
}

const NAV_ITEMS: {
  id: WorkbenchView;
  label: string;
  hint: string;
  icon: typeof Terminal;
}[] = [
  {
    id: "sql",
    label: "SQL Editor",
    hint: "Run Spark SQL",
    icon: Terminal,
  },
  {
    id: "pyspark",
    label: "PySpark Editor",
    hint: "Run PySpark scripts",
    icon: Workflow,
  },
  {
    id: "java",
    label: "Java Editor",
    hint: "Compile & run Java",
    icon: Coffee,
  },
  {
    id: "scala",
    label: "Scala Editor",
    hint: "Compile & run Scala",
    icon: Sigma,
  },
  {
    id: "workspace",
    label: "Workspace",
    hint: "Files & notebooks",
    icon: FolderOpen,
  },
  {
    id: "databases",
    label: "Databases",
    hint: "Browse & import",
    icon: Server,
  },
  {
    id: "schema",
    label: "Schema Explorer",
    hint: "Delta + Iceberg",
    icon: FolderTree,
  },
  {
    id: "storage",
    label: "Storage Inspector",
    hint: "Physical files",
    icon: HardDrive,
  },
  {
    id: "spark",
    label: "Spark Settings",
    hint: "Runtime & installs",
    icon: Cpu,
  },
];

export function Sidebar({ view, onViewChange, health, online }: SidebarProps) {
  const sparkState = !online
    ? "Backend offline"
    : health?.spark_initialized
      ? `Spark ${health.spark_version ?? "warm"}`
      : "Spark cold (lazy)";

  return (
    <aside className="flex w-[76px] shrink-0 flex-col border-r border-border/80 bg-card/70 backdrop-blur-xl xl:w-64">
      <div className="flex h-[76px] items-center justify-center gap-3 border-b border-border/80 px-3 xl:justify-start xl:px-5">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary/15 text-primary ring-1 ring-inset ring-primary/30">
          <Layers className="size-5" />
        </div>
        <div className="hidden min-w-0 xl:block">
          <p className="truncate text-sm font-semibold tracking-tight">
            Open Lakehouse
          </p>
          <p className="text-[11px] text-muted-foreground">
            Local workbench v0.1
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        <p className="mb-2 hidden px-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/70 xl:block">
          Workspace
        </p>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = view === item.id;
          return (
            <button
              key={item.id}
              type="button"
              title={item.label}
              onClick={() => onViewChange(item.id)}
              className={cn(
                "group flex w-full items-center justify-center gap-3 rounded-lg px-2 py-2.5 text-left transition-colors xl:justify-start xl:px-3",
                active
                  ? "bg-primary/10 text-primary ring-1 ring-inset ring-primary/25"
                  : "text-muted-foreground hover:bg-accent/70 hover:text-foreground",
              )}
            >
              <Icon
                className={cn(
                  "size-[18px] shrink-0",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              />
              <span className="hidden min-w-0 flex-1 xl:block">
                <span className="block truncate text-sm font-medium">
                  {item.label}
                </span>
                <span className="block truncate text-[10px] text-muted-foreground">
                  {item.hint}
                </span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="border-t border-border/80 p-3">
        <div className="hidden rounded-lg border border-border/70 bg-background/40 p-3 xl:block">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "size-2 rounded-full",
                online
                  ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
                  : "bg-red-500",
              )}
            />
            <span className="text-xs font-medium">
              {online ? "Backend online" : "Backend offline"}
            </span>
          </div>
          <p className="mt-1 truncate text-[10px] text-muted-foreground">
            {sparkState}
          </p>
          {health ? (
            <p
              className="mt-2 truncate font-mono text-[10px] text-muted-foreground/80"
              title={health.warehouse}
            >
              {shortPath(health.warehouse, 30)}
            </p>
          ) : (
            <p className="mt-2 truncate font-mono text-[10px] text-muted-foreground/80">
              {API_BASE_URL}
            </p>
          )}
          <a
            href={API_DOCS_URL}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
          >
            <Database className="size-3" />
            API docs
            <ExternalLink className="size-3" />
          </a>
        </div>

        <div className="flex justify-center xl:hidden">
          <span
            title={sparkState}
            className={cn(
              "size-2.5 rounded-full",
              online ? "bg-emerald-400" : "bg-red-500",
            )}
          />
        </div>
      </div>
    </aside>
  );
}
