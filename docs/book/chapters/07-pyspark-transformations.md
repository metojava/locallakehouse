# Chapter 7 — PySpark Transformations

The **PySpark Editor** runs Python scripts against the shared SparkSession. The variable `spark` is already available. Return or assign a DataFrame to see a preview.

## Read and inspect data

```python
df = spark.table("local_iceberg.demo.sales")

print("Rows:", df.count())
df.printSchema()
df.show(5)

# Return the DataFrame for a UI preview
df
```

## DataFrame transformations

```python
from pyspark.sql import functions as F

sales = spark.table("local_iceberg.demo.sales")

result = (
    sales
    .filter(F.col("amount") > 100)
    .withColumn("year", F.year("sold_at"))
    .groupBy("year", "country")
    .agg(
        F.count("*").alias("orders"),
        F.sum("amount").alias("revenue"),
        F.avg("amount").alias("avg_order")
    )
    .orderBy(F.desc("revenue"))
)

result
```

## Window functions

```python
from pyspark.sql.window import Window

window_spec = Window.partitionBy("customer_id").orderBy("sold_at")

ranked = (
    sales
    .withColumn("running_total", F.sum("amount").over(window_spec))
    .withColumn("rank", F.row_number().over(window_spec))
)

ranked
```

## User-defined functions (UDFs)

```python
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

@udf(StringType())
def tier(amount):
    if amount > 500:
        return "gold"
    if amount > 100:
        return "silver"
    return "bronze"

sales_with_tier = sales.withColumn("customer_tier", tier(F.col("amount")))
sales_with_tier.groupBy("customer_tier").count()
```

## Write results back

```python
# Write to a Delta table
result.write.format("delta").mode("overwrite").saveAsTable("demo.sales_summary")

# Write to an Iceberg table
result.write.format("iceberg").mode("overwrite").saveAsTable("local_iceberg.demo.sales_summary")

# Confirm
spark.table("demo.sales_summary").show()
```

> **Tip:** PySpark uses lazy evaluation. Nothing executes until you call an action like `count()`, `show()`, or write. The workbench preview automatically triggers an action on the returned DataFrame.

---

[← Importing Data](06-data-import.md) · [Next: Real-World Project →](08-real-world-project.md)
