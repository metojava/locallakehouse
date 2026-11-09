from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import workspace


@pytest.fixture()
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state = {"root": str(tmp_path)}

    monkeypatch.setattr(
        workspace,
        "get_runtime_setting",
        lambda key: state["root"] if key == workspace.WORKSPACE_ROOT_KEY else None,
    )
    monkeypatch.setattr(
        workspace,
        "set_runtime_setting",
        lambda key, value: state.__setitem__(key, value),
    )
    monkeypatch.setattr(
        workspace,
        "clear_runtime_setting",
        lambda key: state.__setitem__(key, None),
    )
    return tmp_path


def test_describe_workspace_builds_tree(root: Path) -> None:
    (root / "scripts").mkdir()
    (root / "scripts" / "job.py").write_text("print('hi')", encoding="utf-8")
    (root / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (root / "image.png").write_bytes(b"\x89PNG")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "dep.js").write_text("x", encoding="utf-8")

    result = workspace.describe_workspace()

    names = {entry["name"] for entry in result["tree"]}
    assert result["exists"] is True
    assert names == {"scripts", "data.csv"}
    scripts = next(entry for entry in result["tree"] if entry["name"] == "scripts")
    assert [child["name"] for child in scripts["children"]] == ["job.py"]


def test_read_and_write_text_file(root: Path) -> None:
    (root / "notes.md").write_text("hello", encoding="utf-8")

    read = workspace.read_text_file("notes.md")
    assert read["content"] == "hello"
    assert read["language"] == "markdown"

    saved = workspace.write_text_file("notes.md", "# updated")
    assert saved["size"] == len("# updated")
    assert (root / "notes.md").read_text(encoding="utf-8") == "# updated"


def test_path_traversal_is_rejected(root: Path) -> None:
    with pytest.raises(workspace.WorkspacePathError):
        workspace.read_text_file("../secrets.txt")


def test_missing_file_raises_not_found(root: Path) -> None:
    with pytest.raises(workspace.WorkspaceNotFoundError):
        workspace.read_text_file("missing.py")


def test_load_notebook_extracts_cells_and_outputs(root: Path) -> None:
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "cells": [
            {
                "cell_type": "markdown",
                "source": ["# Title\n", "Some text"],
                "metadata": {},
            },
            {
                "cell_type": "code",
                "source": ["print('hi')\n", "df"],
                "metadata": {},
                "outputs": [
                    {"output_type": "stream", "name": "stdout", "text": ["hi\n"]},
                    {
                        "output_type": "execute_result",
                        "data": {"text/plain": ["DataFrame[id: bigint]"]},
                        "metadata": {},
                        "execution_count": 1,
                    },
                ],
            },
        ],
    }
    (root / "demo.ipynb").write_text(json.dumps(notebook), encoding="utf-8")

    result = workspace.load_notebook("demo.ipynb")

    assert result["name"] == "demo.ipynb"
    assert result["cells"][0]["type"] == "markdown"
    assert result["cells"][0]["source"] == "# Title\nSome text"
    assert result["cells"][1]["outputs"][0] == {"kind": "text", "text": "hi\n"}
    assert result["cells"][1]["outputs"][1]["text"] == "DataFrame[id: bigint]"


def test_open_workspace_validates_directory(root: Path) -> None:
    with pytest.raises(workspace.WorkspaceError):
        workspace.open_workspace(str(root / "does-not-exist"))


def test_create_notebook_writes_empty_notebook(root: Path) -> None:
    result = workspace.create_notebook("new_analysis")

    assert result["name"] == "new_analysis.ipynb"
    assert result["cells"] == []
    content = json.loads((root / "new_analysis.ipynb").read_text(encoding="utf-8"))
    assert content["nbformat"] == 4
    assert content["cells"] == []


def test_create_notebook_rejects_duplicate_and_traversal(root: Path) -> None:
    (root / "existing.ipynb").write_text("{}", encoding="utf-8")

    with pytest.raises(workspace.WorkspaceError):
        workspace.create_notebook("existing.ipynb")
    with pytest.raises(workspace.WorkspacePathError):
        workspace.create_notebook("../escape.ipynb")


def test_resolve_data_path_supports_logical_and_absolute(root: Path) -> None:
    data = root / "data" / "sales.csv"
    data.parent.mkdir()
    data.write_text("a\n1\n", encoding="utf-8")

    assert workspace.resolve_data_path("data/sales.csv") == str(data.resolve())
    assert workspace.resolve_data_path(str(data)) == str(data.resolve())

    with pytest.raises(workspace.WorkspaceNotFoundError):
        workspace.resolve_data_path("data/missing.csv")
    with pytest.raises(workspace.WorkspacePathError):
        workspace.resolve_data_path("../outside.csv")
