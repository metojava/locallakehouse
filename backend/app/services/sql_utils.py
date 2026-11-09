from __future__ import annotations

import base64
import datetime as dt
import decimal
import json
import math
from typing import Any, Dict, List, Optional

ROW_RETURNING_STATEMENTS = {
    "SELECT",
    "SHOW",
    "DESCRIBE",
    "DESC",
    "EXPLAIN",
    "WITH",
    "VALUES",
    "TABLE",
}

_COMMENT_LINE = "--"
_COMMENT_BLOCK_START = "/*"
_COMMENT_BLOCK_END = "*/"


def split_sql_statements(sql: str) -> List[str]:
    """Split a SQL script on semicolons, respecting literals and comments."""

    statements: List[str] = []
    buffer: List[str] = []
    index = 0
    length = len(sql)
    quote: Optional[str] = None
    in_line_comment = False
    in_block_comment = False

    while index < length:
        char = sql[index]
        following = sql[index + 1] if index + 1 < length else ""

        if in_line_comment:
            buffer.append(char)
            if char in "\r\n":
                in_line_comment = False
            index += 1
            continue

        if in_block_comment:
            buffer.append(char)
            if char == "*" and following == "/":
                buffer.append("/")
                index += 2
                in_block_comment = False
            else:
                index += 1
            continue

        if quote is not None:
            buffer.append(char)
            if char == "\\" and following:
                buffer.append(following)
                index += 2
                continue
            if char == quote:
                if following == quote:  # escaped quote, e.g. 'it''s'
                    buffer.append(following)
                    index += 2
                    continue
                quote = None
            index += 1
            continue

        if char == "-" and following == "-":
            in_line_comment = True
            buffer.append(char)
            index += 1
            continue

        if char == "/" and following == "*":
            in_block_comment = True
            buffer.append(char)
            index += 1
            continue

        if char in ("'", '"', "`"):
            quote = char
            buffer.append(char)
            index += 1
            continue

        if char == ";":
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
            index += 1
            continue

        buffer.append(char)
        index += 1

    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)

    return [statement for statement in statements if _strip_leading_comments(statement)]


def _strip_leading_comments(statement: str) -> str:
    text = statement.lstrip()
    while text:
        if text.startswith(_COMMENT_LINE):
            newline = text.find("\n")
            text = "" if newline == -1 else text[newline + 1 :].lstrip()
            continue
        if text.startswith(_COMMENT_BLOCK_START):
            end = text.find(_COMMENT_BLOCK_END, 2)
            text = "" if end == -1 else text[end + 2 :].lstrip()
            continue
        break
    return text


def statement_type(statement: str) -> str:
    text = _strip_leading_comments(statement)
    token = ""
    for char in text:
        if char.isalpha():
            token += char
        elif token:
            break
        elif char.isspace():
            continue
        else:
            break
    return token.upper() or "UNKNOWN"


def classify_engine(statement: str, current_catalog: Optional[str] = None) -> str:
    """Best-effort engine classification used only for display metadata."""

    lowered = statement.lower()
    if "local_iceberg" in lowered or "using iceberg" in lowered:
        return "iceberg"
    if (
        "spark_catalog." in lowered
        or "using delta" in lowered
        or "using deltalake" in lowered
    ):
        return "delta"
    if current_catalog == "local_iceberg":
        return "iceberg"
    if current_catalog == "spark_catalog":
        return "delta"
    return "spark"


def row_to_jsonable(value: Any) -> Any:
    """Convert Spark/Python values into strict JSON-safe primitives."""

    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, dict):
        return {str(key): row_to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [row_to_jsonable(item) for item in value]

    # Handles pyspark.sql.types.Row, Decimal-like objects and numpy scalars.
    if hasattr(value, "asDict"):
        return row_to_jsonable(value.asDict(recursive=True))
    if hasattr(value, "to_pydatetime"):
        converted = value.to_pydatetime()
        if isinstance(converted, dt.datetime):
            return converted.isoformat()
    if hasattr(value, "item") and not isinstance(value, (dict, list, str)):
        try:
            return row_to_jsonable(value.item())
        except Exception:
            pass

    return str(value)


def preview_json(payload: Dict[str, Any], max_chars: int = 400) -> str:
    try:
        text = json.dumps(payload, default=str)
    except Exception:
        text = str(payload)
    return text if len(text) <= max_chars else text[:max_chars] + "..."
