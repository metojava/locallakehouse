from __future__ import annotations

from pathlib import Path

from app.services import spark_setup


def _make_spark_home(root: Path, version: str, scala: str) -> Path:
    (root / "bin").mkdir(parents=True)
    jars = root / "jars"
    jars.mkdir()
    (jars / f"scala-library-{scala}.12.jar").write_bytes(b"")
    (jars / f"spark-core_{scala.replace('.', '.')}-{version}.jar").write_bytes(b"")
    (root / "RELEASE").write_text(
        f"Spark {version} (git revision deadbeef) built for Hadoop 3.4.1\n",
        encoding="utf-8",
    )
    return root


def test_missing_path_is_not_valid(tmp_path: Path) -> None:
    info = spark_setup.describe_spark_home(tmp_path / "does-not-exist")
    assert info["exists"] is False
    assert info["valid"] is False
    assert info["compatible"] is False


def test_plain_directory_is_not_a_spark_install(tmp_path: Path) -> None:
    info = spark_setup.describe_spark_home(tmp_path)
    assert info["exists"] is True
    assert info["valid"] is False
    assert info["reason"]


def test_compatible_spark_home_is_accepted(tmp_path: Path) -> None:
    version = spark_setup.client_version()
    home = _make_spark_home(tmp_path / "spark", version, "2.13")
    info = spark_setup.describe_spark_home(home)
    assert info["valid"] is True
    assert info["version"] == version
    assert info["scala_version"] == "2.13"
    assert info["compatible"] is True
    assert info["reason"] is None


def test_old_spark_version_is_rejected(tmp_path: Path) -> None:
    home = _make_spark_home(tmp_path / "spark", "3.5.6", "2.12")
    info = spark_setup.describe_spark_home(home)
    assert info["valid"] is True
    assert info["compatible"] is False
    assert "3.5.6" in (info["reason"] or "")


def test_wrong_scala_is_rejected(tmp_path: Path) -> None:
    version = spark_setup.client_version()
    home = _make_spark_home(tmp_path / "spark", version, "2.12")
    info = spark_setup.describe_spark_home(home)
    assert info["compatible"] is False
    assert "Scala" in (info["reason"] or "")


def test_version_falls_back_to_jar_name(tmp_path: Path) -> None:
    home = _make_spark_home(tmp_path / "spark", "4.1.4", "2.13")
    (home / "RELEASE").unlink()
    assert spark_setup.read_release_version(home) == "4.1.4"
