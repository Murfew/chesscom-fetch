from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx2 import Client, MockTransport
from pytest_mock import MockFixture
from rich.console import Console
from typer.testing import CliRunner

import chesscom_fetch.cli
from chesscom_fetch import db
from chesscom_fetch.http import HttpClient
from chesscom_fetch.models import Game
from tests.helpers import TEST_USERNAME, Handler, MakeHttpClient


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


@pytest.fixture
def fake_game() -> Game:
    json_str = (Path(__file__).resolve().parent / Path("./fake_game.json")).read_text(
        encoding="utf-8"
    )

    return Game.model_validate_json(json_str)


@pytest.fixture
def make_http_client(mocker: MockFixture) -> MakeHttpClient:
    def _make_http_client(
        handler: Handler, wait_mock: MagicMock | None = None
    ) -> HttpClient:
        return HttpClient(
            Client(transport=MockTransport(handler)),
            TEST_USERNAME,
            wait_mock if wait_mock is not None else mocker.MagicMock(),
        )

    return _make_http_client
