# Chapter 8 — Real-World Project

In this project you will build a small sales analytics pipeline. You will:

1. Create source tables from CSV and a PostgreSQL database.
2. Clean and transform the data with PySpark.
3. Store the final model as a Delta table.
4. Run analytics queries and time-travel to previous versions.

## Step 1 — Create source data

Import the sample `data/accounts.json` file as a Spark table named `default.customers`.

Then create a sample orders CSV at `C:\data\orders.csv`:

```csv
order_id,customer_id,amount,status,created_at
1,1,99.99,paid,2026-01-15
2,1,149.50,paid,2026-01-16
3,6,29.99,refunded,2026-01-17
4,13,199.00,paid,2026-01-18
5,1,75.00,paid,2026-01-20
```

Import it as a Delta table named `default.orders_raw`.

## Step 2 — Clean with PySpark

```python
from pyspark.sql import functions as F

orders = spark.table("demo.orders_raw")
customers = spark.table("spark_catalog.default.customers")

clean_orders = (
    orders
    .filter(F.col("status") != "refunded")
    .withColumn("amount", F.col("amount").cast("double"))
    .withColumn("created_at", F.to_date("created_at", "yyyy-MM-dd"))
    .dropDuplicates(["order_id"])
)

customer_metrics = (
    clean_orders
    .groupBy("customer_id")
    .agg(
        F.count("*").alias("total_orders"),
        F.sum("amount").alias("lifetime_value"),
        F.max("created_at").alias("last_order_date")
    )
)

final = (
    customers
    .select("account_number", "firstname", "lastname", "state")
    .join(
        customer_metrics,
        customers.account_number == customer_metrics.customer_id,
        "left"
    )
    .fillna(0, ["total_orders", "lifetime_value"])
)

final.write.format("delta").mode("overwrite").saveAsTable("demo.customer_360")

# Return a preview
spark.table("demo.customer_360").limit(20)
```

## Step 3 — Analytics with SQL

```sql
-- Top customers by lifetime value
SELECT firstname, lastname, state, lifetime_value
FROM demo.customer_360
ORDER BY lifetime_value DESC
LIMIT 10;

-- Revenue by state
SELECT state, SUM(lifetime_value) AS total_revenue
FROM demo.customer_360
GROUP BY state
ORDER BY total_revenue DESC;

-- Table history
DESCRIBE HISTORY demo.customer_360;
```

## Step 4 — Time travel

```sql
-- Restore the first version (replace with an actual version number)
SELECT * FROM demo.customer_360 VERSION AS OF 0 LIMIT 5;
```

> **Congratulations!** You have built a complete lakehouse pipeline: ingestion, transformation, modeling, and analytics — all on your local machine.

---

[← PySpark Transformations](07-pyspark-transformations.md) · [Back to Table of Contents →](../index.md)
