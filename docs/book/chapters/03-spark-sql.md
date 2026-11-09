# Chapter 3 — Spark SQL Fundamentals

Spark SQL lets you query data with familiar SQL syntax. The workbench exposes two catalogs: `spark_catalog` (Delta-backed) and `local_iceberg` (Iceberg-backed).

## Catalogs and namespaces

```sql
-- Show current catalog and database
SELECT current_catalog(), current_database();

-- Switch catalog
USE local_iceberg;

-- Switch namespace (database)
USE demo;

-- List namespaces
SHOW NAMESPACES IN spark_catalog;
SHOW NAMESPACES IN local_iceberg;
```

## Creating tables

### Delta table

```sql
CREATE TABLE IF NOT EXISTS demo.orders (
  order_id    BIGINT,
  customer_id BIGINT,
  total       DOUBLE,
  ordered_at  TIMESTAMP
) USING delta;

INSERT INTO demo.orders VALUES
  (1001, 1, 249.99, current_timestamp()),
  (1002, 2, 1899.00, current_timestamp());

SELECT * FROM demo.orders;
```

### Iceberg table

```sql
CREATE TABLE IF NOT EXISTS local_iceberg.demo.events (
  event_id   BIGINT,
  event_type STRING,
  payload    STRING,
  event_ts   TIMESTAMP
) USING iceberg;

INSERT INTO local_iceberg.demo.events VALUES
  (1, 'page_view', '{"page":"/pricing"}', current_timestamp()),
  (2, 'signup', '{"plan":"pro"}', current_timestamp());

SELECT * FROM local_iceberg.demo.events;
```

## Common transformations

```sql
-- Aggregation
SELECT country, COUNT(*) AS customers
FROM demo.customers
GROUP BY country
ORDER BY customers DESC;

-- Join
SELECT c.first_name, c.country, s.amount
FROM demo.customers c
JOIN local_iceberg.demo.sales s
  ON c.id = s.customer_id
LIMIT 100;

-- Window function
SELECT
  customer_id,
  amount,
  SUM(amount) OVER (PARTITION BY customer_id ORDER BY sold_at) AS running_total
FROM local_iceberg.demo.sales
LIMIT 50;
```

## Multiple statements

Paste several statements separated by semicolons. The workbench runs them in order and returns the result of the last one.

```sql
CREATE TABLE IF NOT EXISTS demo.metrics AS SELECT 1 AS id, 10.5 AS value;
INSERT INTO demo.metrics VALUES (2, 20.0), (3, 30.0);
SELECT * FROM demo.metrics ORDER BY id;
```

> **Exercise:** Create a Delta table that stores daily website visits by country, then write a query that ranks countries by total visits.

---

[← Setup & First Query](02-setup.md) · [Next: Delta Lake in Practice →](04-delta-lake.md)
