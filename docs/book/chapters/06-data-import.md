# Chapter 6 — Importing Data

The workbench can import local files and remote database tables. You choose the target format: **Delta**, **Iceberg**, or a plain **Spark** table.

## Import local files

Click **Import file** in the SQL editor. Supported formats:

- CSV
- JSON (line-delimited or multi-line array)
- Parquet
- TXT (treated as CSV)
- ORC
- Avro

### Example: import JSON as Iceberg

```sql
-- After importing data/accounts.json as Iceberg with table name "accounts"
SELECT * FROM local_iceberg.default.accounts LIMIT 10;

SELECT state, COUNT(*) AS customers
FROM local_iceberg.default.accounts
GROUP BY state
ORDER BY customers DESC
LIMIT 10;
```

### Example: import CSV as Delta

Use the UI or the API. A sample request:

```json
POST /api/import-file
{
  "path": "C:\\data\\customers.csv",
  "namespace": "default",
  "table_format": "delta",
  "source_format": "csv",
  "mode": "error",
  "has_header": true,
  "delimiter": ","
}
```

## Import from databases

There are two ways:

1. **databases.cfg** — create a config file in the repository root and browse tables on the **Databases** page.
2. **UI-managed connections** — add a connection in **Import → Database**.

### Sample databases.cfg

```ini
[postgresql.local_pg]
name=Local PostgreSQL
host=localhost
port=5432
database=sales_db
username=postgres
password=secret

[mysql.local_mysql]
name=Local MySQL
host=localhost
port=3306
database=ecommerce
username=root
password=secret
```

### Import a remote table via SQL

```sql
-- Import is done through the API; after importing the "orders" table
SELECT * FROM spark_catalog.default.orders LIMIT 10;
```

## Programmatic import with PySpark

```python
df = (
    spark.read.format("jdbc")
    .option("url", "jdbc:postgresql://localhost:5432/sales_db")
    .option("dbtable", "public.orders")
    .option("user", "postgres")
    .option("password", "secret")
    .option("driver", "org.postgresql.Driver")
    .load()
)

df.write.format("delta").mode("overwrite").saveAsTable("demo.orders_from_pg")
```

> **Tip:** For CSV and TXT files, always check the delimiter and header options. The importer tries to detect the format from the file extension, but you can override it.

---

[← Apache Iceberg in Practice](05-apache-iceberg.md) · [Next: PySpark Transformations →](07-pyspark-transformations.md)
