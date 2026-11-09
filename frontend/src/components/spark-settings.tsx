import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  Download,
  FolderOpen,
  Loader2,
  Package,
  RefreshCw,
  RotateCcw,
} from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ApiError,
  browseSparkHome,
  getSparkConfig,
  getSparkDownloadStatus,
  resetSparkHome,
  setSparkHome,
  startSparkDownload,
  type SparkConfigResponse,
  type SparkDownloadStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const ACTIVE_DOWNLOAD_STATES = new Set([
  "starting",
  "running",
  "extracting",
  "installing",
]);

function toErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "The request failed.";
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  return `${(bytes / 1024 ** exponent).toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

function formatSpeed(bytesPerSecond: number): string {
  return `${formatBytes(bytesPerSecond)}/s`;
}

export function SparkSettings({ online }: { online: boolean }) {
  const [config, setConfig] = useState<SparkConfigResponse | null>(null);
  const [path, setPath] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<
    null | "browse" | "apply" | "reset" | "download"
  >(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [download, setDownload] = useState<SparkDownloadStatus | null>(null);
  const pollRef = useRef<number | null>(null);

  const applyConfig = useCallback((next: SparkConfigResponse) => {
    setConfig(next);
    setPath(next.configured_home ?? next.effective.path);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await getSparkConfig();
      applyConfig(next);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [applyConfig]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const state = download?.state;
    if (!state || !ACTIVE_DOWNLOAD_STATES.has(state)) {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    const tick = async () => {
      try {
        const status = await getSparkDownloadStatus();
        setDownload(status);
        if (!ACTIVE_DOWNLOAD_STATES.has(status.state)) {
          void refresh();
        }
      } catch {
        // Keep polling; a transient error should not stop the UI.
      }
    };

    pollRef.current = window.setInterval(() => void tick(), 1_200);
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [download?.state, refresh]);

  const handleBrowse = useCallback(async () => {
    setBusy("browse");
    setError(null);
    setNotice(null);
    try {
      const result = await browseSparkHome();
      if (result.path) {
        setPath(result.path);
        setNotice("Folder selected. Click “Use this Spark” to apply it.");
      }
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }, []);

  const handleApply = useCallback(async () => {
    if (!path.trim()) return;
    setBusy("apply");
    setError(null);
    setNotice(null);
    try {
      const next = await setSparkHome(path.trim());
      applyConfig(next);
      setNotice("Spark installation updated. The next query starts a fresh session.");
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }, [applyConfig, path]);

  const handleReset = useCallback(async () => {
    setBusy("reset");
    setError(null);
    setNotice(null);
    try {
      const next = await resetSparkHome();
      applyConfig(next);
      setNotice("Reverted to the Spark distribution bundled with PySpark.");
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }, [applyConfig]);

  const handleDownload = useCallback(async () => {
    if (!config) return;
    setBusy("download");
    setError(null);
    setNotice(null);
    try {
      const status = await startSparkDownload({
        version: config.download_available_version,
      });
      setDownload(status);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }, [config]);

  const effective = config?.effective;
  const isExternal = config?.configured_source !== "bundled";
  const downloading = download ? ACTIVE_DOWNLOAD_STATES.has(download.state) : false;
  const downloadError = download?.state === "error" ? download.error : null;
  const downloadDone = download?.state === "done";

  return (
    <div className="animate-fade-in space-y-5">
      <PageHeader
        eyebrow="Runtime"
        title="Spark Settings"
        description="Choose which Apache Spark installation powers the workbench. The bundled PySpark distribution works out of the box; you can point the backend at a compatible local Spark release or install one here."
        actions={
          <>
            <Badge variant="info">PySpark {config?.pyspark_version ?? "…"}</Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void refresh()}
              disabled={loading || !online}
            >
              <RefreshCw className={cn(loading && "animate-spin")} />
              Refresh
            </Button>
          </>
        }
      />

      {error ? (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-red-300">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span className="whitespace-pre-wrap">{error}</span>
        </div>
      ) : null}

      {notice ? (
        <div className="flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
          <span className="whitespace-pre-wrap">{notice}</span>
        </div>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Cpu className="size-4 text-primary" />
                <CardTitle>Active Spark</CardTitle>
              </div>
              {effective ? (
                <Badge
                  variant={
                    effective.source === "bundled"
                      ? "info"
                      : effective.compatible
                        ? "success"
                        : "destructive"
                  }
                >
                  {effective.source === "bundled"
                    ? "Bundled"
                    : effective.compatible
                      ? "External"
                      : "Incompatible"}
                </Badge>
              ) : null}
            </div>
            <CardDescription>
              The session in use by the SQL and PySpark editors.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {effective ? (
              <>
                <dl className="grid grid-cols-[120px_1fr] gap-y-2">
                  <dt className="text-muted-foreground">Spark version</dt>
                  <dd className="font-mono text-xs">{effective.version ?? "unknown"}</dd>
                  <dt className="text-muted-foreground">Scala</dt>
                  <dd className="font-mono text-xs">
                    {effective.scala_version ?? "unknown"}
                  </dd>
                  <dt className="text-muted-foreground">Location</dt>
                  <dd className="break-all font-mono text-[11px] text-muted-foreground">
                    {effective.path}
                  </dd>
                  <dt className="text-muted-foreground">Session</dt>
                  <dd>
                    {config?.spark_started
                      ? `Warm · Spark ${config.spark_version ?? ""}`
                      : "Cold (starts on next query)"}
                  </dd>
                  <dt className="text-muted-foreground">Required</dt>
                  <dd className="font-mono text-xs">
                    Spark {config?.required_spark_version} · Scala 2.13
                  </dd>
                </dl>
                {!effective.compatible && effective.reason ? (
                  <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-red-300">
                    {effective.reason}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="text-muted-foreground">Loading configuration…</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FolderOpen className="size-4 text-primary" />
              <CardTitle>Use a local Spark installation</CardTitle>
            </div>
            <CardDescription>
              Select a Spark {config?.required_spark_version ?? "4.1.x"} folder that
              contains <span className="font-mono">bin/</span> and{" "}
              <span className="font-mono">jars/</span>.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                value={path}
                onChange={(event) => setPath(event.target.value)}
                placeholder="C:\\path\\to\\spark-4.1.x-bin-hadoop3"
                spellCheck={false}
                className="h-9 min-w-0 flex-1 rounded-md border border-input bg-background/60 px-3 font-mono text-xs outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-primary/60 focus:ring-1 focus:ring-primary/30"
              />
              <Button
                variant="outline"
                size="sm"
                className="h-9"
                onClick={() => void handleBrowse()}
                disabled={!online || busy !== null}
              >
                {busy === "browse" ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <FolderOpen />
                )}
                Browse…
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                onClick={() => void handleApply()}
                disabled={!online || busy !== null || !path.trim()}
              >
                {busy === "apply" ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <CheckCircle2 />
                )}
                Use this Spark
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => void handleReset()}
                disabled={!online || busy !== null || !isExternal}
              >
                {busy === "reset" ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <RotateCcw />
                )}
                Use bundled
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Detection runs server-side. A folder must match the PySpark client
              version and the Scala 2.13 connectors or it is rejected with the
              reason.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Package className="size-4 text-primary" />
              <CardTitle>Download &amp; install Spark</CardTitle>
            </div>
            <Badge variant="outline">
              Spark {config?.download_available_version ?? "4.1.x"}
            </Badge>
          </div>
          <CardDescription>
            Optional: fetch an Apache Spark release matching this backend
            ({"≈"} 570 MB) and select it automatically. Requires internet access.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={() => void handleDownload()}
              disabled={!online || busy !== null || downloading}
            >
              {busy === "download" || downloading ? (
                <Loader2 className="animate-spin" />
              ) : (
                <Download />
              )}
              {downloading
                ? "Installing…"
                : downloadDone
                  ? "Download again"
                  : "Download & install"}
            </Button>
            {config ? (
              <span
                className="truncate font-mono text-[11px] text-muted-foreground"
                title={config.download_dir}
              >
                → {config.download_dir}
              </span>
            ) : null}
          </div>

          {download && download.state !== "idle" ? (
            <div className="space-y-2 rounded-lg border border-border/70 bg-background/40 p-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium capitalize text-foreground/90">
                  {download.state}
                </span>
                <span className="font-mono text-[11px] text-muted-foreground">
                  {download.state === "running" || download.state === "done"
                    ? `${formatBytes(download.downloaded_bytes)} / ${
                        download.total_bytes
                          ? formatBytes(download.total_bytes)
                          : "?"
                      }`
                    : download.message}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{ width: `${Math.min(download.percent, 100)}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span>{download.message}</span>
                <span className="font-mono">
                  {download.percent.toFixed(1)}% ·{" "}
                  {formatSpeed(download.speed_bps)}
                </span>
              </div>
              {downloadError ? (
                <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-red-300">
                  {downloadError}
                </p>
              ) : null}
              {downloadDone && download.installed_path ? (
                <p className="break-all font-mono text-[11px] text-emerald-300">
                  Installed at {download.installed_path}
                </p>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
