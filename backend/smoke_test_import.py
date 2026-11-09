"""Smoke test: import the sample JSON file as Delta, Iceberg, and Spark tables."""
from __future__ import annotations

import shutil
from pathlib import Path

from app.services.importer import import_file
from app.spark_manager import spark_manager

WAREHOUSE = Path(__file__).resolve().parent.parent / "data_warehouse"
SAMPLE = Path(r"C:\Users\dell\Desktop\warehouse\data\accounts.json")


def clean_namespace(catalog: str, namespace: str) -> None:
    spark = spark_manager.get_session()
    if catalog == "spark_catalog":
        spark.sql(f"DROP TABLE IF EXISTS {namespace}.accounts_smoke")
    else:
        spark.sql(f"DROP TABLE IF EXISTS {catalog}.{namespace}.accounts_smoke")


def main() -> None:
    for fmt in ("delta", "iceberg", "spark"):
        ns = f"smoke_{fmt}"
        clean_namespace("spark_catalog" if fmt != "iceberg" else "local_iceberg", ns)
        result = import_file(
            source_path=str(SAMPLE),
            table_name="accounts_smoke",
            namespace=ns,
            table_format=fmt,
            mode="overwrite",
        )
        print(f"{fmt}: {result['row_count']} rows -> {result['table']}")

    spark_manager.stop()

    # Clean up smoke directories
    for fmt in ("delta", "iceberg"):
        path = WAREHOUSE / fmt / f"smoke_{fmt}"
        if path.exists():
            shutil.rmtree(path)
    print("Smoke test passed.")


if __name__ == "__main__":
    main()
