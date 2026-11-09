# Open Lakehouse Workbench

A **100% local** lakehouse workbench for data analysts and engineers. It gives you SQL, PySpark, Java and Scala editors, a file workspace with Jupyter-style notebooks, a database browser, a catalog explorer, and a physical storage inspector. All of it runs over a single Apache Spark session that reads and writes **Delta Lake** and **Apache Iceberg** tables stored on your own filesystem.

Import CSV, JSON, Parquet, TXT, ORC, and Avro files, or connect to local MySQL, PostgreSQL, and SQL Server databases and import tables directly into Delta, Iceberg, or plain Spark tables.

No cloud account, no external catalog service, no cluster required.

```
┌──────────────────────────────────────────────────────────────────┐
│ React + TypeScript + Tailwind + Shadcn-style UI                  │
│  SQL · PySpark · Java · Scala · Workspace/Notebooks · Databases  │
│  Schema · Storage · Spark Settings                               │
└───────────────────────────────┬──────────────────────────────────┘
                                │ REST (FastAPI, 127.0.0.1:8000)
┌───────────────────────────────▼──────────────────────────────────┐
│ FastAPI                                                          │
│  /api/execute-sql  /api/execute-pyspark  /api/execute-jvm        │
│  /api/notebook/*   /api/workspace/*      /api/kernels            │
│  /api/import-*     /api/tables           /api/storage-explorer   │
│         │                │                 │                     │
│         ▼                ▼                 ▼                     │
│  SQL/PySpark engine  Java/Scala runner  Jupyter kernels          │
│  (shared session)    (javac/scalac +    (IJava, almond: one      │
│                       spark-submit)      kernel per notebook)    │
│         │                                                         │
│         ▼                                                         │
│  Single local SparkSession (thread-safe, lazily started)         │
│   ├─ spark_catalog   → DeltaCatalog → ./data_warehouse/delta     │
│   └─ local_iceberg   → Hadoop catalog → ./data_warehouse/iceberg │
└──────────────────────────────────────────────────────────────────┘
```

## Stack

| Layer | Technology |
| --- | --- |
| API | FastAPI, Uvicorn, Pydantic v2 |
| Execution | PySpark **4.1.4** (Java 17+, Scala 2.13) |
| Java / Scala | `javac` and the bundled Scala 2.13 compiler, run through `spark-submit` |
| Notebook kernels | `jupyter_client` 8.x; IJava (Java) and almond (Scala) kernels |
| Table formats | Delta Lake **4.3.1**, Apache Iceberg **1.12.0** (Spark 4.1 runtime) |
| Catalog/storage | Local filesystem (`data_warehouse/delta`, `data_warehouse/iceberg`) |
| UI | React 18, TypeScript, Vite, Tailwind CSS, Radix + Shadcn-style components |

> **Why Spark 4.1 and not 4.3?** Spark 4.3 is the latest Spark release, but Iceberg 1.12.0 publishes runtime jars for Spark 4.0/4.1 only. Spark 4.1.4 + Delta 4.3.1 + Iceberg 1.12.0 is the newest mutually supported combination. Versions are configurable in `backend/app/config.py` or via environment variables.

## Features

| Area | What you can do |
| --- | --- |
| **SQL Editor** | Run one or more Spark SQL statements (Ctrl/Cmd + Enter), with samples, several editor tabs (**New** button), results as a table or JSON (copy rows as JSON), and **Import file** to load CSV/JSON/Parquet/TXT/ORC/Avro. |
| **PySpark Editor** | Run PySpark scripts against the shared `spark` session. A returned or last assigned DataFrame is previewed. Editor tabs as above. |
| **Java / Scala Editors** | Compile and run a `Main` class (Java with `javac`, Scala with the bundled Scala 2.13 compiler) as a Spark job. Each run is a separate JVM. See [Java and Scala programs](#java-and-scala-programs). |
| **Workspace** | Open any folder on the backend machine, browse it, edit text files, and create new notebooks (**New notebook**). |
| **Notebooks** | Jupyter-style `.ipynb` notebooks with code and markdown cells, **Run all**, cell outputs, a per-notebook **kernel** (PySpark built-in, Java, or Scala), **Data source** loading, and save back to `.ipynb`. See [Notebooks](#notebooks). |
| **Databases** | Browse `databases.cfg` connections, list databases and tables, import tables into Delta/Iceberg/Spark, and open an imported table in the SQL editor. Saved connections can also be created in the UI. |
| **Schema Explorer** | Browse Delta and Iceberg namespaces and tables; click a table to query it. |
| **Storage Inspector** | Read-only tree of the warehouse folders with sizes and file counts. |
| **Spark Settings** | See the active Spark installation, choose a compatible local Spark folder, or download one. |
| **Appearance** | A fixed top bar sets the font size and dark/light theme for code editors and notebooks. |

## Project layout

```
warehouse/
├─ backend/
│  ├─ app/
│  │  ├─ api/routes.py              # REST endpoints
│  │  ├─ models/schemas.py          # Pydantic request/response models
│  │  ├─ services/
│  │  │  ├─ sql_engine.py           # Spark SQL execution, timeout, result materialisation
│  │  │  ├─ pyspark_engine.py       # PySpark cells/scripts; notebook namespaces; read_data_file / read_database helpers
│  │  │  ├─ jvm_runner.py           # Java/Scala compile + spark-submit runner
│  │  │  ├─ kernel_service.py       # Jupyter kernels for notebooks (IJava, almond); Java kernel installer
│  │  │  ├─ workspace.py            # Workspace folder tree, text files, notebook load/create
│  │  │  ├─ folder_picker.py        # Native folder/file pickers on the backend machine
│  │  │  ├─ importer.py             # CSV/JSON/Parquet/TXT/ORC/Avro → Delta/Iceberg/Spark
│  │  │  ├─ database_connections.py # Saved database connection CRUD
│  │  │  ├─ database_config.py      # Read databases.cfg and browse remote tables
│  │  │  ├─ jdbc_importer.py        # Import from JDBC sources
│  │  │  ├─ spark_setup.py          # Spark home detection, validation, download
│  │  │  ├─ runtime_settings.py     # UI-driven overrides persisted to .runtime_settings.json
│  │  │  ├─ sql_utils.py            # statement splitter/classifier, JSON sanitiser
│  │  │  ├─ catalog.py              # Delta + Iceberg namespace/table discovery
│  │  │  └─ storage.py              # path-guarded warehouse scanner
│  │  ├─ config.py                  # env-driven settings
│  │  ├─ spark_manager.py           # singleton local Spark session + SQL lock
│  │  └─ main.py                    # FastAPI app, CORS, lifespan
│  ├─ tests/                        # backend unit tests (pytest)
│  ├─ seed_demo.py                  # creates demo Iceberg + Delta tables
│  ├─ requirements.txt
│  └─ requirements-dev.txt
├─ frontend/                        # main React + TypeScript UI (port 5173)
│  ├─ src/
│  │  ├─ components/                # sidebar, top bar, editors, notebook, workspace, databases, ui/*
│  │  ├─ lib/                       # API client, samples, editor preferences and buffers, utils
│  │  ├─ App.tsx
│  │  └─ main.tsx
│  ├─ package.json
│  ├─ tailwind.config.js
│  └─ vite.config.ts
├─ frontend-ts/                     # TypeScript-only copy of the UI (port 5174)
├─ docs/
│  ├─ book/                         # Multi-page online book (HTML + Markdown)
│  └─ getting-started.html / .md    # Startup quick-start guide
├─ scripts/
│  ├─ start-backend.ps1 / .sh / .bat
│  ├─ start-frontend.ps1 / .sh / .bat
│  ├─ start-frontend-ts.ps1 / .bat
│  └─ start-all.ps1 / .bat
├─ data_warehouse/
│  ├─ delta/                        # managed Delta tables + _delta_log
│  └─ iceberg/                      # Iceberg metadata + Parquet data
├─ .spark_metastore/                # embedded Derby Hive metastore (generated)
├─ .spark_tmp/                      # Spark and Java/Scala run temp files (generated)
├─ .env.example
└─ README.md
```

## Prerequisites

- **Python 3.11+** (the start scripts check for it)
- **Java 17+** to 21  — `JAVA_HOME` set and `java -version` on PATH. The Java and Scala editors and kernels use the same JDK.
- **Node.js 20+** and npm
- **Internet access on first Spark startup** to download the Delta/Iceberg jars from Maven Central (Maven coordinates are in `backend/app/config.py`)
- **Windows only:** Hadoop `winutils.exe` + `hadoop.dll`, with `HADOOP_HOME` pointed at the Hadoop directory (see [Windows setup](#windows-setup))
- **Optional:** a Java and/or Scala Jupyter kernel for notebooks (see [Java and Scala notebook kernels](#java-and-scala-notebook-kernels))

## Quick start

to run double click:  scripts\start-all.bat


From the repository root:

```powershell
# Terminal 1 — FastAPI + Spark (creates .venv and installs deps on first run)
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1

# Terminal 2 — React UI   || in this fole change frontend to frontend-ts to run typescript version ... 
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Or start both (`start-all.ps1` opens the backend in a new window):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-all.ps1
```

On Windows you can also double-click (or run from `cmd`) the batch wrappers:

```bat
scripts\start-backend.bat
scripts\start-frontend.bat
scripts\start-all.bat
```

Open **http://127.0.0.1:5173** for the workbench and **http://127.0.0.1:8000/docs** for the OpenAPI UI. The `frontend-ts` copy runs on **http://127.0.0.1:5174**.

## Documentation

- **Getting Started for Startups**: open `docs/getting-started.html` in a browser or read `docs/getting-started.md`.
- **Online Book**: open `docs/book/index.html` for a multi-page guide to big data transformation with Spark, Delta, and Iceberg, or read `docs/book/index.md`.

The book includes copy-paste SQL and PySpark examples that run directly in the workbench.

### macOS / Linux

```bash
./scripts/start-backend.sh     # terminal 1
./scripts/start-frontend.sh    # terminal 2
```

### Manual launch

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

The first SQL query starts Spark and downloads the connector jars; it can take 30–90 seconds. The UI health indicator changes from **Spark cold** to **Spark warm** once the session exists.

## Seed demo data

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python seed_demo.py
```

This creates:

- **Delta:** `demo.customers` (also addressable as `spark_catalog.demo.customers`)
- **Iceberg:** `local_iceberg.demo.sales`

Run the seed script while the backend is **stopped**: Delta metadata lives in an embedded Derby Hive metastore (`<repo>/.spark_metastore`) that allows only one JVM at a time.

Then try:

```sql
SELECT * FROM local_iceberg.demo.sales ORDER BY sold_at DESC LIMIT 100;

SELECT country, count(*) AS customers
FROM demo.customers
GROUP BY country
ORDER BY customers DESC;
```

Multi-statement scripts are executed in order (semicolons inside strings/comments are handled):

```sql
CREATE TABLE IF NOT EXISTS demo.orders (
  order_id BIGINT,
  customer_id BIGINT,
  total DOUBLE,
  ordered_at TIMESTAMP
) USING delta;

INSERT INTO demo.orders VALUES (1001, 1, 249.99, current_timestamp());
SELECT * FROM demo.orders;
```

## Using the workbench

### SQL and PySpark editors

- Each editor has tabs. **New** adds an empty tab; click a tab to switch, and × to close it (the last tab stays).
- **Samples** insert example code into the active tab; **Reset** restores the default code.
- Run the active tab with the **Run** button or Ctrl/Cmd + Enter.
- In the PySpark editor the variable `spark` is already bound to the shared session. Return or assign a DataFrame to see a preview.
- Clicking a table in the Schema Explorer writes a `SELECT` into the active SQL tab.

### Java and Scala programs

The **Java Editor** and **Scala Editor** pages compile and run a single program:

- Define `public class Main` (Java) or `object Main` (Scala) with a `main` method.
- Compiler errors are shown and the program is not run.
- The program output (stdout and stderr) is shown below the editor.
- Each run starts a **new JVM** through `spark-submit`, so it takes about 15–40 seconds and variables do not carry between runs. Create the SparkSession inside your program (`SparkSession.builder().getOrCreate()`).
- Runs use an **in-memory catalog**, because the backend holds the Derby metastore lock. Delta and Iceberg tables can be read by path (for example `spark.read().format("delta").load(path)`), but tables registered only in the backend metastore are not visible from these programs. The PySpark editor and SQL editor are the right place for work on the shared catalog.

### Workspace and files

- **Workspace** opens a folder on the backend machine (**Browse…** opens a native folder picker, or type the path and **Open**).
- The explorer lists text, script, JSON/CSV and notebook (`.ipynb`) files. Click a text file to edit and **Save** it; click a `.ipynb` file to open it as a notebook. Parquet and other binary data files are not listed; open them with **Data source** → **Browse file system…**.
- **New notebook** (header or explorer) creates an empty `.ipynb` in the open folder. Enter a name, optionally with subfolders such as `analysis/first.ipynb`. The folder must already exist.
- Paths are checked against the open folder; `..` and absolute paths outside it are refused.

### Notebooks

Open a notebook from the Workspace explorer.

- **Cells:** add **Code** and **Markdown** cells. Run one cell with its run button, or all code cells with **Run all**. Variables persist between cells of the same notebook.
- **Kernel:** the **Kernel** dropdown in the header chooses the language for the notebook:
  - **Python 3 (PySpark built-in)** — the default. Runs in the backend's PySpark session, with `spark` bound.
  - **Java** and **Scala** — kernels installed on your machine (see [Java and Scala notebook kernels](#java-and-scala-notebook-kernels)). Each notebook keeps its own kernel process, so variables persist between its cells. The Java kernel is not connected to the PySpark session.
  - A notebook whose kernel is not installed shows “(not installed)” in the dropdown; cells fail with a clear message until you install it or pick another kernel.
- **Reset kernel** clears the variables and stops the non-Python kernels of this notebook.
- The kernel is saved in the notebook file (`metadata.kernelspec`), so Jupyter opens it with the same kernel name.
- **Save** writes the notebook back to `.ipynb`. Outputs are not saved, only the cell sources and kernel.
- Code cells use the font size and theme from the top bar.

### Loading data (Data source)

**Data source** in the notebook header inserts a new code cell that loads data:

- **Files:** browse the file system with **Browse file system…** (native file picker on the backend machine), choose a file from the open workspace folder, or type a **logical path** (relative to the workspace folder) or an absolute path. The cell calls `read_data_file("...")`. CSV/TSV use a header row and inferred types; JSON, Parquet, ORC, Avro, and text are supported.
- **Database:** choose a `databases.cfg` connection, a database, and a table. The cell calls `read_database("connection", "table", database="...")`. Credentials stay in the backend configuration and are not written into the notebook.

These helpers are available in the built-in PySpark kernel only. They run in the backend process.

### Databases

- **Connections** come from `databases.cfg` and from connections you create in the UI (see [Database connections](#database-connections)).
- Pick a connection and a database. The page lists its tables. Use **Preview** for a sample of rows.
- **Import** copies a table into Delta, Iceberg, or a plain Spark table in the chosen namespace. Choose the write mode (error if exists, overwrite, or append).
- After an import, **Query in SQL editor** opens the table in the SQL editor. You can also find it in the Schema Explorer.
- **Import file** (SQL editor and Schema Explorer) loads a local CSV/JSON/Parquet/TXT/ORC/Avro file into a table.

### Schema Explorer and Storage Inspector

- **Schema Explorer** lists the `spark_catalog` (Delta) and `local_iceberg` namespaces and their tables with format and location. Click a table to query it in the SQL editor.
- **Storage Inspector** shows the physical folders under `data_warehouse/` read-only, with depth controls and breadcrumbs.

### Spark Settings

See [Spark installation](#spark-installation-bundled-vs-local).

### Appearance

The **top bar** (1 cm high, above every page) has two selectors:

- **Font:** 12–22 px for the code in the SQL, PySpark, Java, Scala editors and the notebook.
- **Theme:** **Dark** or **Light**. The theme switches the whole interface. Code colours can be changed per theme in each editor's colour settings.

The choices are saved in the browser.

## Java and Scala notebook kernels

Notebooks run Python cells on the built-in PySpark engine. A notebook can also use a **Java** or **Scala** Jupyter kernel, selected in the notebook's **Kernel** dropdown. Kernels run in their own process and are started on the first cell.

Requirements for both kernels: a JDK 17+ on `PATH` or `JAVA_HOME`, and internet access for the first install and first start (dependencies are downloaded).

The backend finds kernels that are installed in standard Jupyter locations. It also scans `%LOCALAPPDATA%\Programs\Python\Python*\share\jupyter\kernels` on Windows. Non-Python kernels such as the C++ kernels are listed too.

### Java kernel (IJava)

**From the UI:** open a notebook. If no Java kernel is installed, the header shows **Install Java kernel**. Click it. The backend downloads IJava 1.3.0 from GitHub and registers it in your user Jupyter folder:

- Windows: `%APPDATA%\jupyter\kernels\java`
- Linux/macOS: `~/.local/share/jupyter/kernels/java`

The message on the page confirms the location. Select **Java** in the Kernel dropdown.

**Manual install (if the download is blocked or you prefer it):**

1. Download `ijava-1.3.0.zip` from https://github.com/SpencerPark/IJava/releases/tag/v1.3.0 and extract `ijava-1.3.0.jar`.
2. Create `<jupyter data dir>/kernels/java/kernel.json` with the jar path set to where you extracted it:

```json
{
  "argv": [
    "java",
    "--add-exports=java.base/sun.nio.ch=ALL-UNNAMED",
    "--add-opens=java.base/java.lang=ALL-UNNAMED",
    "-jar",
    "C:/path/to/ijava-1.3.0.jar",
    "{connection_file}"
  ],
  "display_name": "Java (IJava 1.3.0)",
  "language": "java",
  "interrupt_mode": "message"
}
```

3. Reload the workbench page. **Java** appears in the Kernel dropdown.

### Scala kernel (almond)

The Scala kernel is [almond](https://almond.sh). The workbench does not install it; install it once with coursier:

```powershell
# Windows (PowerShell, in an empty folder)
bitsadmin /transfer downloadCoursierBat https://git.io/coursier-bat "$PWD\coursier.bat"
.\coursier.bat launch --use-bootstrap almond -M almond.ScalaKernel -- --install
```

```bash
# Linux / macOS
curl -Lo coursier https://git.io/coursier-cli && chmod +x coursier
./coursier launch --use-bootstrap almond -- --install
rm -f coursier
```

The installer registers a kernel named `scala`. Reload the workbench page and select **Scala** in the Kernel dropdown. The first start is slow (dependency download). Update with `-- --install --force`; remove with `jupyter kernelspec remove scala`.

### Using Spark from Java or Scala notebooks

A kernel does not start Spark by itself. Add the Spark dependencies in the first cell and create the session in your code, using the same version as the PySpark engine (Spark 4.1.x, Scala 2.13):

- Java kernel: `%maven org.apache.spark:spark-sql_2.13:4.1.4`
- Scala kernel: `import $ivy.\`org.apache.spark::spark-sql:4.1.4\``

Delta and Iceberg tables are reached through the same catalog settings as in the Java/Scala editors (see [Java and Scala programs](#java-and-scala-programs)). The kernel session is separate from the backend session.

## Database connections

Create a file named `databases.cfg` in the repository root to pre-define connections:

```ini
[mysql.local_mysql]
name=Local MySQL
host=localhost
port=3306
database=mydb
username=root
password=changeme

[postgresql.local_postgres]
name=Local PostgreSQL
host=localhost
port=5432
database=mydb
username=postgres
password=changeme

[sqlserver.local_sqlserver]
name=Local SQL Server
host=localhost
port=1433
database=mydb
username=sa
password=Changeme1
```

The **Databases** page reads this file, lists remote databases and tables, and lets you import them into Delta, Iceberg, or Spark tables. You can also create, test, and edit connections in the UI (Databases page, or the **Database** tab of **Import file**). Connections created in the UI are saved to `data_warehouse/.connections.json`.

> **Security:** `databases.cfg` and `data_warehouse/.connections.json` store passwords in plain text. Keep them out of version control; `.gitignore` does not list `databases.cfg` yet, so add it before committing.

## REST API

All paths are under `/api`. The interactive OpenAPI page is at `http://127.0.0.1:8000/docs`.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Backend status, warehouse path, Spark warm/cold state and version. |
| `POST` | `/api/execute-sql` | Run one or more SQL statements. Body: `{ "sql": "...", "max_rows": 1000, "timeout_seconds": 300 }`. |
| `POST` | `/api/execute-pyspark` | Run a PySpark script with `spark` bound to the shared SparkSession. Body: `{ "script": "...", "timeout_seconds": 300 }`. |
| `POST` | `/api/execute-jvm` | Compile and run a Java or Scala `Main` as a Spark job. Body: `{ "language": "java" \| "scala", "source": "...", "timeout_seconds": 600 }`. |
| `POST` | `/api/import-file` | Import CSV, JSON, Parquet, TXT, ORC, or Avro into Delta, Iceberg, or a Spark table. |
| `POST` | `/api/import-database` | Import a table from a saved connection or `databases.cfg` connection. |
| `GET/POST` | `/api/connections` | List and create saved database connections (UI-managed). |
| `PUT/DELETE` | `/api/connections/{id}` | Update or delete a saved connection. |
| `POST` | `/api/connections/{id}/test` | Test a saved connection. |
| `POST` | `/api/connections/{id}/preview` | Preview rows of a remote table. |
| `GET` | `/api/database-config/connections` | List connections defined in `databases.cfg`. |
| `GET` | `/api/database-config/connections/{id}/databases` | List databases of a `databases.cfg` connection. |
| `GET` | `/api/database-config/connections/{id}/tables?database=` | List tables of a `databases.cfg` connection, optionally for one database. |
| `GET` | `/api/tables?include_details=true` | Namespaces and tables for `delta` (`spark_catalog`) and `local_iceberg`. |
| `GET` | `/api/storage-explorer?path=&depth=&max_entries=` | Read-only filesystem tree of `data_warehouse` (defaults from `LAKEHOUSE_STORAGE_MAX_DEPTH` and `LAKEHOUSE_STORAGE_MAX_ENTRIES`). |
| `GET` | `/api/spark/config` | Active/compatible Spark installation, PySpark version and detected releases. |
| `POST` | `/api/spark/home` | Select a local Spark home (`{ "path": "..." }`); restarts the session. |
| `DELETE` | `/api/spark/home` | Revert to the Spark bundled with PySpark. |
| `POST` | `/api/spark/browse` | Open a native folder picker on the backend machine. |
| `POST` | `/api/spark/download` | Download & install a compatible Spark release in the background. |
| `GET` | `/api/spark/download/status` | Progress of the background Spark download. |
| `GET` | `/api/workspace` | The open workspace folder and its file tree. |
| `POST` | `/api/workspace/open` | Open a folder with the native folder picker. |
| `POST` | `/api/workspace/root` | Open a folder by path: `{ "path": "..." }`. |
| `DELETE` | `/api/workspace/root` | Close the workspace folder. |
| `GET/PUT` | `/api/workspace/file` | Read or save a text file in the workspace (`?path=` / `{ "path", "content" }`). |
| `GET` | `/api/workspace/notebook?path=` | Load a `.ipynb` file with its cells and kernel. |
| `POST` | `/api/workspace/notebook` | Create an empty notebook: `{ "path": "name.ipynb" }` (returns 201). |
| `POST` | `/api/files/pick` | Open a native file picker on the backend machine (used by Data source). |
| `POST` | `/api/notebook/execute` | Run a notebook cell: `{ "notebook_id", "script", "kernel_name"?, "timeout_seconds"? }`. Without a non-Python `kernel_name` the cell runs on the PySpark kernel. |
| `POST` | `/api/notebook/reset` | Clear a notebook's variables and stop its non-Python kernels: `{ "notebook_id" }`. |
| `GET` | `/api/kernels` | Notebook kernels: the built-in PySpark kernel plus installed Java/Scala/other kernels. |
| `POST` | `/api/kernels/java/install` | Download and register the IJava Java kernel (no-op if a Java kernel exists). |

Example:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/execute-sql `
  -H "Content-Type: application/json" `
  -d '{\"sql\":\"SELECT * FROM local_iceberg.demo.sales LIMIT 5\"}'
```

Errors are returned as non-2xx responses with a plain-text `detail`. Spark analysis errors return `400`, timeouts return `408`, and an unavailable Spark session returns `503`. A failed Java/Scala compile returns `200` with `compile_ok: false` and the compiler output.

## Catalog semantics

| Catalog | Implementation | Warehouse | Query form |
| --- | --- | --- | --- |
| `spark_catalog` (shown as **delta**) | Delta Lake `DeltaCatalog` over an embedded Derby Hive metastore | `data_warehouse/delta` | `db.table` or `spark_catalog.db.table` |
| `local_iceberg` | Iceberg `SparkCatalog` with `type=hadoop` | `data_warehouse/iceberg` | `local_iceberg.db.table` |

The Derby metastore under `.spark_metastore/` is what makes Delta databases and tables survive backend restarts. Iceberg's Hadoop catalog stores table metadata directly in its warehouse, so it needs no metastore.

The `engine` field returned by the API is display metadata derived from the statement/current catalog; Spark itself remains the source of truth. `USE catalog.db` is supported, but remember the Spark session is shared by every browser tab.

## Configuration

Copy `.env.example` to `.env` in the repository root (or set variables directly). All backend variables use the `LAKEHOUSE_` prefix.

| Variable | Default |
| --- | --- |
| `LAKEHOUSE_APP_NAME` | `Open Lakehouse Workbench` |
| `LAKEHOUSE_API_PREFIX` | `/api` |
| `LAKEHOUSE_CORS_ORIGINS` | `http://localhost` and `http://127.0.0.1` on ports 5173, 5174, 4173, 4174 |
| `LAKEHOUSE_WAREHOUSE_DIR` | `<repo>/data_warehouse` |
| `LAKEHOUSE_SPARK_METASTORE_DIR` | `<repo>/.spark_metastore` |
| `LAKEHOUSE_SPARK_LOCAL_DIR` | `<repo>/.spark_tmp` (Spark temp files and Java/Scala/kernel run folders) |
| `LAKEHOUSE_SPARK_APP_NAME` | `OpenLakehouseWorkbench` |
| `LAKEHOUSE_SPARK_MASTER` | `local[*]` |
| `LAKEHOUSE_SPARK_DRIVER_MEMORY` | `2g` |
| `LAKEHOUSE_SPARK_LOG_LEVEL` | `WARN` |
| `LAKEHOUSE_SPARK_HOME` | unset (use the Spark bundled with PySpark) |
| `LAKEHOUSE_SPARK_DIST_DIR` | `<repo>/.spark_dist` |
| `LAKEHOUSE_RUNTIME_SETTINGS_FILE` | `<repo>/.runtime_settings.json` |
| `LAKEHOUSE_DELTA_PACKAGE` | `io.delta:delta-spark_2.13:4.3.1` |
| `LAKEHOUSE_ICEBERG_PACKAGE` | `org.apache.iceberg:iceberg-spark-runtime-4.1_2.13:1.12.0` |
| `LAKEHOUSE_AVRO_PACKAGE` | `org.apache.spark:spark-avro_2.13:4.1.4` |
| `LAKEHOUSE_JDBC_MYSQL_PACKAGE` | `com.mysql:mysql-connector-j:8.4.0` |
| `LAKEHOUSE_JDBC_POSTGRES_PACKAGE` | `org.postgresql:postgresql:42.7.3` |
| `LAKEHOUSE_JDBC_SQLSERVER_PACKAGE` | `com.microsoft.sqlserver:mssql-jdbc:12.6.1.jre11` |
| `LAKEHOUSE_DATABASE_CONFIG_FILE` | `<repo>/databases.cfg` |
| `LAKEHOUSE_SPARK_JARS` | unset (use Maven packages instead) |
| `LAKEHOUSE_SPARK_EXTRA_OPTIONS` | unset (semicolon-separated `key=value`) |
| `LAKEHOUSE_MAX_RESULT_ROWS` | `1000` |
| `LAKEHOUSE_QUERY_TIMEOUT_SECONDS` | `300` |
| `LAKEHOUSE_STORAGE_MAX_ENTRIES` | `5000` |
| `LAKEHOUSE_STORAGE_MAX_DEPTH` | `6` |

Frontend: `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`). See `frontend/.env.example`.

### Spark installation (bundled vs local)

By default the backend runs the Spark distribution **bundled with the PySpark
wheel** in `backend/.venv` — there is nothing to install and no global
`SPARK_HOME`/`PATH` entry is required. Open **Spark Settings** in the UI to:

- see the active Spark version, its Scala build and whether Spark is warm;
- **Browse…** for a local Spark folder (a native folder picker opens on the
  backend machine) or type a path, then **Use this Spark**;
- **Download & install** a matching Spark release in the background;
- revert to the bundled distribution with **Use bundled**.

A selected Spark home is validated server-side and must match the PySpark
client (`4.1.x`, Scala 2.13) or it is rejected with a reason — for example the
common `spark-3.5.6-bin-hadoop3` download is **Scala 2.12** and cannot load the
Delta 4.3.1 / Iceberg 1.12 connectors. The choice is stored in
`<repo>/.runtime_settings.json` (takes precedence over `LAKEHOUSE_SPARK_HOME`)
and the Spark session is restarted when it changes.

### Offline / air-gapped use

The first session needs Maven Central access. After one successful startup, the resolved jars are cached in `%USERPROFILE%\.ivy2\jars` (Windows) or `~/.ivy2/jars` (Unix). For an offline machine, copy the Delta and Iceberg jars (including Delta's transitive jars) to a local folder, then set:

```dotenv
LAKEHOUSE_SPARK_JARS=C:/jars/delta-spark_2.13-4.3.1.jar,C:/jars/delta-storage-4.3.1.jar,C:/jars/iceberg-spark-runtime-4.1_2.13-1.12.0.jar,C:/jars/spark-avro_2.13-4.1.4.jar
LAKEHOUSE_DELTA_PACKAGE=
LAKEHOUSE_ICEBERG_PACKAGE=
LAKEHOUSE_AVRO_PACKAGE=
```

Restart the backend after changing Spark configuration; sessions are created once per process.

## Security notes

- **No authentication.** The API executes arbitrary SQL, PySpark, Java, Scala, and kernel code, and can read and write files the backend process can access. It binds to `127.0.0.1` and is intended for a single trusted workstation.
- **Plain-text passwords** in `databases.cfg` and `data_warehouse/.connections.json` (see [Database connections](#database-connections)).
- Notebook files never store database passwords: `read_database` reads them from the backend configuration.

## Architecture notes

- **One session per process.** `SparkManager` lazily builds a single local session and all SQL runs under a re-entrant execution lock, preventing catalog/temp-view races between requests.
- **Notebook namespaces.** Each notebook keeps its own PySpark variables while the backend runs; **Reset kernel** clears them.
- **Separate JVM for Java/Scala programs.** The editors and `execute-jvm` run each program in its own `spark-submit` JVM with an in-memory catalog. This avoids the Derby metastore lock.
- **Jupyter kernels.** Non-Python notebooks use `jupyter_client`. One kernel process is kept per notebook and language; it is stopped by **Reset kernel** or when the backend exits.
- **Timeouts that actually cancel work.** Each statement runs in a worker thread under a Spark job group (`interruptOnCancel=True`). On timeout the job group is cancelled, not just abandoned.
- **Bounded results.** SELECT-like statements are capped at `max_rows + 1`; `truncated` is returned with the exact `max_rows` used. Values (Decimal, dates, binary, NaN/Infinity) are converted to strict JSON.
- **Path-safe storage inspector and workspace.** Every requested path is resolved and checked against the warehouse root or the open workspace folder; symlinks are skipped and scans are capped by depth and entry count.

## Testing and builds

```powershell
# Backend unit tests (no Spark session required for most tests)
cd backend
pip install -r requirements-dev.txt
pytest -q

# Frontend typecheck + production build (run in both UI folders)
cd frontend
npm run typecheck
npm run build
```

## Windows setup

Spark on Windows uses Hadoop's native file APIs. Without `winutils.exe` and `hadoop.dll`, table writes can fail with `UnsatisfiedLinkError` or `NativeIO` exceptions.

1. Obtain a Hadoop `bin` directory (for example `hadoop-3.3.5/bin`) containing `winutils.exe` and `hadoop.dll`.
2. Put it somewhere stable, e.g. `C:\hadoop`.
3. Set user environment variables:

```powershell
setx HADOOP_HOME "C:\hadoop"
setx PATH "$env:PATH;C:\hadoop\bin"
```

4. Open a new terminal and verify `winutils.exe` is on PATH. Ensure `JAVA_HOME` points to a **JDK 17+**.

PowerShell may block `.ps1` scripts or the `npm.ps1` shim. The provided scripts call `npm.cmd` and can be run with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Could not start Apache Spark` | Check Java 17+, `JAVA_HOME`, internet/proxy access to Maven Central, and the `spark.jars.packages` coordinates. |
| `UnsatisfiedLinkError`, `winutils`, `NativeIO` on Windows | Set `HADOOP_HOME` and put `winutils.exe`/`hadoop.dll` in `%HADOOP_HOME%\bin`; restart the backend. |
| First query hangs 30–90s | Normal: Spark JVM startup + Ivy jar resolution. Watch backend logs. |
| Java/Scala program takes 15–40 s | Normal: each run compiles and starts a new JVM (`spark-submit`). |
| `ClassNotFoundException` for Delta/Iceberg | Versions must match the Spark minor version. Keep Delta 4.3.x + Iceberg 4.1 runtime with Spark 4.1.x. |
| Local Spark rejected in Spark Settings | The folder must be Spark **4.1.x** built for **Scala 2.13** to match the PySpark client and connectors; 3.5.x / Scala 2.12 installs are incompatible. |
| Notebook dropdown has no Java or Scala entry | Install the kernel (see [Java and Scala notebook kernels](#java-and-scala-notebook-kernels)), then reload the page. |
| Notebook cell says “Kernel … is not installed” | The notebook was saved with a kernel that is missing here. Install it, or change the dropdown to Python. |
| Java kernel does not start | Check `java -version` (JDK 17+ on PATH) and the kernel's `kernel.json` path. The first start can take a minute. |
| Port already in use | Change the Uvicorn port and set `VITE_API_BASE_URL`; add the UI origin to `LAKEHOUSE_CORS_ORIGINS` if it is not one of the default origins. |
| UI shows “Backend offline” | Backend not running or CORS/origin mismatch. Check `http://127.0.0.1:8000/api/health`. |
| Changed Spark config but nothing happens | Stop/restart the backend; `SparkSession` is created once per process. |
| `Another instance of Derby may have already booted` | Only one JVM may open the embedded metastore. Stop the backend before running `seed_demo.py` or other Spark scripts. |
| Delta table exists on disk but `TABLE_OR_VIEW_NOT_FOUND` | The table was created by an older in-memory-catalog session. Recreate it (or re-run `seed_demo.py`) so the metastore records it. |
| Java/Scala program cannot see a table | Those runs use an in-memory catalog. Read the table by path, or query it from the SQL/PySpark editor. |
| Reset the lakehouse | Stop the backend, then delete the contents of `data_warehouse/` and `.spark_metastore/` (keep the folders). This also removes UI-saved connections in `data_warehouse/.connections.json`. |
