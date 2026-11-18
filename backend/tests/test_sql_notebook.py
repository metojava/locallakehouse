from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.services.kernel_service import is_builtin, is_sql_kernel, list_kernels
from app.services.pyspark_engine import extract_sql_source


def test_line_magic_uses_inline_sql() -> None:
    assert extract_sql_source("%sql SELECT 1 AS answer") == "SELECT 1 AS answer"


def test_line_magic_uses_following_lines() -> None:
    script = "\n\n%sql\nSHOW TABLES"
    assert extract_sql_source(script) == "SHOW TABLES"


def test_cell_magic_uses_whole_body() -> None:
    script = "%%sql\nSELECT 1 AS answer\n"
    assert extract_sql_source(script) == "SELECT 1 AS answer"


def test_magic_is_case_insensitive() -> None:
    assert extract_sql_source("%SQL SELECT 1") == "SELECT 1"


def test_other_magics_and_python_are_not_sql() -> None:
    assert extract_sql_source("%sqlite3 my.db") is None
    assert extract_sql_source("x = 1\n%sql SELECT 1") is None
    assert extract_sql_source("spark.range(10)") is None


def test_empty_magic_has_no_statements() -> None:
    assert extract_sql_source("%%sql") == ""


def test_sql_is_a_builtin_kernel() -> None:
    kernels = {kernel["name"]: kernel for kernel in list_kernels()["kernels"]}

    assert kernels["sql"]["display_name"] == "SQL (Spark SQL built-in)"
    assert kernels["sql"]["language"] == "sql"
    assert kernels["sql"]["builtin"] is True
    assert is_builtin("sql")
    assert is_sql_kernel("SQL")
    assert not is_sql_kernel("python3")


def test_sql_kernel_routes_to_sql_executor(monkeypatch) -> None:
    calls: dict[str, str] = {}

    def fake_sql_cell(notebook_id, script, timeout_seconds=None, target=None):
        calls["notebook_id"] = notebook_id
        calls["script"] = script
        return {
            "script": script,
            "engine": "sql",
            "columns": [{"name": "answer", "type": "int"}],
            "rows": [{"answer": 1}],
            "row_count": 1,
            "execution_time_ms": 1.0,
            "truncated": False,
            "max_rows": 1000,
            "stdout": "",
            "stderr": "",
            "result_type": "spark.sql.DataFrame",
            "result_repr": None,
        }

    monkeypatch.setattr(routes, "execute_notebook_sql_cell", fake_sql_cell)

    with TestClient(app) as client:
        response = client.post(
            "/api/notebook/execute",
            json={
                "notebook_id": "sql.ipynb",
                "script": "SELECT 1 AS answer",
                "kernel_name": "sql",
            },
        )

    assert response.status_code == 200
    assert calls == {"notebook_id": "sql.ipynb", "script": "SELECT 1 AS answer"}
    assert response.json()["engine"] == "sql"


def test_scala_is_not_a_builtin_kernel() -> None:
    assert not is_builtin("scala")


def test_kernel_list_reports_scala_install_flag() -> None:
    data = list_kernels()

    assert "scala_installed" in data
    assert isinstance(data["scala_installed"], bool)
    assert data["scala_installed"] == any(
        kernel["language"] == "scala" for kernel in data["kernels"]
    )


def test_kernel_list_endpoint_includes_scala_flag() -> None:
    with TestClient(app) as client:
        response = client.get("/api/kernels")

    assert response.status_code == 200
    assert isinstance(response.json()["scala_installed"], bool)


def test_scala_kernel_routes_to_jupyter(monkeypatch) -> None:
    calls: dict[str, str] = {}

    def fake_execute(notebook_id, kernel_name, script, timeout_seconds=None, target=None):
        calls["notebook_id"] = notebook_id
        calls["kernel_name"] = kernel_name
        calls["script"] = script
        return {
            "script": script,
            "engine": kernel_name,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "execution_time_ms": 1.0,
            "truncated": False,
            "max_rows": 0,
            "stdout": "42\n",
            "stderr": "",
            "result_type": "text/plain",
            "result_repr": None,
        }

    monkeypatch.setattr(routes.kernel_service, "execute", fake_execute)

    with TestClient(app) as client:
        response = client.post(
            "/api/notebook/execute",
            json={
                "notebook_id": "scala.ipynb",
                "script": "println(42)",
                "kernel_name": "scala",
            },
        )

    assert response.status_code == 200
    assert calls == {
        "notebook_id": "scala.ipynb",
        "kernel_name": "scala",
        "script": "println(42)",
    }
    assert response.json()["stdout"] == "42\n"


def test_scala_install_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "install_scala_kernel",
        lambda: {
            "installed": True,
            "already_installed": False,
            "message": "Installed the Scala (almond) kernel.",
        },
    )

    with TestClient(app) as client:
        response = client.post("/api/kernels/scala/install")

    assert response.status_code == 200
    assert response.json()["installed"] is True
    assert "Scala" in response.json()["message"]


def test_scala_install_is_a_noop_when_present(monkeypatch) -> None:
    import app.services.kernel_service as kernel_service_module

    monkeypatch.setattr(
        kernel_service_module,
        "list_kernels",
        lambda: {"kernels": [{"language": "scala"}], "java_installed": False, "scala_installed": True},
    )

    result = kernel_service_module.install_scala_kernel()

    assert result["installed"] is False
    assert result["already_installed"] is True


def test_java_kernel_classpath_uses_spark_jars_glob(tmp_path, monkeypatch) -> None:
    import app.services.kernel_service as kernel_service_module

    (tmp_path / "jars").mkdir()
    monkeypatch.setattr(
        kernel_service_module,
        "resolve_spark_home",
        lambda: {"path": str(tmp_path)},
    )

    classpath = kernel_service_module._spark_jars_classpath()

    assert classpath == (tmp_path / "jars").as_posix() + "/*"
    assert "\\" not in classpath
    assert kernel_service_module._spark_kernel_env() == {
        "IJAVA_CLASSPATH": classpath
    }


def test_java_kernel_classpath_is_skipped_without_jars(tmp_path, monkeypatch) -> None:
    import app.services.kernel_service as kernel_service_module

    monkeypatch.setattr(
        kernel_service_module,
        "resolve_spark_home",
        lambda: {"path": str(tmp_path)},
    )

    assert kernel_service_module._spark_jars_classpath() is None
    assert kernel_service_module._spark_kernel_env() == {}
