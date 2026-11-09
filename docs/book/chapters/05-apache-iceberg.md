# Chapter 5 — Apache Iceberg in Practice

Apache Iceberg is an open table format designed for huge analytic tables. It separates physical storage from logical tables, supports hidden partitioning, and allows safe schema evolution.

## Create an Iceberg table with partitioning

```sql
CREATE TABLE IF NOT EXISTS local_iceberg.demo.web_events (
  event_id   BIGINT,
  user_id    BIGINT,
  event_type STRING,
  page       STRING,
  event_time TIMESTAMP
) USING iceberg
PARTITIONED BY (days(event_time));

INSERT INTO local_iceberg.demo.web_events VALUES
  (1, 1001, 'click', '/home',    TIMESTAMP '2026-01-15 08:30:00'),
  (2, 1002, 'view',  '/pricing', TIMESTAMP '2026-01-15 09:00:00'),
  (3, 1001, 'click', '/pricing', TIMESTAMP '2026-01-16 10:15:00'),
  (4, 1003, 'view',  '/docs',    TIMESTAMP '2026-01-16 11:00:00');

SELECT * FROM local_iceberg.demo.web_events ORDER BY event_time;
```

## Hidden partitioning

The partition column `days(event_time)` is computed automatically. Queries that filter on `event_time` benefit from partition pruning without users knowing the partition layout.

```sql
-- This query reads only the relevant day partition
SELECT event_type, COUNT(*) AS events
FROM local_iceberg.demo.web_events
WHERE event_time >= TIMESTAMP '2026-01-16 00:00:00'
GROUP BY event_type;
```

## Snapshots and time travel

```sql
-- List snapshots
SELECT * FROM local_iceberg.demo.web_events.snapshots;

-- Query an earlier snapshot (replace the snapshot ID with one from the table above)
SELECT * FROM local_iceberg.demo.web_events
FOR SYSTEM_VERSION AS OF <snapshot_id>;
```

## Schema evolution

```sql
-- Add a column
ALTER TABLE local_iceberg.demo.web_events
ADD COLUMN referrer STRING;

-- Write data with the new column
INSERT INTO local_iceberg.demo.web_events
  (event_id, user_id, event_type, page, event_time, referrer)
VALUES
  (5, 1004, 'click', '/blog', TIMESTAMP '2026-01-17 12:00:00', 'google.com');

SELECT * FROM local_iceberg.demo.web_events ORDER BY event_time;
```

> **Remember:** Iceberg tables are stored under `data_warehouse/iceberg`. The Hadoop catalog keeps all metadata in the warehouse, so you only need the files to move or back up a database.

---

[← Delta Lake in Practice](04-delta-lake.md) · [Next: Importing Data →](06-data-import.md)
