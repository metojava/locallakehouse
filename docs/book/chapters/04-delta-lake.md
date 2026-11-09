# Chapter 4 — Delta Lake in Practice

Delta Lake brings ACID transactions, scalable metadata, and time travel to Apache Spark. Every change creates a new version stored in the `_delta_log` directory.

## Create a partitioned Delta table

```sql
CREATE TABLE IF NOT EXISTS demo.sales_delta (
  sale_id     BIGINT,
  customer_id BIGINT,
  amount      DOUBLE,
  country     STRING,
  sold_date   DATE
) USING delta
PARTITIONED BY (country);

INSERT INTO demo.sales_delta VALUES
  (1, 101, 99.99,  'US', DATE '2026-01-15'),
  (2, 102, 149.50, 'US', DATE '2026-01-16'),
  (3, 103, 29.99,  'DE', DATE '2026-01-17'),
  (4, 104, 199.00, 'FR', DATE '2026-01-18');

SELECT country, COUNT(*) AS sales, SUM(amount) AS revenue
FROM demo.sales_delta
GROUP BY country
ORDER BY revenue DESC;
```

## Updates and deletes

```sql
-- Update
UPDATE demo.sales_delta
SET amount = amount * 1.10
WHERE country = 'US';

-- Delete
DELETE FROM demo.sales_delta
WHERE amount < 50;

SELECT * FROM demo.sales_delta ORDER BY sale_id;
```

## Time travel with VERSION AS OF

```sql
-- See table history
DESCRIBE HISTORY demo.sales_delta;

-- Query version 0 (before updates/deletes)
SELECT * FROM demo.sales_delta VERSION AS OF 0;
```

## Merge (upsert)

```sql
CREATE OR REPLACE TEMP VIEW new_sales AS
SELECT * FROM VALUES
  (5, 105, 75.00,  'US', DATE '2026-01-20'),
  (2, 102, 159.50, 'US', DATE '2026-01-16')
AS t(sale_id, customer_id, amount, country, sold_date);

MERGE INTO demo.sales_delta AS target
USING new_sales AS source
ON target.sale_id = source.sale_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

SELECT * FROM demo.sales_delta ORDER BY sale_id;
```

> **Best practice:** Partition Delta tables on low-cardinality columns like `country` or `date`. Avoid partitioning on high-cardinality columns such as user IDs because it creates too many small files.

---

[← Spark SQL Fundamentals](03-spark-sql.md) · [Next: Apache Iceberg in Practice →](05-apache-iceberg.md)
