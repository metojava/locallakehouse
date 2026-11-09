"""Create small Delta and Iceberg demo tables in the local warehouse.

Run from the backend directory with the backend virtualenv active:

    python seed_demo.py
"""

from __future__ import annotations

import logging
import sys

from app.spark_manager import spark_manager

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("seed-demo")


DELTA_DDL = """
CREATE TABLE IF NOT EXISTS demo.customers (
    id BIGINT,
    name STRING,
    country STRING,
    signed_up DATE
)
USING delta
"""

DELTA_INSERT = """
INSERT INTO demo.customers VALUES
    (1, 'Acme Corp', 'US', CAST('2024-01-15' AS DATE)),
    (2, 'Globex', 'DE', CAST('2024-03-02' AS DATE)),
    (3, 'Initech', 'GB', CAST('2024-06-21' AS DATE)),
    (4, 'Umbrella Labs', 'FR', CAST('2024-09-09' AS DATE))
"""

ICEBERG_DDL = """
CREATE TABLE IF NOT EXISTS local_iceberg.demo.sales (
    sale_id BIGINT,
    region STRING,
    product STRING,
    amount DOUBLE,
    sold_at TIMESTAMP
)
USING iceberg
"""

ICEBERG_INSERT = """
INSERT INTO local_iceberg.demo.sales VALUES
    (101, 'EMEA', 'Starter', 1200.0, CAST('2026-01-04 09:15:00' AS TIMESTAMP)),
    (102, 'AMER', 'Pro', 4800.5, CAST('2026-01-04 11:30:00' AS TIMESTAMP)),
    (103, 'APAC', 'Enterprise', 9900.0, CAST('2026-01-05 02:45:00' AS TIMESTAMP)),
    (104, 'EMEA', 'Pro', 5100.0, CAST('2026-01-05 16:20:00' AS TIMESTAMP))
"""


def main() -> int:
    spark = spark_manager.get_session()
    try:
        spark.sql("CREATE DATABASE IF NOT EXISTS demo")
        spark.sql(DELTA_DDL)
        if spark.table("demo.customers").limit(1).count() == 0:
            spark.sql(DELTA_INSERT)
        logger.info("Delta table ready: demo.customers")

        spark.sql("CREATE NAMESPACE IF NOT EXISTS local_iceberg.demo")
        spark.sql(ICEBERG_DDL)
        if spark.table("local_iceberg.demo.sales").limit(1).count() == 0:
            spark.sql(ICEBERG_INSERT)
        logger.info("Iceberg table ready: local_iceberg.demo.sales")

        logger.info(
            "Row counts -> delta.demo.customers=%d, iceberg.demo.sales=%d",
            spark.table("demo.customers").count(),
            spark.table("local_iceberg.demo.sales").count(),
        )
        return 0
    finally:
        spark_manager.stop()


if __name__ == "__main__":
    sys.exit(main())
