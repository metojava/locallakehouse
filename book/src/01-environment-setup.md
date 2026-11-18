# Environment Setup

The entire book runs on a single laptop. No Docker is required until Project 11 (Kafka) and Project 16 (Iceberg catalog), and even there a single-container setup is enough.

## 0. Version matrix (pin these)

| Component | Version | Notes |
|---|---|---|
| Apache Spark | **3.5.3** (any 3.5.x ≥ 3.5.3) | `-bin-hadoop3` distribution |
| Scala binary | **2.12** | Spark 3.5 default; all `_2.12` artifacts |
| Java | **17** (Temurin/Adoptium 17.0.x) | Spark 3.5 supports 8/11/17. **Do not use Java 21.** |
| Python | **3.10 or 3.11** | PySpark 3.5 supports 3.8–3.11. Avoid 3.12. |
| Maven | **3.9.x** | |
| Hadoop client | bundled (3.3.4) | Windows needs `winutils.exe` + `hadoop.dll` |
| Kafka | 3.6.x (Docker) | Projects 11–15 only |
| Docker Desktop | 4.x | Projects 11–20 (Kafka, MinIO, Iceberg REST) |

> **Why Java 17 and not 21?** Spark 3.5's bytecode and dependency set (Netty 4.1.x, Arrow, older Kryo) are validated against JDK 8/11/17. JDK 21 support landed in Spark 4.0. Using 21 on 3.5 produces intermittent `InaccessibleObjectException` and Arrow `Unsafe` failures that are painful to diagnose. Stay on 17.

## 1. Install Java 17

**Windows (PowerShell, elevated):**

```powershell
winget install --id EclipseAdoptium.Temurin.17.JDK -e --accept-source-agreements --accept-package-agreements
```

**Linux (Debian/Ubuntu):**

```bash
sudo apt-get update && sudo apt-get install -y temurin-17-jdk
```

**macOS:**

```bash
brew install --cask temurin@17
```

Verify and set `JAVA_HOME`:

```powershell
# Windows
java -version
[Environment]::SetEnvironmentVariable("JAVA_HOME", "C:\Program Files\Eclipse Adoptium\jdk-17.0.11.9-hotspot", "Machine")
```

```bash
# Linux / macOS
java -version
export JAVA_HOME=$(dirname $(dirname $(readlink -f $(which java))))
echo 'export JAVA_HOME='"$JAVA_HOME" >> ~/.bashrc
```

`java -version` must print `17.0.x`. If it prints 21 or 8, fix `JAVA_HOME` and reorder `PATH` **before continuing** — Maven and Spark both silently pick the wrong JDK otherwise.

## 2. Install Apache Spark 3.5.3

**Windows:** download `spark-3.5.3-bin-hadoop3.tgz` from
`https://archive.apache.org/dist/spark/spark-3.5.3/`
and extract with 7-Zip to `C:\spark` (avoid spaces and OneDrive-synced folders).

**Linux / macOS:**

```bash
cd /opt
sudo curl -LO https://archive.apache.org/dist/spark/spark-3.5.3/spark-3.5.3-bin-hadoop3.tgz
sudo tar -xzf spark-3.5.3-bin-hadoop3.tgz
sudo ln -s /opt/spark-3.5.3-bin-hadoop3 /opt/spark
```

Set environment variables:

```powershell
# Windows (persist to Machine scope)
[Environment]::SetEnvironmentVariable("SPARK_HOME", "C:\spark", "Machine")
$env:Path = "C:\spark\bin;" + $env:Path
spark-submit --version
```

```bash
# Linux / macOS
export SPARK_HOME=/opt/spark
export PATH=$SPARK_HOME/bin:$PATH
spark-submit --version
```

Expected output includes:

```text
Welcome to
      ____              __
     / __/__  ___ _____/ /__
    _\ \/ _ \/ _ `/ __/  '_/
   /___/ .__/\_,_/_/ /_/\_\   version 3.5.3
```

## 3. Windows: `winutils.exe` and `hadoop.dll` (mandatory)

Spark on Windows delegates file permissions and NativeIO calls to Hadoop's Windows binaries. Without them, **every write fails** with:

```text
java.lang.UnsatisfiedLinkError: org.apache.hadoop.io.nativeio.NativeIO$Windows.access0(...)
```

Install them:

```powershell
# Create the Hadoop home layout
New-Item -ItemType Directory -Force -Path "C:\hadoop\bin" | Out-Null

# Fetch winutils + hadoop.dll for Hadoop 3.3.x
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/cdarlint/winutils/master/hadoop-3.3.6/bin/winutils.exe" -OutFile "C:\hadoop\bin\winutils.exe"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/cdarlint/winutils/master/hadoop-3.3.6/bin/hadoop.dll" -OutFile "C:\hadoop\bin\hadoop.dll"

# hadoop.dll must also be visible to the JVM
Copy-Item "C:\hadoop\bin\hadoop.dll" "C:\Windows\System32\hadoop.dll" -Force

[Environment]::SetEnvironmentVariable("HADOOP_HOME", "C:\hadoop", "Machine")
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\hadoop\bin", "Machine")

# Sanity check: must list C:\ without an error
& "C:\hadoop\bin\winutils.exe" ls C:\
```

If you run jobs as a non-admin user and hit `Permission denied` on `C:\tmp\hive`, run once:

```powershell
& "C:\hadoop\bin\winutils.exe" chmod -R 777 C:\tmp\hive
```

## 4. Python environment

```powershell
py -3.11 -m venv $BOOK_HOME\.venv
$BOOK_HOME\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "pyspark==3.5.3" "pyarrow==15.0.2" "pandas==2.2.2" `
    "faker==25.2.0" "pytest==8.2.2" "python-dateutil==2.9.0.post0"
```

```bash
python3.11 -m venv "$BOOK_HOME/.venv"
source "$BOOK_HOME/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install "pyspark==3.5.3" "pyarrow==15.0.2" "pandas==2.2.2" \
    "faker==25.2.0" "pytest==8.2.2" "python-dateutil==2.9.0.post0"
```

**The one rule that prevents 90% of setup pain:** the pip `pyspark` version and `$SPARK_HOME` version must be **identical**. We install the pip package so `import pyspark` resolves inside the venv, and use the tarball's `spark-submit` as the entry point. Both are 3.5.3, so they agree.

Pin the interpreter for the JVM workers:

```powershell
[Environment]::SetEnvironmentVariable("PYSPARK_PYTHON", "$BOOK_HOME\.venv\Scripts\python.exe", "User")
[Environment]::SetEnvironmentVariable("PYSPARK_DRIVER_PYTHON", "$BOOK_HOME\.venv\Scripts\python.exe", "User")
```

```bash
export PYSPARK_PYTHON="$BOOK_HOME/.venv/bin/python"
export PYSPARK_DRIVER_PYTHON="$BOOK_HOME/.venv/bin/python"
```

## 5. Configure Spark defaults (Java 17 `--add-opens`)

Spark 3.5 performs deep reflection into `java.base`, `sun.nio.ch`, and `sun.security.action` (Netty direct buffers, Kryo, Arrow, Hadoop `UserGroupInformation`). Java 17's module system blocks this unless you open the packages explicitly.

Create `%SPARK_HOME%\conf\spark-defaults.conf` (`$SPARK_HOME/conf/spark-defaults.conf`):

```properties
# ---- cluster / driver -------------------------------------------------------
spark.master                          local[*]
spark.driver.memory                   4g
spark.driver.maxResultSize            2g
spark.ui.port                         4040
spark.sql.warehouse.dir               file:///C:/spark-warehouse

# ---- sane local defaults ----------------------------------------------------
spark.sql.shuffle.partitions          8
spark.sql.adaptive.enabled            true
spark.sql.adaptive.coalescePartitions.enabled   true
spark.sql.adaptive.skewJoin.enabled   true
spark.serializer                      org.apache.spark.serializer.KryoSerializer
spark.sql.parquet.compression.codec   snappy

# ---- Java 17 module access (REQUIRED) --------------------------------------
spark.driver.extraJavaOptions         -XX:+IgnoreUnrecognizedVMOptions --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.invoke=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED --add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.util.concurrent=ALL-UNNAMED --add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/sun.nio.cs=ALL-UNNAMED --add-opens=java.base/sun.security.action=ALL-UNNAMED --add-opens=java.base/sun.util.calendar=ALL-UNNAMED -Djdk.reflect.useDirectMethodHandle=false

spark.executor.extraJavaOptions       -XX:+IgnoreUnrecognizedVMOptions --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.lang.invoke=ALL-UNNAMED --add-opens=java.base/java.lang.reflect=ALL-UNNAMED --add-opens=java.base/java.io=ALL-UNNAMED --add-opens=java.base/java.net=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED --add-opens=java.base/java.util.concurrent=ALL-UNNAMED --add-opens=java.base/java.util.concurrent.atomic=ALL-UNNAMED --add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/sun.nio.cs=ALL-UNNAMED --add-opens=java.base/sun.security.action=ALL-UNNAMED --add-opens=java.base/sun.util.calendar=ALL-UNNAMED -Djdk.reflect.useDirectMethodHandle=false
```

In `local[*]` mode the driver *is* the executor JVM, so both properties must be set — a very common cause of "works on the cluster, fails on the laptop."

For the rare case where `spark-defaults.conf` is being ignored (for example, PySpark launched from an unrelated venv), export the options directly:

```powershell
$env:SPARK_SUBMIT_OPTS = "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED"
```

```bash
export SPARK_SUBMIT_OPTS="--add-opens=java.base/sun.nio.ch=ALL-UNNAMED --add-opens=java.base/java.nio=ALL-UNNAMED --add-opens=java.base/java.lang=ALL-UNNAMED --add-opens=java.base/java.util=ALL-UNNAMED"
```

## 6. Maven

```powershell
winget install --id Apache.Maven -e --accept-source-agreements --accept-package-agreements
mvn -version    # must report Java version: 17.x and Maven 3.9.x
```

```bash
brew install maven                # macOS
sudo apt-get install -y maven     # Debian/Ubuntu
mvn -version
```

Pre-warm the local repository once (saves ~2 minutes on the first chapter build):

```bash
mvn -q dependency:get -Dartifact=org.apache.spark:spark-sql_2.12:3.5.3
```

> **Golden rule for Java Spark projects:** Spark dependencies are declared with `<scope>provided</scope>`. The cluster (or `spark-submit`) supplies Spark at runtime. If you bundle Spark into your fat jar, you get `NoSuchMethodError` and `AbstractMethodError` at runtime — always, not sometimes.

## 7. Docker (needed from Part III onward)

```bash
docker --version
docker run --rm hello-world
```

Chapters supply their own compose files. Nothing needs to be running yet.

## 8. Smoke test — Python

Save as `$BOOK_HOME/setup_check.py`:

```python
"""Environment smoke test: validates Spark, Java 17 and Arrow wiring."""
from __future__ import annotations

import logging
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("setup_check")

SCHEMA = StructType(
    [
        StructField("employee", StringType(), False),
        StructField("department", StringType(), False),
        StructField("salary", IntegerType(), False),
    ]
)

ROWS = [
    ("ada", "engineering", 145_000),
    ("grace", "engineering", 152_000),
    ("linus", "platform", 138_000),
    ("margaret", "platform", 161_000),
    ("alan", "research", 129_000),
]


def main() -> int:
    spark = (
        SparkSession.builder.appName("setup-check")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    log.info("Spark version  : %s", spark.version)
    log.info("Java version   : %s", spark.sparkContext._jvm.System.getProperty("java.version"))
    log.info("Default parallelism: %s", spark.sparkContext.defaultParallelism)

    df = spark.createDataFrame(ROWS, schema=SCHEMA)
    result = (
        df.groupBy("department")
        .agg(
            F.count("*").alias("headcount"),
            F.round(F.avg("salary"), 2).alias("avg_salary"),
        )
        .orderBy(F.desc("avg_salary"))
    )
    result.show(truncate=False)

    assert result.count() == 3, "expected three departments"
    assert spark.version.startswith("3.5."), f"unexpected Spark version: {spark.version}"

    spark.stop()
    log.info("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run it:

```bash
spark-submit --master "local[*]" setup_check.py
```

You must see `SMOKE TEST PASSED` and **no** `WARN NativeCodeLoader` beyond the harmless "Unable to load native-hadoop library" line (expected on Windows unless Hadoop native libraries are on `PATH`).

## 9. Smoke test — Java

`$BOOK_HOME/setup-java/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <groupId>com.sparkmastery</groupId>
  <artifactId>setup-java</artifactId>
  <version>1.0.0</version>
  <packaging>jar</packaging>
  <name>setup-java</name>

  <properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <maven.compiler.release>17</maven.compiler.release>
    <spark.version>3.5.3</spark.version>
    <scala.binary.version>2.12</scala.binary.version>
  </properties>

  <dependencies>
    <dependency>
      <groupId>org.apache.spark</groupId>
      <artifactId>spark-sql_${scala.binary.version}</artifactId>
      <version>${spark.version}</version>
      <scope>provided</scope>
    </dependency>
  </dependencies>

  <build>
    <finalName>${project.artifactId}-${project.version}</finalName>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.13.0</version>
        <configuration>
          <release>17</release>
          <compilerArgs>
            <arg>-parameters</arg>
          </compilerArgs>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
```

`$BOOK_HOME/setup-java/src/main/java/com/sparkmastery/setup/HelloSpark.java`:

```java
package com.sparkmastery.setup;

import org.apache.spark.sql.Dataset;
import org.apache.spark.sql.Row;
import org.apache.spark.sql.RowFactory;
import org.apache.spark.sql.SparkSession;
import org.apache.spark.sql.types.DataTypes;
import org.apache.spark.sql.types.StructField;
import org.apache.spark.sql.types.StructType;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;

import static org.apache.spark.sql.functions.avg;
import static org.apache.spark.sql.functions.count;
import static org.apache.spark.sql.functions.desc;
import static org.apache.spark.sql.functions.round;

/**
 * Minimal end-to-end validation of the Java 17 + Spark 3.5 toolchain.
 */
public final class HelloSpark {

    private static final Logger LOG = LoggerFactory.getLogger(HelloSpark.class);

    private static final StructType SCHEMA = DataTypes.createStructType(new StructField[]{
            DataTypes.createStructField("employee", DataTypes.StringType, false),
            DataTypes.createStructField("department", DataTypes.StringType, false),
            DataTypes.createStructField("salary", DataTypes.IntegerType, false)
    });

    private HelloSpark() {
        // utility class
    }

    public static void main(final String[] args) {
        final SparkSession spark = SparkSession.builder()
                .appName("hello-spark")
                .master("local[*]")
                .config("spark.sql.shuffle.partitions", "4")
                .config("spark.ui.enabled", "false")
                .getOrCreate();

        spark.sparkContext().setLogLevel("WARN");

        try {
            LOG.info("Spark version: {}", spark.version());
            LOG.info("Java version : {}", System.getProperty("java.version"));
            LOG.info("Cores        : {}", spark.sparkContext().defaultParallelism());

            final List<Row> rows = List.of(
                    RowFactory.create("ada", "engineering", 145_000),
                    RowFactory.create("grace", "engineering", 152_000),
                    RowFactory.create("linus", "platform", 138_000),
                    RowFactory.create("margaret", "platform", 161_000),
                    RowFactory.create("alan", "research", 129_000)
            );

            final Dataset<Row> df = spark.createDataFrame(rows, SCHEMA);

            final Dataset<Row> result = df.groupBy("department")
                    .agg(
                            count("*").as("headcount"),
                            round(avg("salary"), 2).as("avg_salary")
                    )
                    .orderBy(desc("avg_salary"));

            result.show(false);

            if (result.count() != 3L) {
                throw new IllegalStateException("expected exactly 3 departments");
            }
            if (!spark.version().startsWith("3.5.")) {
                throw new IllegalStateException("unexpected Spark version: " + spark.version());
            }

            LOG.info("SMOKE TEST PASSED: max avg salary = {}",
                    result.first().getAs("avg_salary", Double.class));
        } finally {
            spark.stop();
        }
    }
}
```

Build and run:

```bash
cd setup-java
mvn -q clean package
spark-submit --class com.sparkmastery.setup.HelloSpark --master "local[*]" target/setup-java-1.0.0.jar
```

You must see `SMOKE TEST PASSED`. If both smoke tests pass, every chapter in this book will run unmodified.

## 10. Troubleshooting matrix

| Symptom | Root cause | Fix |
|---|---|---|
| `InaccessibleObjectException: Unable to make field ... accessible: module java.base does not "opens java.lang"` | Missing `--add-opens` | Apply §5; verify `spark.driver.extraJavaOptions` **and** `spark.executor.extraJavaOptions` |
| `java.lang.UnsatisfiedLinkError: ...NativeIO$Windows.access0` | No `winutils.exe` | Apply §3; confirm `HADOOP_HOME` and `hadoop.dll` in `System32` |
| `Python in worker has different version (3.1x) than that in driver` | Venv not pinned | Set `PYSPARK_PYTHON` / `PYSPARK_DRIVER_PYTHON` |
| `NoSuchMethodError` / `AbstractMethodError` in Java jobs | Spark jars bundled in the fat jar | Ensure `<scope>provided</scope>` |
| `ClassNotFoundException: org.apache.spark.sql.SparkSession` at runtime | Missing `provided` deps on classpath | Run via `spark-submit`, not `java -jar` |
| `InvalidClassException` / Kryo errors | Serializer mismatch across versions | Keep Spark and pip versions identical; clear `~/.ivy2/cache` |
| `WARN NativeCodeLoader: Unable to load native-hadoop library` | Native libs absent | Harmless. Ignore unless using LZO or similar codecs |
| `org.apache.hadoop.ipc.RemoteException: ... Permission denied` on Windows | Hive/warehouse permissions | `winutils chmod -R 777 C:\tmp\hive` |
| Maven build takes minutes on first run | Cold local repository | Pre-warm per §6 |
| `AnalysisException: Unable to infer schema` | Empty input directory | Regenerate data; every generator writes ≥ 1 partition |

## 11. Cluster submit delta

Everything in this book runs in `local[*]`. To move a job to a real cluster, the *only* mandatory changes are:

```bash
spark-submit \
  --master yarn \
  --deploy-mode cluster \
  --num-executors 8 \
  --executor-cores 4 \
  --executor-memory 8g \
  --driver-memory 4g \
  --conf spark.sql.shuffle.partitions=800 \
  --conf spark.sql.adaptive.enabled=true \
  retail_etl.py --input hdfs:///data/orders --output hdfs:///data/silver/orders
```

Two rules that keep the migration boring:

1. **Replace every `file:///` path** with an HDFS/S3 URI. Local `file://` paths resolve to the *driver's* disk in cluster mode and will silently produce empty reads.
2. **Scale `spark.sql.shuffle.partitions` to `≈ 2 × total_cores`**, not to the local default of 8. AQE will coalesce downward, but it cannot split a single 20 GB partition.
