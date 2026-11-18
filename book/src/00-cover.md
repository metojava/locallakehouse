# Mastering Apache Spark

## 20 Real-World Data Engineering Projects in Python & Java

**Apache Spark 3.5.x · Java 17 · Python 3.10+ · First Edition**

---

### A build-it book for production data engineering

Most Spark material teaches you `df.groupBy().count()` and stops. Production data engineering starts *after* that — where schemas drift, keys skew, files multiply into the millions, streams arrive late, upserts must be idempotent, and the same job has to run identically from a laptop and a 200-node cluster.

This book is a **build-it book**. Twenty self-contained projects, each one a slice of a real production system. Every chapter ships with:

- a **synthetic data generator** so you never need a cloud account or a proprietary dataset,
- a **complete, runnable PySpark module**,
- a **complete, runnable Java (Spark Java API) module** with a full `pom.xml`,
- an **internals deep-dive** explaining *why* the code behaves the way it does at the Catalyst / Tungsten / scheduler level,
- and **tuning guidance** grounded in measurable effects, not folklore.

Nothing is stubbed. No `// TODO`, no "left as an exercise", no `...`. If a file is listed, it is complete and it compiles.

---

### Who this book is for

| You are… | You get… |
|---|---|
| A data engineer moving from pandas/SQL to distributed compute | A mental model of partitions, shuffles and the Catalyst optimizer that survives contact with production |
| A Python developer forced to ship Java/Scala Spark jobs | A line-by-line Python ↔ Java API translation in every chapter |
| A Java engineer inheriting a Spark platform | Idiomatic `Dataset<T>` code, `Encoders`, `TypedColumn`, and why `Row`-based code is often the wrong default |
| A senior engineer preparing for platform/architecture work | Lakehouse table formats, stateful streaming, point-in-time feature correctness, and observability patterns |

### The dual-language contract

Every project is implemented **twice** — PySpark and Java — against the *same* input data and producing the *same* output. This is deliberate. It forces you to confront the places where the two APIs genuinely diverge:

- Python `udf` vs Java `UDF1..UDF22` / `MapFunction`, and JVM-versus-Python serialization cost
- Lazy `Column` expressions vs typed `Column` / `TypedColumn` with `Encoders`
- `foreachBatch` closures capturing Python state vs Java `VoidFunction2<Dataset<Row>, Long>`
- Checkpoint and state-store shapes in `applyInPandasWithState` vs `flatMapGroupsWithState`
- Build and runtime packaging: `--py-files` vs shaded jars vs `provided` scope

### Book conventions

| Convention | Meaning |
|---|---|
| `$BOOK_HOME` | Root of your working directory. All paths are relative to it. |
| `file:///` URIs | Used for all local I/O so behaviour matches HDFS / S3 semantics. |
| Dataset sizes | Every generator produces data sized for a **laptop**: 50k–5M rows, 1–3 min runtimes in `local[*]`. |
| `local[*]` | Default master. Every chapter notes the cluster-submit delta. |
| Version pins | Spark **3.5.3**, Scala **2.12**, Java **17**, Python **3.10/3.11**. Patch differences within 3.5.x are drop-in. |
| Paths on Windows | PowerShell uses backslashes and `` ` `` for line continuation; `bash` examples use `/` and `\`. |
| Logging | All jobs use `logging` (Python) / SLF4J (Java) — never bare `print` / `System.out`. |

### Repository layout you will build

```text
spark-mastery/
├── data/                                  # generated datasets (git-ignored)
├── lib/
│   ├── spark_session.py                   # shared session factory (Project 1)
│   └── quality.py                         # rules engine (Project 10)
├── projects/
│   ├── p01_retail_etl/
│   │   ├── generate_data.py
│   │   ├── retail_etl.py
│   │   └── java/
│   │       ├── pom.xml
│   │       └── src/main/java/com/sparkmastery/p01/RetailEtlJob.java
│   ├── p02_customer_360/
│   └── ...
└── README.md
```

### How each chapter is structured

1. **Business Problem & Architecture** — the scenario, the pipeline data flow, and the engineering argument for Spark.
2. **Sample Data Generator** — standalone Python, `faker` + `random` + `csv`/`json`, no external downloads.
3. **Spark Internals & Mechanics** — the optimizer / scheduler / state-store reality behind the code.
4. **Complete PySpark Implementation** — typed, logged, modular, plus the exact `spark-submit`.
5. **Complete Java Implementation** — full `pom.xml`, full class, plus `mvn clean package` and `spark-submit`.
6. **Code Walkthrough & Tuning Tips** — key logic, Python vs Java nuance, three production optimizations.

**Pacing.** Roughly 60–120 minutes per chapter if you run everything; about 25 minutes if you read only. Parts I and II are sequential. Part III and Part IV chapters are independent but assume the shared `lib/` helpers introduced earlier.

> **Verification gate.** Before starting Project 1, complete the Environment Setup chapter and get both smoke tests — Python and Java — to print `SMOKE TEST PASSED`. Every chapter in this book then runs unmodified.
