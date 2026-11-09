from __future__ import annotations

import json
import logging
import re
import secrets
import threading
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from ..config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.RLock()

# Masked placeholder so we can round-trip passwords without exposing them.
_PASSWORD_PLACEHOLDER = "__OPENCODE_KEEP_PASSWORD__"

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


@dataclass
class DatabaseConnection:
    id: str
    name: str
    dialect: str  # mysql | postgresql | sqlserver
    host: str
    port: int
    database: str
    username: str
    password: str
    properties: Optional[Dict[str, str]] = None

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "dialect": self.dialect,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "has_password": bool(self.password),
            "properties": self.properties or {},
        }

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


class ConnectionValidationError(ValueError):
    pass


class ConnectionNotFoundError(KeyError):
    pass


def _connections_path() -> Any:
    return get_settings().connections_file


def _validate_connection(conn: DatabaseConnection) -> None:
    if not conn.id or not _ID_PATTERN.match(conn.id):
        raise ConnectionValidationError(
            "Connection id must start with a lowercase letter and contain only "
            "lowercase letters, digits, underscores, and hyphens (max 64 chars)."
        )
    if not conn.name or len(conn.name) > 120:
        raise ConnectionValidationError(
            "Connection name is required and must be at most 120 characters."
        )
    if conn.dialect not in {"mysql", "postgresql", "sqlserver"}:
        raise ConnectionValidationError(
            "dialect must be one of: mysql, postgresql, sqlserver."
        )
    if not conn.host or len(conn.host) > 253:
        raise ConnectionValidationError("host is required and too long.")
    if not 1 <= conn.port <= 65535:
        raise ConnectionValidationError("port must be between 1 and 65535.")
    if not conn.database:
        raise ConnectionValidationError("database is required.")


def _load_raw() -> List[Dict[str, Any]]:
    path = _connections_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        logger.warning("Connections file is corrupt: %s", exc)
        return []
    if not isinstance(data, list):
        return []
    return data


def _save_raw(connections: List[Dict[str, Any]]) -> None:
    path = _connections_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(connections, handle, indent=2)


def _dict_to_connection(data: Dict[str, Any]) -> DatabaseConnection:
    return DatabaseConnection(
        id=str(data["id"]),
        name=str(data["name"]),
        dialect=str(data["dialect"]),
        host=str(data["host"]),
        port=int(data["port"]),
        database=str(data["database"]),
        username=str(data.get("username", "")),
        password=str(data.get("password", "")),
        properties=dict(data.get("properties") or {}),
    )


def list_connections() -> List[DatabaseConnection]:
    with _lock:
        return [_dict_to_connection(item) for item in _load_raw()]


def get_connection(connection_id: str) -> DatabaseConnection:
    with _lock:
        for item in _load_raw():
            if item.get("id") == connection_id:
                return _dict_to_connection(item)
    raise ConnectionNotFoundError(f"Connection '{connection_id}' not found.")


def resolve_connection(connection_id: str) -> DatabaseConnection:
    """Return a connection from saved connections or the databases.cfg file."""

    from .database_config import get_config_connection, to_database_connection

    try:
        return get_connection(connection_id)
    except ConnectionNotFoundError:
        pass
    try:
        return to_database_connection(get_config_connection(connection_id))
    except KeyError as exc:
        raise ConnectionNotFoundError(
            f"Connection '{connection_id}' not found."
        ) from exc


def create_connection(
    name: str,
    dialect: str,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    properties: Optional[Dict[str, str]] = None,
    connection_id: Optional[str] = None,
) -> DatabaseConnection:
    base_id = connection_id or re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "connection"
    candidate_id = base_id
    existing_ids = {item.get("id") for item in _load_raw()}
    counter = 1
    while candidate_id in existing_ids:
        candidate_id = f"{base_id}_{counter}"
        counter += 1

    conn = DatabaseConnection(
        id=candidate_id,
        name=name,
        dialect=dialect,
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        properties=properties,
    )
    _validate_connection(conn)

    with _lock:
        connections = _load_raw()
        connections.append(asdict(conn))
        _save_raw(connections)
    return conn


def update_connection(
    connection_id: str,
    name: Optional[str] = None,
    dialect: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    properties: Optional[Dict[str, str]] = None,
) -> DatabaseConnection:
    with _lock:
        connections = _load_raw()
        for index, item in enumerate(connections):
            if item.get("id") == connection_id:
                if name is not None:
                    item["name"] = name
                if dialect is not None:
                    item["dialect"] = dialect
                if host is not None:
                    item["host"] = host
                if port is not None:
                    item["port"] = port
                if database is not None:
                    item["database"] = database
                if username is not None:
                    item["username"] = username
                if password is not None and password != _PASSWORD_PLACEHOLDER:
                    item["password"] = password
                if properties is not None:
                    item["properties"] = properties
                conn = _dict_to_connection(item)
                _validate_connection(conn)
                _save_raw(connections)
                return conn
    raise ConnectionNotFoundError(f"Connection '{connection_id}' not found.")


def delete_connection(connection_id: str) -> None:
    with _lock:
        connections = [item for item in _load_raw() if item.get("id") != connection_id]
        if len(connections) == len(_load_raw()):
            raise ConnectionNotFoundError(f"Connection '{connection_id}' not found.")
        _save_raw(connections)


def test_connection(connection_id: str) -> Dict[str, Any]:
    """Try to read a single row from the connection to verify reachability."""

    from ..spark_manager import spark_manager

    conn = resolve_connection(connection_id)
    with spark_manager.sql_lock:
        spark = spark_manager.get_session()
        try:
            df = (
                spark.read.format("jdbc")
                .option("url", conn.jdbc_url())
                .option("driver", conn.driver_class())
                .option("user", conn.username)
                .option("password", conn.password)
                .option("dbtable", "(SELECT 1 AS connectivity_test) AS t")
                .load()
            )
            row_count = df.count()
            return {"ok": True, "row_count": row_count}
        except Exception as exc:
            logger.warning("Connection test failed for %s: %s", connection_id, exc)
            raise ConnectionValidationError(
                f"Could not connect to {conn.name}: {exc}"
            ) from exc


def generate_password() -> str:
    """Generate a random placeholder used by the UI for password round-trips."""

    return _PASSWORD_PLACEHOLDER + secrets.token_hex(8)
