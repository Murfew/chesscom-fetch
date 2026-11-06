from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

import chesscom_fetch.cli
from chesscom_fetch import db


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    db.init_db(db_path)
    return db_path


@pytest.fixture(autouse=True)
def setup_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "1000")
    monkeypatch.setenv("TERMINAL_WIDTH", "1000")
    monkeypatch.setattr(
        chesscom_fetch.cli,
        "console",
        Console(force_terminal=False, color_system=None),
    )
    monkeypatch.setattr(
        chesscom_fetch.cli,
        "err_console",
        Console(stderr=True, force_terminal=False, color_system=None),
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
