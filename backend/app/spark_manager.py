from __future__ import annotations

import atexit
import logging
import os
import platform
import threading
from typing import Optional

from pyspark.sql import SparkSession

from .config import Settings, ensure_pyspark_python, get_settings
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

        # A py4j gateway port inherited from another process would make PySpark
        # connect to a dead JVM instead of launching its own.
        os.environ.pop("PYSPARK_GATEWAY_PORT", None)
        os.environ.pop("PYSPARK_GATEWAY_SECRET", None)

        # Spark's Python workers default to ``python3``, which is absent on
        # Windows. Point them at the interpreter running the backend so RDD and
        # UDF work does not fail with "Cannot run program \"python3\"".
        python_executable = ensure_pyspark_python()
        logger.info("Spark Python workers will use %s", python_executable)

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
            # On Windows the local-mode executor starts its heartbeater before
            # SparkContext initialises the driver BlockManager. With the default
            # 10s interval the first heartbeat can land in that window and Spark
            # throws "BlockManagerId.executorId() ... idWithoutTopologyInfo is
            # null" (SPARK-53042). The first heartbeat is sent after
            # interval + random(0..interval), so a long interval keeps it well
            # past initialisation. Spark requires network.timeout to be greater
            # than the heartbeat interval, so both are raised together.
            .config("spark.executor.heartbeatInterval", "300s")
            .config("spark.network.timeout", "600s")
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
            self._reset_pyspark_state()
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

    @staticmethod
    def _reset_pyspark_state() -> None:
        """Forget PySpark's cached py4j gateway after a failed startup.

        ``SparkSession.builder.getOrCreate()`` stores the gateway on
        ``SparkContext`` class attributes. If startup fails the JVM may already
        be gone, and later attempts would keep reusing that dead gateway instead
        of launching a fresh one. Clearing the cached objects lets the next
        request start cleanly without restarting the backend.
        """
        try:
            from pyspark import SparkContext

            gateway = SparkContext._gateway
            SparkContext._gateway = None
            SparkContext._jvm = None
            SparkContext._active_spark_context = None
            if gateway is not None:
                try:
                    gateway.shutdown_gateway()
                except Exception:  # pragma: no cover - gateway already dead
                    pass
        except Exception:  # pragma: no cover - defensive
            logger.debug("Could not reset PySpark gateway state", exc_info=True)

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
