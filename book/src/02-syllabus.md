# The 20-Project Master Syllabus

Four parts. Each part builds a distinct production capability, and each chapter is a complete vertical slice: generator → PySpark → Java → tuning.

## Summary map

| Part | Projects | Domain capability | Difficulty |
|---|---|---|---|
| **I — Foundations & Batch ETL** | 1–5 | Deterministic, idempotent batch pipelines; window functions; dimensional modeling | ★★☆☆☆ |
| **II — Optimization, Joins & Data Quality** | 6–10 | Shuffle economics, skew, file layout, semi-structured ingestion, data contracts | ★★★☆☆ |
| **III — Streaming & Real-Time** | 11–15 | Exactly-once streaming, watermarks, arbitrary state, stream joins, sink idempotency | ★★★★☆ |
| **IV — Lakehouse & ML at Scale** | 16–20 | Iceberg/Delta ACID tables, point-in-time features, MLlib pipelines, production hardening | ★★★★★ |

**Project dependency graph.** Projects 1–10 are sequential: each introduces a helper that later chapters import (`lib/spark_session.py` in 1, `lib/quality.py` in 10). Projects 11–20 are independent of each other but assume Part I's data generators and Part II's performance harness.

---

## Part I — Foundations & Batch ETL

### Project 1 · Retail Order ETL: CSV → Parquet Medallion Pipeline

**Business scenario.** A mid-market retailer receives nightly order extracts from four store systems. Files are late, duplicated, malformed, and inconsistently cased. Finance needs a trustworthy, partitioned Parquet table by 06:00 local time.

**Spark mechanics.** Explicit `StructType` schemas vs inference; `permissive` mode and `_corrupt_record`; deduplication with `row_number()` over a business key plus ingestion timestamp; `partitionBy` and the small-file consequences; AQE partition coalescing; reading `explain(True)`.

**You will ship.** `generate_data.py` (Faker-based, 250k orders including seeded defects), `retail_etl.py` with bronze/silver/gold stages and a rejection table, and a Java `RetailEtlJob` producing byte-identical partitioned output.

**Difficulty** ★★☆☆☆ · **Runtime** ~90 s

### Project 2 · Customer 360: Identity Resolution & Deduplication at Scale

**Business scenario.** The same human exists as `J. Smith`, `John Smith`, and `JONATHAN SMITH` across CRM, web, and POS with different emails and phone formats. Marketing needs one golden record per person without merging distinct people.

**Spark mechanics.** Blocking keys to avoid O(n²) self-joins; `broadcast()` semantics and the 8 GB broadcast limit; `levenshtein`, `soundex`, normalization via `regexp_replace`; determinism and `monotonically_increasing_id` pitfalls; surviving-record selection with `row_number()`; graph-free union-find approximation via two-pass connected components.

**You will ship.** A generator with deliberately injected duplicates and near-misses, a scored match pipeline with thresholds, a golden-record builder, plus the Java equivalent using `Dataset<Row>` joins and `Column` predicates.

**Difficulty** ★★★☆☆ · **Runtime** ~2 min

### Project 3 · Clickstream Sessionization & Conversion Funnel

**Business scenario.** An e-commerce site emits raw click events. Analytics wants 30-minute-inactivity sessions and a five-step funnel (land → product → cart → checkout → purchase) with drop-off attribution per channel.

**Spark mechanics.** Event time vs processing time; gaps-and-islands via `lag` plus a cumulative `sum` over `Window.partitionBy(user).orderBy(ts)`; window frame boundaries (`rowsBetween` vs `rangeBetween`); funnel construction with `max(when(...))` pivots; `first`/`last` with `ignorenulls`.

**You will ship.** A generator producing ~1M events with realistic bot traffic and channel attribution, a sessionizer with funnel metrics, and the Java job using `WindowSpec` and `functions.when`.

**Difficulty** ★★★☆☆ · **Runtime** ~2 min

### Project 4 · SCD Type 2 Dimension Loader (Idempotent Upsert on Parquet)

**Business scenario.** The product dimension must retain full history — price and category changes need `valid_from` / `valid_to` / `is_current`. The job reruns daily, sometimes twice, and must never create duplicate versions.

**Spark mechanics.** Change detection with a `full outer join` plus a `hash` of tracked columns; closing open versions; `unionByName` for inserts; **idempotency without MERGE** using a deterministic `version_id` and `dropDuplicates`; partition overwrite semantics (`spark.sql.sources.partitionOverwriteMode=dynamic`); why this is exactly the problem Delta/Iceberg `MERGE` solves — foreshadowing Project 16.

**You will ship.** A generator with three daily snapshots containing inserts, updates, and no-ops; the loader; a verification script that replays a snapshot and asserts row-count invariance.

**Difficulty** ★★★☆☆ · **Runtime** ~60 s

### Project 5 · Log Mining & Anomaly Detection with Skew Handling

**Business scenario.** 40 GB/day of nginx-style logs from 12 services. SRE needs per-service error-rate anomalies and top-N failing endpoints — but one service emits 60% of all rows and destroys the shuffle.

**Spark mechanics.** `regexp_extract` over native functions vs Python UDF vs pandas UDF (measured, not asserted); hot-key salting (`concat(key, '_', floor(rand() * N))`) with two-phase aggregation; `approx_count_distinct` (HyperLogLog) vs `countDistinct`; anomaly flagging with `stddev_pop` z-scores; `spark.sql.adaptive.skewJoin` limits.

**You will ship.** A log generator with an intentionally skewed service, a native-function parser, a benchmark harness comparing three parsing strategies, and the salted aggregation.

**Difficulty** ★★★☆☆ · **Runtime** ~90 s

---

## Part II — Optimization, Joins & Data Quality

### Project 6 · Star-Schema Join Optimization Laboratory

**Business scenario.** A BI query joins a 500M-row fact table to five dimensions. Currently it spills to disk nightly. You must cut runtime by at least 60% without more hardware.

**Spark mechanics.** Broadcast hash join vs sort-merge join vs shuffled hash join — how the planner chooses, and how `/*+ BROADCAST(d) */` overrides it; `spark.sql.autoBroadcastJoinThreshold`; salting a skewed dimension key; AQE skew-join splitting; reading stage metrics; the real cost of `count()` on a cached plan.

**You will ship.** A synthetic star schema with a deliberately skewed dimension, five query variants, and a benchmarking harness that reports shuffle bytes read/written per strategy.

**Difficulty** ★★★★☆ · **Runtime** ~3 min

### Project 7 · File Layout Engineering: Partitioning, Bucketing & Compaction

**Business scenario.** A table written hourly has accumulated 1.2M files averaging 40 KB. Every query pays a metadata tax. You own the compaction service.

**Spark mechanics.** Target file size math (`spark.sql.files.maxPartitionBytes`, `openCostInBytes`); `repartition(n, col)` vs `coalesce(n)` vs `repartitionByRange`; `bucketBy` + `sortBy` and why bucket pruning only works with `saveAsTable`; hidden partitioning vs directory partitioning; a compaction job safe to run concurrently with readers; retention reasoning.

**You will ship.** A generator that manufactures a pathological small-file table, a compaction job with dry-run reporting, and a query benchmark before and after.

**Difficulty** ★★★★☆ · **Runtime** ~2 min

### Project 8 · Semi-Structured Ingestion: Nested JSON, XML & Schema Evolution

**Business scenario.** Three upstream teams ship event payloads: deeply nested JSON, XML from a legacy ERP, and a JSON feed that gains fields without warning. The warehouse must ingest all three without breaking.

**Spark mechanics.** `from_json` with DDL schema strings vs `StructType`; `explode` vs `explode_outer` vs `posexplode`; schema evolution strategies (rescue column, `mergeSchema`, explicit contract versioning); XML via `spark-xml` with `rowTag` and attribute mapping; flattening arrays-of-structs into relational form; `to_json` / `get_json_object` performance profile.

**You will ship.** A multi-format generator, a flattening pipeline with a rescue column that captures unknown fields as `MapType`, and the Java job using `functions.from_json` with a `DataType` tree.

**Difficulty** ★★★★☆ · **Runtime** ~2 min

### Project 9 · Query Acceleration Lab: Caching, Plans & Benchmarks

**Business scenario.** A dashboard issues the same seven aggregations against a 200M-row table. Each refresh takes 40 minutes; the business wants under five.

**Spark mechanics.** `persist` storage levels and their real memory/disk trade-offs; when caching *hurts* (wide rows, lost column pruning); `CACHE TABLE` vs `persist`; column pruning and predicate pushdown verified through `explain`; `spark.sql.inMemoryColumnarStorage.batchSize` and `compression`; join reordering with `spark.sql.cbo.enabled` and statistics via `ANALYZE TABLE`.

**You will ship.** A repeatable benchmark harness (warm-up, N iterations, median plus p95), a plan-comparison reporter, and a decision matrix for cache vs pre-aggregate vs materialize.

**Difficulty** ★★★★☆ · **Runtime** ~4 min

### Project 10 · Declarative Data Quality Framework with Quarantine

**Business scenario.** Every pipeline re-implements its own null checks. Auditors want a single rule catalog, per-run metrics, and bad rows quarantined rather than dropped.

**Spark mechanics.** Rule specification as data (YAML/JSON) compiled to `Column` predicates; `when(...).otherwise(...)` to split good and bad in one pass instead of two scans; aggregate rule metrics with a single `agg` (`sum(when(...))`); quarantine writes with reason codes; fail-fast vs warn-and-continue policy; integrating checks into the job DAG so downstream stages never see dirty data.

**You will ship.** `lib/quality.py` (reused by later chapters), a rules YAML with 24 production-grade checks, a runner that emits a metrics table plus a quarantine dataset, and a Java port of the core predicate compiler.

**Difficulty** ★★★★☆ · **Runtime** ~90 s

---

## Part III — Streaming & Real-Time

### Project 11 · Kafka → Structured Streaming Bronze Ingestion (Exactly-Once)

**Business scenario.** A payments platform publishes ~20k events/s to Kafka. The lakehouse needs a bronze table that never loses or duplicates a record, survives restarts, and can be backfilled on demand.

**Spark mechanics.** Sources, sinks and the exactly-once contract; checkpoint anatomy (`offsets/`, `commits/`, `metadata`); `trigger(processingTime)` vs `availableNow` vs `once`; `maxOffsetsPerTrigger` and backpressure; `foreachBatch` for idempotent writes keyed by `batchId`; Kafka connector offset-commit semantics; schema enforcement at ingestion via a versioned contract.

**You will ship.** A docker-compose Kafka plus a Python producer replaying a generated event file, the streaming job writing partitioned Parquet with a `batch_id`, and a restart test that proves no duplication.

**Difficulty** ★★★★☆

### Project 12 · Watermarks, Late Data & Deduplication

**Business scenario.** Mobile clients buffer events offline for up to 50 minutes. The five-minute revenue dashboard must be correct despite late arrivals and client-side retries.

**Spark mechanics.** Watermark definition and its three consequences (state eviction, late-data drop, output finalization); `withWatermark` on the event-time column vs a derived column; `dropDuplicates` with and without a watermark; `dropDuplicatesWithinWatermark` semantics in 3.5; append vs update vs complete output modes and where each is legal; inspecting state via `StreamingQueryProgress.stateOperators`.

**You will ship.** A producer emitting 0–55 minute late events, a windowed aggregation with a 10-minute watermark, a dedup stage keyed by `event_id`, and an assertion suite proving late-but-in-watermark data is counted exactly once.

**Difficulty** ★★★★☆

### Project 13 · Stateful Fraud Detection with `applyInPandasWithState`

**Business scenario.** A card-not-present fraud model scores each user's transaction stream against their last 30 minutes of behaviour: velocity, amount deviation, distinct-merchant burst. Rules must not lose state across micro-batches.

**Spark mechanics.** Arbitrary stateful processing; the `GroupState` API (`exists`, `get`, `update`, `remove`, `setTimeoutDuration`); processing-time vs event-time timeouts; state schema design and unbounded-state risk; `flatMapGroupsWithState` (Java) vs `applyInPandasWithState` (Python) and Arrow serialization cost; output mode constraints; state-store growth and `spark.sql.streaming.stateStore.providerClass`.

**You will ship.** A transaction generator with injected fraud patterns, a stateful scorer emitting alerts, state-size instrumentation, and the Java `flatMapGroupsWithState` implementation with `Encoders`.

**Difficulty** ★★★★★

### Project 14 · Streaming Joins: Enrichment and Interval Correlation

**Business scenario.** Orders stream in and need (a) enrichment from a slowly changing product catalog and (b) correlation with shipment events that may arrive before or after the order.

**Spark mechanics.** Stream-static joins and why the static side must be broadcastable (and refreshed); stream-stream **interval joins** with `eventTimeRangeStartExpression` / `End`; watermark requirements on both sides; deduplication *before* the join to prevent fan-out; join output-mode restrictions; state size = watermark bound × event rate, with the formula and how to size it.

**You will ship.** Two producers (orders, shipments) with controlled arrival skew, an enrichment join with catalog refresh, an interval join producing order-to-shipment latency, and a state-size budget worksheet.

**Difficulty** ★★★★★

### Project 15 · Real-Time Sink, Idempotency & Streaming Observability

**Business scenario.** Aggregated metrics must land in PostgreSQL for a live dashboard, be safe under retries, and page an on-call engineer when throughput collapses.

**Spark mechanics.** `foreachBatch` with JDBC upserts (`INSERT ... ON CONFLICT`); staging-table-then-swap for atomicity; `batchId`-keyed idempotency; partition-level parallelism (`numPartitions`, `repartition`); `StreamingQueryListener` (`onQueryStarted`, `onQueryProgress`, `onQueryTerminated`) for metrics; `lastProgress` parsing (input/output rows per second, `durationMs` breakdown); graceful shutdown and listener registration; checkpoint location per query vs per sink.

**You will ship.** A docker-compose Postgres, an idempotent upsert sink, a listener that emits JSON metrics and flags zero-progress windows, and a controlled-failure drill proving no partial batches.

**Difficulty** ★★★★☆

---

## Part IV — Lakehouse & Machine Learning at Scale

### Project 16 · Apache Iceberg Lakehouse: MERGE, Time Travel & Maintenance

**Business scenario.** A lakehouse must support row-level upserts and deletes, ACID reads during writes, schema evolution, and point-in-time audit queries — on object storage.

**Spark mechanics.** Catalog configuration (Hadoop catalog vs REST vs Nessie) and warehouse layout; `MERGE INTO` with `WHEN MATCHED` / `NOT MATCHED BY SOURCE`; snapshot isolation and `VERSION AS OF` / `TIMESTAMP AS OF`; hidden partitioning (`days(ts)`, `bucket(16, id)`) and partition evolution; `rewrite_data_files` and `expire_snapshots`; manifest and file-count effects on planning time; equality vs positional deletes.

**You will ship.** MinIO plus Iceberg in docker-compose (or a pure-local Hadoop catalog), a full SCD2-via-MERGE implementation that replaces Project 4's hand-rolled version, a time-travel audit query, and a maintenance job with retention policy.

**Difficulty** ★★★★★

### Project 17 · Delta Lake Medallion Architecture (Bronze/Silver/Gold)

**Business scenario.** You are consolidating 14 ad-hoc pipelines into a governed medallion architecture with schema enforcement, constraints, and change data feed for downstream consumers.

**Spark mechanics.** Delta transaction log anatomy; `MERGE` vs `INSERT` plus `replaceWhere`; `CHECK` constraints and `NOT NULL`; `mergeSchema` vs `overwriteSchema`; `OPTIMIZE` plus `ZORDER BY` (data-skipping effectiveness measured via `numFiles` / `numOutputBytes`); `VACUUM` retention and the reader-safety contract; Change Data Feed for incremental downstream jobs; `DESCRIBE HISTORY`.

**You will ship.** A three-layer pipeline over the retail dataset from Project 1, DDL with constraints, a Z-order benchmark, a CDF consumer, and a cost/retention policy document.

**Difficulty** ★★★★★

### Project 18 · Point-in-Time Correct Feature Engineering

**Business scenario.** A churn model trained on features that leaked future information scored 0.94 offline and 0.61 in production. You must rebuild the feature layer with strict as-of semantics.

**Spark mechanics.** Label and feature time boundaries; `Window.rangeBetween` on epoch seconds for trailing windows; as-of joins (`join` on `feature_ts <= label_ts` then `row_number()` descending) vs interval joins; feature versioning and backfill; train/serve skew and how `Pipeline` plus saved transformers prevent it; feature freshness partitioning; cardinality control with `approx_count_distinct` and hashing.

**You will ship.** An event generator spanning 18 months, a feature builder producing 30 point-in-time-correct features, a leakage test that *fails* on a deliberately leaky variant, and a feature-store-style Parquet layout partitioned by `feature_date`.

**Difficulty** ★★★★★

### Project 19 · MLlib Churn Prediction End-to-End

**Business scenario.** A subscription business needs a weekly churn probability per account, a threshold tuned to retention-budget economics, and explainable drivers for the CRM team.

**Spark mechanics.** `StringIndexer` / `OneHotEncoder` / `VectorAssembler` inside a `Pipeline`; `StandardScaler` and why fitting on the full dataset is leakage; `GBTClassifier` vs `LogisticRegression` vs `RandomForestClassifier`; `CrossValidator` plus `ParamGridBuilder` with `parallelism`; `BinaryClassificationEvaluator` (AUC) vs `MulticlassClassificationMetrics`; class imbalance via `weightCol`; model persistence (`save`/`load`) and schema compatibility; batch scoring with `model.transform` and feature-importance extraction.

**You will ship.** A training job, a saved pipeline model, a scoring job writing predictions to the lakehouse, an evaluation report with PR-curve points, and a Java inference job loading the same model.

**Difficulty** ★★★★★

### Project 20 · Capstone: Real-Time Recommendation & Production Hardening

**Business scenario.** Ship a streaming recommender: ALS trained nightly on implicit feedback, served in-stream with sub-second latency, with cold-start fallback, CI, and SLOs.

**Spark mechanics.** `ALS` with implicit preference (`implicitPrefs = true`), `alpha`, regularization, and ranking cut-offs; `recommendForUserSubset` vs `recommendForAllUsers` memory profile; embedding export (`.userFactors` / `.itemFactors`) and serving via broadcast lookup or a `mapInPandas` scorer; streaming inference in `foreachBatch` with model hot-reload; cold-start handling via popularity fallback; NDCG and recall@k offline evaluation; deployment packaging (`--py-files` zip), config via `--conf` and environment, structured JSON logging, and a CI pipeline that builds both language stacks and runs the regression suite.

**You will ship.** A complete, deployable project: trainer, exporter, streaming scorer, offline evaluator, `Dockerfile`, `docker-compose`, CI workflow, and a runbook with SLOs and alert thresholds.

**Difficulty** ★★★★★

---

## What you will be able to say after Project 20

- "I can read a physical plan and tell you where the shuffle, skew, and spill are."
- "I can prove a pipeline is idempotent under retries — and demonstrate it with a test."
- "I know when a broadcast join will OOM the driver before it happens."
- "I can size streaming state from event rate and watermark, not guesswork."
- "I can implement the same business logic in PySpark and Java and explain every API difference."
- "I can put a Spark job behind CI, SLOs, and a runbook."
