export interface SqlSample {
  id: string;
  label: string;
  description: string;
  sql: string;
}

export interface PySparkSample {
  id: string;
  label: string;
  description: string;
  script: string;
}

export const DEFAULT_SQL = `-- Welcome to the local Open Lakehouse Workbench.
-- Ctrl/Cmd + Enter runs the script. Multiple statements are executed in order.
SELECT
  current_catalog()       AS active_catalog,
  current_database()      AS active_database,
  current_date()          AS today,
  current_timestamp()     AS now,
  'spark + iceberg + delta' AS stack;
`;

export const DEFAULT_PYSPARK = `# Welcome to the local PySpark workspace.
# The 'spark' variable is the shared SparkSession.
# Return or assign a DataFrame to see a preview.

from pyspark.sql import functions as F

df = spark.range(100).withColumn("value", F.rand())
df
`;

export const SQL_SAMPLES: SqlSample[] = [
  {
    id: "iceberg-preview",
    label: "Iceberg preview",
    description: "Read the demo Iceberg table created by seed_demo.py",
    sql: "SELECT *\nFROM local_iceberg.demo.sales\nORDER BY sold_at DESC\nLIMIT 100;\n",
  },
  {
    id: "delta-preview",
    label: "Delta preview",
    description: "Read the demo Delta table created by seed_demo.py",
    sql: "SELECT *\nFROM demo.customers\nORDER BY id\nLIMIT 100;\n",
  },
  {
    id: "iceberg-create",
    label: "Create Iceberg",
    description: "Create an Iceberg table in the local Hadoop catalog",
    sql: `CREATE TABLE IF NOT EXISTS local_iceberg.demo.events (
  event_id BIGINT,
  event_type STRING,
  payload STRING,
  event_ts TIMESTAMP
)
USING iceberg;

INSERT INTO local_iceberg.demo.events VALUES
  (1, 'page_view', '{"page":"/pricing"}', current_timestamp()),
  (2, 'signup', '{"plan":"pro"}', current_timestamp());
`,
  },
  {
    id: "delta-create",
    label: "Create Delta",
    description: "Create a Delta table in Spark's Delta-backed catalog",
    sql: `CREATE TABLE IF NOT EXISTS demo.orders (
  order_id BIGINT,
  customer_id BIGINT,
  total DOUBLE,
  ordered_at TIMESTAMP
)
USING delta;

INSERT INTO demo.orders VALUES
  (1001, 1, 249.99, current_timestamp()),
  (1002, 2, 1899.00, current_timestamp());
`,
  },
];

export const PYSPARK_SAMPLES: PySparkSample[] = [
  {
    id: "pyspark-range",
    label: "Spark range",
    description: "Create a simple DataFrame from a range",
    script: `from pyspark.sql import functions as F

df = spark.range(100).withColumn("value", F.rand())
df
`,
  },
  {
    id: "pyspark-read-json",
    label: "Read JSON file",
    description: "Load the sample accounts JSON file as a DataFrame",
    script: `df = spark.read.json("C:/Users/dell/Desktop/warehouse/data/accounts.json")
df.printSchema()
df.groupBy("state").count().orderBy("count", ascending=False)
`,
  },
  {
    id: "pyspark-catalogs",
    label: "Catalog tables",
    description: "List tables in the Delta and Iceberg catalogs",
    script: `spark.catalog.setCurrentCatalog("spark_catalog")
spark.sql("SHOW TABLES").show()

spark.catalog.setCurrentCatalog("local_iceberg")
spark.sql("SHOW TABLES").show()
`,
  },
];

export const DEFAULT_JAVA = `// Java runs as a separate Spark job (spark-submit). Define public class Main.
// Each run builds its own SparkSession; variables do not persist between runs.
import org.apache.spark.sql.Dataset;
import org.apache.spark.sql.Row;
import org.apache.spark.sql.SparkSession;

public class Main {
  public static void main(String[] args) {
    SparkSession spark = SparkSession.builder().getOrCreate();
    Dataset<Row> df = spark.range(10).selectExpr("id", "id * id AS square");
    df.show();
    System.out.println("rows = " + df.count());
    spark.stop();
  }
}
`;

export const DEFAULT_SCALA = `// Scala runs as a separate Spark job (spark-submit). Define object Main.
// Each run builds its own SparkSession; variables do not persist between runs.
import org.apache.spark.sql.SparkSession

object Main {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder().getOrCreate()
    val df = spark.range(10).selectExpr("id", "id * id AS square")
    df.show()
    println(s"rows = \${df.count()}")
    spark.stop()
  }
}
`;
