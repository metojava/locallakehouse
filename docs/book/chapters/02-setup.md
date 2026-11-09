# Chapter 2 — Setup & First Query

## Prerequisites

  Python 3.10 or newer
  Java 17 or newer with `JAVA_HOME` set
  Node.js 20 or newer
  Windows users: Hadoop `winutils.exe` on PATH (see README)

## Launch the backend

Open PowerShell in the repository root and run:

```powershell
powershell  ExecutionPolicy Bypass  File .\scripts\start backend.ps1
```

The first run creates a Python virtual environment and downloads Delta/Iceberg jars from Maven Central. This can take 30–90 seconds.

## Launch the frontend

In a second terminal:

```powershell
powershell  ExecutionPolicy Bypass  File .\scripts\start frontend.ps1
```

## Your first query

Open http://127.0.0.1:5173, paste this into the SQL editor, and press `Ctrl+Enter` (or `Cmd+Enter` on macOS):

```sql
SELECT
  current_catalog()   AS active_catalog,
  current_database()  AS active_database,
  current_timestamp() AS now;
```

You should see one row showing the active catalog (`spark_catalog`), the active database (`default`), and the current timestamp.

## Seed demo data

Stop the backend, then run:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python seed_demo.py
```

This creates:

  `demo.customers` — a Delta table in `spark_catalog`
  `local_iceberg.demo.sales` — an Iceberg table

> **Remember:** The embedded Derby metastore allows only one JVM at a time. Stop the backend before running `seed_demo.py` or any other Spark script.

## Verify the tables

Restart the backend and run:

```sql
SELECT * FROM demo.customers LIMIT 5;
SELECT * FROM local_iceberg.demo.sales LIMIT 5;
```

   

[← Introduction](01 introduction.md) · [Next: Spark SQL Fundamentals →](03 spark sql.md)
