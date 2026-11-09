import { useCallback, useEffect, useState } from "react";

import { DatabasesPage } from "@/components/databases-page";
import { JvmEditor } from "@/components/jvm-editor";
import { useEditorBuffers } from "@/lib/editor-buffers";
import { PySparkEditor } from "@/components/pyspark-editor";
import { SchemaExplorer } from "@/components/schema-explorer";
import { Sidebar, type WorkbenchView } from "@/components/sidebar";
import { SparkSettings } from "@/components/spark-settings";
import { SqlEditor } from "@/components/sql-editor";
import { StorageInspector } from "@/components/storage-inspector";
import { TopBar } from "@/components/top-bar";
import { WorkspacePage } from "@/components/workspace-page";
import {
  ApiError,
  executeJvm,
  executePySpark,
  executeSql,
  getHealth,
  type ExecutePySparkResponse,
  type ExecuteSqlResponse,
  type HealthResponse,
  type JvmLanguage,
  type JvmRunResponse,
} from "@/lib/api";
import {
  DEFAULT_JAVA,
  DEFAULT_PYSPARK,
  DEFAULT_SCALA,
  DEFAULT_SQL,
} from "@/lib/samples";

interface JvmRunState {
  result: JvmRunResponse | null;
  error: string | null;
  running: boolean;
}

export default function App() {
  const [view, setView] = useState<WorkbenchView>("sql");
  const sqlTabs = useEditorBuffers("Query {n}", DEFAULT_SQL);
  const sql = sqlTabs.source;
  const setSql = sqlTabs.setSource;
  const [sqlResult, setSqlResult] = useState<ExecuteSqlResponse | null>(null);
  const [sqlError, setSqlError] = useState<string | null>(null);
  const [sqlRunning, setSqlRunning] = useState(false);

  const pysparkTabs = useEditorBuffers("Script {n}", DEFAULT_PYSPARK);
  const pyspark = pysparkTabs.source;
  const setPyspark = pysparkTabs.setSource;
  const [pysparkResult, setPysparkResult] = useState<ExecutePySparkResponse | null>(
    null,
  );
  const [pysparkError, setPysparkError] = useState<string | null>(null);
  const [pysparkRunning, setPysparkRunning] = useState(false);

  const javaTabs = useEditorBuffers("Java {n}", DEFAULT_JAVA);
  const scalaTabs = useEditorBuffers("Scala {n}", DEFAULT_SCALA);
  const [jvm, setJvm] = useState<Record<JvmLanguage, JvmRunState>>({
    java: { result: null, error: null, running: false },
    scala: { result: null, error: null, running: false },
  });

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [online, setOnline] = useState(false);

  useEffect(() => {
    let active = true;

    const checkHealth = async () => {
      try {
        const nextHealth = await getHealth();
        if (active) {
          setHealth(nextHealth);
          setOnline(true);
        }
      } catch {
        if (active) {
          setHealth(null);
          setOnline(false);
        }
      }
    };

    void checkHealth();
    const timer = window.setInterval(checkHealth, 8_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const nextHealth = await getHealth();
      setHealth(nextHealth);
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  const runQuery = useCallback(async () => {
    if (!sql.trim() || sqlRunning) return;
    setSqlRunning(true);
    setSqlError(null);
    try {
      const response = await executeSql(sql);
      setSqlResult(response);
      if (!online) setOnline(true);
    } catch (err) {
      setSqlResult(null);
      setSqlError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "The query failed.",
      );
    } finally {
      setSqlRunning(false);
      void refreshHealth();
    }
  }, [online, refreshHealth, sql, sqlRunning]);

  const runPySpark = useCallback(async () => {
    if (!pyspark.trim() || pysparkRunning) return;
    setPysparkRunning(true);
    setPysparkError(null);
    try {
      const response = await executePySpark(pyspark);
      setPysparkResult(response);
      if (!online) setOnline(true);
    } catch (err) {
      setPysparkResult(null);
      setPysparkError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "The script failed.",
      );
    } finally {
      setPysparkRunning(false);
      void refreshHealth();
    }
  }, [online, pyspark, pysparkRunning, refreshHealth]);

  const updateJvm = useCallback(
    (language: JvmLanguage, patch: Partial<JvmRunState>) => {
      setJvm((prev) => ({ ...prev, [language]: { ...prev[language], ...patch } }));
    },
    [],
  );

  const runJvm = useCallback(
    async (language: JvmLanguage, source: string) => {
      if (!source.trim() || jvm[language].running) return;
      updateJvm(language, { running: true, error: null });
      try {
        const response = await executeJvm(language, source);
        updateJvm(language, { result: response });
        if (!online) setOnline(true);
      } catch (err) {
        updateJvm(language, {
          result: null,
          error: err instanceof Error ? err.message : "The program failed.",
        });
      } finally {
        updateJvm(language, { running: false });
      }
    },
    [jvm, online, updateJvm],
  );

  const useTable = useCallback(
    (fullName: string) => {
      setSql(`SELECT * FROM ${fullName} LIMIT 100;\n`);
      setView("sql");
    },
    [setSql],
  );

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden bg-background">
      <TopBar />
      <div className="flex min-h-0 flex-1">
      <Sidebar
        view={view}
        onViewChange={setView}
        health={health}
        online={online}
      />

      <main className="workbench-glow relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-grid opacity-[0.22]" />
        <div className="relative flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1680px] p-5 lg:p-7 xl:p-8">
            {view === "sql" ? (
              <SqlEditor
                tabs={sqlTabs}
                sql={sql}
                onSqlChange={setSql}
                onRun={runQuery}
                running={sqlRunning}
                result={sqlResult}
                error={sqlError}
                online={online}
                onImported={refreshHealth}
              />
            ) : null}
            {view === "pyspark" ? (
              <PySparkEditor
                tabs={pysparkTabs}
                script={pyspark}
                onScriptChange={setPyspark}
                onRun={runPySpark}
                running={pysparkRunning}
                result={pysparkResult}
                error={pysparkError}
              />
            ) : null}
            {view === "java" ? (
              <JvmEditor
                tabs={javaTabs}
                language="java"
                source={javaTabs.source}
                onSourceChange={javaTabs.setSource}
                onRun={() => void runJvm("java", javaTabs.source)}
                running={jvm.java.running}
                result={jvm.java.result}
                error={jvm.java.error}
              />
            ) : null}
            {view === "scala" ? (
              <JvmEditor
                tabs={scalaTabs}
                language="scala"
                source={scalaTabs.source}
                onSourceChange={scalaTabs.setSource}
                onRun={() => void runJvm("scala", scalaTabs.source)}
                running={jvm.scala.running}
                result={jvm.scala.result}
                error={jvm.scala.error}
              />
            ) : null}
            {view === "databases" ? (
              <DatabasesPage
                online={online}
                onImported={refreshHealth}
                onUseTable={useTable}
              />
            ) : null}
            {view === "workspace" ? <WorkspacePage online={online} /> : null}
            {view === "schema" ? (
              <SchemaExplorer onUseTable={useTable} online={online} />
            ) : null}
            {view === "storage" ? <StorageInspector online={online} /> : null}
            {view === "spark" ? <SparkSettings online={online} /> : null}
          </div>
        </div>
      </main>
      </div>
    </div>
  );
}
