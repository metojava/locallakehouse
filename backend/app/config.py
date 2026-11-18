from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    """Runtime configuration for the local lakehouse workbench.

    Every field can be overridden with a ``LAKEHOUSE_``-prefixed environment
    variable, for example ``LAKEHOUSE_WAREHOUSE_DIR=D:/lakehouse``.
    """

    model_config = SettingsConfigDict(
        env_prefix="LAKEHOUSE_",
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Open Lakehouse Workbench"
    api_prefix: str = "/api"
    cors_origins: Tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:4174",
        "http://127.0.0.1:4174",
    )

    warehouse_dir: Path = PROJECT_ROOT / "data_warehouse"
    spark_local_dir: Path = PROJECT_ROOT / ".spark_tmp"
    # Embedded Derby Hive metastore shared by every Spark session. Keeping the
    # metastore on disk is what makes Delta databases/tables survive restarts.
    spark_metastore_dir: Path = PROJECT_ROOT / ".spark_metastore"
    # Optional INI-style file with pre-defined database connections.
    database_config_file: Path = PROJECT_ROOT / "databases.cfg"

    spark_app_name: str = "OpenLakehouseWorkbench"
    spark_master: str = "local[*]"
    spark_driver_memory: str = "2g"
    spark_log_level: str = "WARN"

    # Optional path to an external Apache Spark installation (must be a Spark
    # release compatible with the PySpark client below, i.e. same major.minor).
    # When unset the Spark distribution bundled with the PySpark wheel is used.
    spark_home: Optional[Path] = None
    # Where the optional "download & install Spark" action extracts releases.
    spark_dist_dir: Path = PROJECT_ROOT / ".spark_dist"
    # JSON file that stores UI-driven overrides (e.g. the chosen Spark home)
    # so they survive backend restarts.
    runtime_settings_file: Path = PROJECT_ROOT / ".runtime_settings.json"

    # Spark 4.1.x is the newest Spark release that both Delta and Iceberg
    # publish connectors for (see README for the compatibility matrix).
    delta_package: str = "io.delta:delta-spark_2.13:4.3.1"
    iceberg_package: str = (
        "org.apache.iceberg:iceberg-spark-runtime-4.1_2.13:1.12.0"
    )
    avro_package: str = "org.apache.spark:spark-avro_2.13:4.1.4"
    jdbc_mysql_package: str = "com.mysql:mysql-connector-j:8.4.0"
    jdbc_postgres_package: str = "org.postgresql:postgresql:42.7.3"
    jdbc_sqlserver_package: str = "com.microsoft.sqlserver:mssql-jdbc:12.6.1.jre11"
    spark_jars: Optional[str] = None
    spark_extra_options: str = ""

    max_result_rows: int = 1_000
    query_timeout_seconds: int = 300
    storage_max_entries: int = 5_000
    storage_max_depth: int = 6
    # Maximum number of bytes returned when previewing a warehouse file.
    storage_preview_max_bytes: int = 2 * 1024 * 1024

    @property
    def connections_file(self) -> Path:
        return self.warehouse_dir / ".connections.json"

    @property
    def delta_warehouse_dir(self) -> Path:
        return self.warehouse_dir / "delta"

    @property
    def iceberg_warehouse_dir(self) -> Path:
        return self.warehouse_dir / "iceberg"

    @property
    def spark_packages(self) -> str:
        packages = [
            p.strip()
            for p in (
                self.delta_package,
                self.iceberg_package,
                self.avro_package,
                self.jdbc_mysql_package,
                self.jdbc_postgres_package,
                self.jdbc_sqlserver_package,
            )
        ]
        return ",".join(p for p in packages if p)

    def ensure_directories(self) -> None:
        for directory in (
            self.warehouse_dir,
            self.delta_warehouse_dir,
            self.iceberg_warehouse_dir,
            self.spark_local_dir,
            self.spark_metastore_dir,
            self.spark_dist_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def _is_python_executable(value: str) -> bool:
    if os.path.isabs(value):
        return os.path.isfile(value)
    return shutil.which(value) is not None


def ensure_pyspark_python() -> str:
    """Make Spark's Python workers use the interpreter running the backend.

    PySpark falls back to the literal command ``python3``. That name does not
    exist on a default Windows installation, so RDD/UDF work fails with
    ``java.io.IOException: Cannot run program "python3"``. Pointing the setting
    at ``sys.executable`` also guarantees workers run inside the backend
    virtualenv and can import the same packages.

    Called at import time so both the in-process Spark session and
    ``spark-submit`` child processes (Java/Scala runs) inherit the value.
    """

    configured = os.environ.get("PYSPARK_PYTHON")
    if not configured or not _is_python_executable(configured):
        configured = sys.executable
    os.environ["PYSPARK_PYTHON"] = configured
    # Only used by the PySpark shells; keep an explicit user choice (e.g.
    # ipython) but provide a working default for child processes.
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", configured)
    return configured


ensure_pyspark_python()
