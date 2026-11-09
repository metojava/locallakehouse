from __future__ import annotations

import atexit
import logging
import os
import platform
import threading
from typing import Optional

from pyspark.sql import SparkSession

from .config import Settings, get_settings
from .services.spark_setup import SparkSetupError, resolve_spark_home

logger = logging.getLogger(__name__)


class SparkUnavailableError(RuntimeError):
    """Raised when the local Spark session cannot be created or reached."""


class SparkManager:
    """Process-wide owner of a single local Spark session.

    Spark SQL sessions carry mutable state (current catalog/database, temp
    views, cached tables). The workbench therefore keeps exactly one session
    per process and serialises SQL execution through :attr:`sql_lock`.
    """

    _instance: Optional["SparkManager"] = None
    _instance_lock = threading.Lock()

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._session: Optional[SparkSession] = None
        self._init_lock = threading.RLock()
        self.sql_lock = threading.RLock()
        self._job_group: Optional[str] = None
        self._job_group_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "SparkManager":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def is_started(self) -> bool:
        session = self._session
        if session is None:
            return False
        try:
            return not session.sparkContext._jsc.sc().isStopped()
        except Exception:  # pragma: no cover - JVM already gone
            return False

    @property
    def version(self) -> Optional[str]:
        if not self.is_started or self._session is None:
            return None
        try:
            return self._session.version
        except Exception:  # pragma: no cover - JVM shutting down
            return None

    def get_session(self) -> SparkSession:
        if self.is_started:
            assert self._session is not None
            return self._session

        with self._init_lock:
            if self.is_started:
                assert self._session is not None
                return self._session
            self._session = self._build_session()
            return self._session

    def _build_session(self) -> SparkSession:
        settings = self._settings
        settings.ensure_directories()

        # Resolve the Spark installation to run: an explicitly configured (and
        # compatible) external Spark home, otherwise the PySpark-bundled one.
        try:
            spark_home = resolve_spark_home()
        except SparkSetupError as exc:
            raise SparkUnavailableError(
                "The configured Spark installation cannot be used. " + str(exc)
            ) from exc
        os.environ["SPARK_HOME"] = str(spark_home["path"])
        logger.info(
            "Using Spark %s (%s) from %s",
            spark_home.get("version") or "unknown",
            spark_home.get("source"),
            spark_home["path"],
        )

        if platform.system() == "Windows":
            hadoop_home = os.environ.get("HADOOP_HOME")
            if not hadoop_home:
                logger.warning(
                    "HADOOP_HOME is not set. Spark on Windows needs winutils.exe "
                    "for file permission operations. See README.md -> Windows setup."
                )
        if not os.environ.get("JAVA_HOME"):
            logger.warning(
                "JAVA_HOME is not set. Spark 4.1 requires Java 17 or newer on PATH."
            )
        os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

        delta_warehouse_uri = settings.delta_warehouse_dir.as_uri()
        iceberg_warehouse_uri = settings.iceberg_warehouse_dir.as_uri()
        metastore_db = (settings.spark_metastore_dir / "metastore_db").resolve()
        metastore_jdbc = (
            f"jdbc:derby:;databaseName={metastore_db.as_posix()};create=true"
        )

        builder = (
            SparkSession.builder.appName(settings.spark_app_name)
            .master(settings.spark_master)
            .config("spark.driver.memory", settings.spark_driver_memory)
            .config("spark.driver.host", "127.0.0.1")
            .config("spark.driver.bindAddress", "127.0.0.1")
            .config("spark.ui.enabled", "false")
            .config("spark.ui.showConsoleProgress", "false")
            .config("spark.local.dir", str(settings.spark_local_dir))
            .config("spark.sql.warehouse.dir", delta_warehouse_uri)
            # Use the on-disk Derby Hive metastore instead of Spark's default
            # in-memory catalog, otherwise Delta tables disappear on restart.
            .config("spark.sql.catalogImplementation", "hive")
            .config("spark.hadoop.javax.jdo.option.ConnectionURL", metastore_jdbc)
            .config(
                "spark.hadoop.javax.jdo.option.ConnectionDriverName",
                "org.apache.derby.jdbc.EmbeddedDriver",
            )
            .config("spark.hadoop.datanucleus.schema.autoCreateAll", "true")
            .config("spark.hadoop.hive.metastore.schema.verification", "false")
            .config("spark.sql.shuffle.partitions", "8")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.defaultCatalog", "spark_catalog")
            .config("spark.sql.parquet.compression.codec", "snappy")
            .config(
                "spark.sql.extensions",
                ",".join(
                    (
                        "io.delta.sql.DeltaSparkSessionExtension",
                        "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
                    )
                ),
            )
            # Delta Lake is exposed through Spark's session catalog. Tables can
            # be queried as ``db.table`` or ``spark_catalog.db.table``.
            .config(
                "spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog",
            )
            # Apache Iceberg gets its own Hadoop-backed catalog rooted in the
            # local warehouse. Tables are queried as ``local_iceberg.db.table``.
            .config(
                "spark.sql.catalog.local_iceberg",
                "org.apache.iceberg.spark.SparkCatalog",
            )
            .config("spark.sql.catalog.local_iceberg.type", "hadoop")
            .config(
                "spark.sql.catalog.local_iceberg.warehouse", iceberg_warehouse_uri
            )
        )

        if settings.spark_packages:
            builder = builder.config("spark.jars.packages", settings.spark_packages)
        if settings.spark_jars:
            builder = builder.config("spark.jars", settings.spark_jars)

        for option in settings.spark_extra_options.split(";"):
            option = option.strip()
            if not option or "=" not in option:
                continue
            key, value = option.split("=", 1)
            builder = builder.config(key.strip(), value.strip())

        logger.info(
            "Starting local Spark session (master=%s, packages=%s)",
            settings.spark_master,
            settings.spark_packages or "<preinstalled jars>",
        )
        try:
            session = builder.getOrCreate()
            session.sparkContext.setLogLevel(settings.spark_log_level)
        except Exception as exc:  # pragma: no cover - environment dependent
            raise SparkUnavailableError(
                "Could not start Apache Spark. Verify Java 17+, JAVA_HOME, network "
                "access to Maven Central for the Delta/Iceberg jars, and on Windows "
                "HADOOP_HOME/winutils.exe. Original error: " + str(exc)
            ) from exc

        logger.info(
            "Spark %s ready. Delta warehouse=%s Iceberg warehouse=%s",
            session.version,
            settings.delta_warehouse_dir,
            settings.iceberg_warehouse_dir,
        )
        return session

    def stop(self) -> None:
        with self._init_lock:
            session = self._session
            self._session = None
            if session is not None:
                try:
                    session.stop()
                    logger.info("Spark session stopped")
                except Exception as exc:  # pragma: no cover - shutdown best effort
                    logger.warning("Error while stopping Spark: %s", exc)


spark_manager = SparkManager.instance()
atexit.register(spark_manager.stop)
