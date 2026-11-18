# Getting Started for Startups

A fast, zero-cloud lakehouse for small teams.

---

Startups need to move fast without big infrastructure bills. The Open Lakehouse Workbench gives your team a production-like Spark, Delta Lake, and Iceberg environment on a single laptop or small server.

[Read the full book](book/index.md) · [HTML version](getting-started.html)

---

## Why this matters for startups

- **No cloud bill** — everything runs locally.
- **Open formats** — avoid vendor lock-in from day one.
- **Same tools as the big platforms** — Spark SQL, PySpark, Delta, Iceberg.
- **Easy migration path** — skills and code transfer directly to Databricks, AWS, or Azure later.

## Five-minute startup

### 1. Install prerequisites

- Python 3.10+
- Java 17+
- Node.js 20+

### 2. Start the backend

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

### 3. Start the frontend

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

### 4. Open the workbench

Navigate to http://127.0.0.1:5173 and run:

```sql
SELECT current_timestamp() AS first_query;
```

## Typical startup workflows

### Load customer data from your app database

Create `databases.cfg` in the repository root:

```ini
[postgresql.production_read_replica]
name=Production Read Replica
host=db.mystartup.com
port=5432
database=app_db
username=analytics
password=your_password
```

Open the **Databases** page, browse tables, and import them as Delta or Iceberg tables.

### Build your first metrics model

```sql
CREATE TABLE IF NOT EXISTS demo.daily_revenue AS
SELECT
  DATE(created_at) AS day,
  COUNT(*)         AS orders,
  SUM(amount)      AS revenue
FROM demo.orders
GROUP BY DATE(created_at);

SELECT * FROM demo.daily_revenue ORDER BY day DESC LIMIT 30;
```

### Share results

Export query results from the UI, or query them via the REST API:

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/execute-sql `
  -H "Content-Type: application/json" `
  -d '{"sql":"SELECT * FROM demo.daily_revenue ORDER BY day DESC LIMIT 30"}'
```

## When to move to the cloud

The workbench is perfect for:

- Local development and debugging
- Small datasets that fit on one machine
- Learning and proofs of concept

When you outgrow it, your SQL and PySpark code run almost unchanged on Databricks, EMR, Dataproc, or Azure Synapse.

> **Pro tip:** Keep `data_warehouse` and `.spark_metastore` in version control exclusions. They are local data, not source code.

## Next steps

1. Read the [full online book](book/index.md).
2. Run the `seed_demo.py` script to create sample tables.
3. Connect your own database with `databases.cfg`.
4. Build your first PySpark transformation.

---

*Open Lakehouse Workbench · Getting Started for Startups*
