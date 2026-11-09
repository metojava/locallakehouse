from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..config import get_settings
from ..spark_manager import spark_manager
from .database_connections import DatabaseConnection
from .sql_engine import format_spark_error

logger = logging.getLogger(__name__)


@dataclass
class ConfigDatabaseConnection:
    id: str
    name: str
    dialect: str
    host: str
    port: int
    database: str
    username: str
    password: str

    def jdbc_url(self) -> str:
        if self.dialect == "mysql":
            return (
                f"jdbc:mysql://{self.host}:{self.port}/{self.database}"
                "?useSSL=false&allowPublicKeyRetrieval=true"
            )
        if self.dialect == "postgresql":
            return f"jdbc:postgresql://{self.host}:{self.port}/{self.database}"
        if self.dialect == "sqlserver":
            return (
                f"jdbc:sqlserver://{self.host}:{self.port}"
                f";databaseName={self.database};encrypt=false"
            )
        raise ValueError(f"Unsupported dialect: {self.dialect}")

    def driver_class(self) -> str:
        if self.dialect == "mysql":
            return "com.mysql.cj.jdbc.Driver"
        if self.dialect == "postgresql":
            return "org.postgresql.Driver"
        if self.dialect == "sqlserver":
            return "com.microsoft.sqlserver.jdbc.SQLServerDriver"
        raise ValueError(f"Unsupported dialect: {self.dialect}")

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "dialect": self.dialect,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
        }


def _config_path() -> Any:
    return get_settings().database_config_file


def _infer_dialect(section_name: str) -> Optional[str]:
    lowered = section_name.lower()
    for dialect in ("mysql", "postgresql", "sqlserver"):
        if lowered.startswith(f"{dialect}.") or lowered == dialect:
            return dialect
    return None


def _parse_connection(section: str, items: Dict[str, str]) -> ConfigDatabaseConnection:
    dialect = items.get("dialect") or _infer_dialect(section)
    if dialect not in {"mysql", "postgresql", "sqlserver"}:
        raise ValueError(
            f"Section '{section}' must specify a dialect (mysql, postgresql, sqlserver)."
        )
    base_id = section.split(".", 1)[-1] if "." in section else section
    return ConfigDatabaseConnection(
        id=base_id,
        name=items.get("name") or base_id,
        dialect=dialect,
        host=items.get("host", "localhost"),
        port=int(items.get("port", "5432")),
        database=items.get("database", ""),
        username=items.get("username", ""),
        password=items.get("password", ""),
    )


def load_config_connections() -> List[ConfigDatabaseConnection]:
    path = _config_path()
    if not path.exists():
        return []

    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not read database config %s: %s", path, exc)
        return []

    connections: List[ConfigDatabaseConnection] = []
    for section in parser.sections():
        try:
            items = dict(parser.items(section))
            connections.append(_parse_connection(section, items))
        except Exception as exc:
            logger.warning("Skipping database config section '%s': %s", section, exc)
    return connections


def get_config_connection(connection_id: str) -> ConfigDatabaseConnection:
    for conn in load_config_connections():
        if conn.id == connection_id:
            return conn
    raise KeyError(f"Config connection '{connection_id}' not found.")


def list_config_databases(connection_id: str) -> Dict[str, Any]:
    conn = get_config_connection(connection_id)
    with spark_manager.sql_lock:
        spark = spark_manager.get_session()
        try:
            df = (
                spark.read.format("jdbc")
                .option("url", conn.jdbc_url())
                .option("driver", conn.driver_class())
                .option("user", conn.username)
                .option("password", conn.password)
                .option(
                    "dbtable",
                    "(SELECT schema_name AS database_name "
                    "FROM information_schema.schemata) AS t",
                )
                .load()
            )
            by_lower = {name.lower(): name for name in df.columns}
            name_key = by_lower.get("database_name") or by_lower.get("schema_name")
            if not name_key:
                raise RuntimeError(
                    "The database did not expose a schema list via information_schema."
                )
            databases = sorted({str(row[name_key]) for row in df.collect()})
            return {
                "connection_id": connection_id,
                "databases": databases,
                "default": conn.database,
            }
        except Exception as exc:
            message = format_spark_error(exc)
            logger.warning("Could not list databases for %s: %s", connection_id, message)
            raise RuntimeError(message) from exc


def list_config_tables(
    connection_id: str, database: Optional[str] = None
) -> List[Dict[str, Any]]:
    conn = get_config_connection(connection_id)
    with spark_manager.sql_lock:
        spark = spark_manager.get_session()
        try:
            df = (
                spark.read.format("jdbc")
                .option("url", conn.jdbc_url())
                .option("driver", conn.driver_class())
                .option("user", conn.username)
                .option("password", conn.password)
                .option(
                    "dbtable",
                    "(SELECT table_schema AS schema_name, table_name AS object_name "
                    "FROM information_schema.tables "
                    "WHERE table_type = 'BASE TABLE') AS t",
                )
                .load()
            )
            # MySQL returns information_schema columns in upper case, so resolve
            # the projected columns case-insensitively.
            by_lower = {name.lower(): name for name in df.columns}
            schema_key = by_lower.get("schema_name") or by_lower.get("table_schema")
            name_key = by_lower.get("object_name") or by_lower.get("table_name")
            if not schema_key or not name_key:
                raise RuntimeError(
                    "The database did not expose schema/table columns in "
                    "information_schema."
                )
            rows = df.collect()
            tables = []
            for row in rows:
                schema = str(row[schema_key])
                if database and schema.lower() != database.lower():
                    continue
                name = str(row[name_key])
                tables.append(
                    {
                        "schema": schema,
                        "name": name,
                        "full_name": f"{schema}.{name}",
                    }
                )
            tables.sort(key=lambda t: (t["schema"].lower(), t["name"].lower()))
            return tables
        except Exception as exc:
            message = format_spark_error(exc)
            logger.warning("Could not list tables for %s: %s", connection_id, message)
            raise RuntimeError(message) from exc


def to_database_connection(conn: ConfigDatabaseConnection) -> DatabaseConnection:
    return DatabaseConnection(
        id=conn.id,
        name=conn.name,
        dialect=conn.dialect,
        host=conn.host,
        port=conn.port,
        database=conn.database,
        username=conn.username,
        password=conn.password,
    )
