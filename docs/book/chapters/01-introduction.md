# Chapter 1 — Introduction

Modern data platforms are built on three ideas: a fast execution engine, a way to store tables reliably, and an open format that prevents vendor lock-in. This book teaches all three using the **Open Lakehouse Workbench**.

## What is the Open Lakehouse Workbench?

It is a fully local application that bundles:

- **Apache Spark 4.1** — the engine for SQL and Python data processing.
- **Delta Lake 4.3** — ACID transactions and time travel for the default catalog.
- **Apache Iceberg 1.12** — an open table format with snapshot isolation and hidden partitioning.
- **FastAPI + React** — a web UI with a SQL editor, PySpark editor, schema explorer, and database browser.

## Why these three technologies?

| Technology | Role |
|------------|------|
| Apache Spark | Distributed data processing engine. Runs SQL and Python transformations. |
| Delta Lake | ACID table format with scalable metadata handling. |
| Apache Iceberg | Open table format designed for cloud-scale analytics and engine interoperability. |

## Key concepts you will learn

1. How to write Spark SQL that works across Delta and Iceberg catalogs.
2. How to import CSV, JSON, Parquet, ORC, Avro, and database tables.
3. How to use PySpark for complex transformations.
4. How Delta Lake handles updates, deletes, and time travel.
5. How Iceberg manages snapshots, partitioning, and hidden evolution.
6. How to build an end-to-end analytics pipeline.

> **Tip:** Keep the workbench open while reading. Every code example in this book can be copied directly into the SQL editor or PySpark editor and executed locally.

---

[← Table of Contents](../index.md) · [Next: Setup & First Query →](02-setup.md)
